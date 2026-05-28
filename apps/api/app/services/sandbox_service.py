import ast
import logging
import asyncio
from typing import Dict, Any, List
from bs4 import BeautifulSoup
import re
import json
import datetime
from concurrent.futures import ProcessPoolExecutor
from app.core.config import settings

logger = logging.getLogger(__name__)

BANNED_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", 
    "importlib", "requests", "httpx", "urllib", "builtins"
}

BANNED_FUNCTIONS = {
    "eval", "exec", "open", "compile", "globals", "locals", 
    "getattr", "setattr", "delattr"
}

ALLOWED_SANDBOX_IMPORTS = {
    "bs4", "beautifulsoup4", "re", "json", "datetime", "lxml"
}

class ASTValidationError(Exception):
    """Raised when generated code contains unsafe AST nodes."""
    pass

class SandboxService:
    @staticmethod
    def verify_ast_safety(code: str) -> None:
        """
        Parses the code into an AST and verifies it contains no unsafe constructs
        such as banned module imports or execution helpers.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise ASTValidationError(f"Generated code is not syntactically valid Python: {str(e)}")

        for node in ast.walk(tree):
            # Check for import os, sys, etc.
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name_root = alias.name.split('.')[0]
                    if name_root in BANNED_MODULES:
                        raise ASTValidationError(f"Unsafe import detected in script: import {alias.name}")
            
            # Check for from os import ...
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name_root = node.module.split('.')[0]
                    if name_root in BANNED_MODULES:
                        raise ASTValidationError(f"Unsafe import detected in script: from {node.module} import ...")
            
            # Check for calls to eval, exec, open
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in BANNED_FUNCTIONS:
                        raise ASTValidationError(f"Unsafe function call detected in script: {node.func.id}()")
                elif isinstance(node.func, ast.Attribute):
                    if getattr(node.func, "attr", None) in BANNED_FUNCTIONS:
                        raise ASTValidationError(f"Unsafe attribute call detected in script: .{node.func.attr}()")

    @staticmethod
    def _execute_in_restricted_env(code: str, html_content: str, dom_tree: dict) -> List[Dict[str, Any]]:
        """
        Executes code inside a restricted runtime environment.
        This function runs in a separate process for isolation and CPU protection.
        """
        # Define a safe import function wrapper to allow whitelist modules
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            name_root = name.split('.')[0]
            if name_root not in ALLOWED_SANDBOX_IMPORTS:
                raise ImportError(f"Import of module '{name}' is restricted inside this sandbox.")
            return __import__(name, globals, locals, fromlist, level)

        # Build safe builtins namespace
        safe_builtins = {
            "__import__": safe_import,
            "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool, "chr": chr,
            "dict": dict, "dir": dir, "divmod": divmod, "enumerate": enumerate, "filter": filter,
            "float": float, "format": format, "hash": hash, "hex": hex, "id": id, "int": int,
            "isinstance": isinstance, "issubclass": issubclass, "iter": iter, "len": len,
            "list": list, "map": map, "max": max, "min": min, "next": next, "oct": oct,
            "ord": ord, "pow": pow, "print": print, "range": range, "repr": repr, "reversed": reversed,
            "round": round, "set": set, "slice": slice, "sorted": sorted, "str": str, "sum": sum,
            "tuple": tuple, "type": type, "zip": zip,
            "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
            "KeyError": KeyError, "IndexError": IndexError, "AttributeError": AttributeError
        }

        # Build custom global variables context containing allowed libraries and parameters
        restricted_globals = {
            "__builtins__": safe_builtins,
            "BeautifulSoup": BeautifulSoup,
            "bs4": BeautifulSoup,
            "re": re,
            "json": json,
            "datetime": datetime,
        }

        local_vars: Dict[str, Any] = {}
        try:
            compiled_code = compile(code, "<sandbox>", "exec")
            exec(compiled_code, restricted_globals, local_vars)
            
            if "extract" not in local_vars:
                raise Exception("Script does not define an 'extract' function.")
            
            extract_fn = local_vars["extract"]
            
            result = extract_fn(html_content, dom_tree)
            if asyncio.iscoroutine(result):
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(result)
                
            if not isinstance(result, list):
                raise Exception("Extractor must return a list of dictionaries.")
                
            return result
        except Exception as e:
            logger.error(f"Execution error in sandbox namespace: {str(e)}")
            raise e

    @classmethod
    async def execute_extractor(
        cls,
        code: str,
        html_content: str,
        dom_tree: dict
    ) -> List[Dict[str, Any]]:
        """
        Runs the generated code inside a restricted execution block.
        Ensures AST verification passes before running code.
        """
        # Step 1: Static validation
        cls.verify_ast_safety(code)
        
        logger.info("AST safety check passed. Starting sandbox subprocess execution.")
        
        # Step 2: Resource-bounded execution using a Process Pool
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(max_workers=1) as executor:
            try:
                fut = loop.run_in_executor(
                    executor,
                    cls._execute_in_restricted_env,
                    code,
                    html_content,
                    dom_tree
                )
                return await asyncio.wait_for(fut, timeout=settings.SANDBOX_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                logger.error("Sandbox execution timeout exceeded.")
                raise Exception("Sandbox execution timeout exceeded.")
            except Exception as e:
                logger.error(f"Failed to execute extractor in sandbox: {str(e)}")
                raise e
