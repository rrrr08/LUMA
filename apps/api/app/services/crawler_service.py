import base64
import logging
import sys
import asyncio
import threading
from typing import Dict, Any
from playwright.async_api import async_playwright
from app.core.config import settings

logger = logging.getLogger(__name__)

class CrawlerService:
    @classmethod
    async def crawl(cls, url: str, capture_screenshot: bool = True, proxy_settings: dict = None) -> Dict[str, Any]:
        """
        Public crawl entrypoint. Runs the async crawling process inside a dedicated 
        thread with a WindowsProactorEventLoop on Windows systems to bypass 
        Uvicorn's SelectorEventLoop limitations.
        """
        loop = asyncio.get_running_loop()
        
        # Run the thread-bound crawl helper using a Future to return the data asynchronously
        fut = loop.create_future()
        
        def thread_worker():
            try:
                # Force Proactor loop on Windows in this thread context
                if sys.platform == "win32":
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                
                thread_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(thread_loop)
                
                try:
                    result = thread_loop.run_until_complete(
                        cls._crawl_async(url, capture_screenshot, proxy_settings)
                    )
                    loop.call_soon_threadsafe(fut.set_result, result)
                except Exception as ex:
                    loop.call_soon_threadsafe(fut.set_exception, ex)
                finally:
                    thread_loop.close()
            except Exception as outer_ex:
                loop.call_soon_threadsafe(fut.set_exception, outer_ex)

        thread = threading.Thread(target=thread_worker, daemon=True)
        thread.start()
        
        return await fut

    @staticmethod
    async def _crawl_async(url: str, capture_screenshot: bool, proxy_settings: dict = None) -> Dict[str, Any]:
        """
        Internal async crawler logic executing Playwright page crawls.
        """
        logger.info(f"Thread worker starting crawl for URL: {url}")
        
        launch_args = {
            "headless": settings.PLAYWRIGHT_HEADLESS,
            "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        }
        
        if proxy_settings and proxy_settings.get("enabled"):
            server = proxy_settings.get("server")
            if server:
                proxy_param = {"server": server}
                if proxy_settings.get("username"):
                    proxy_param["username"] = proxy_settings.get("username")
                if proxy_settings.get("password"):
                    proxy_param["password"] = proxy_settings.get("password")
                launch_args["proxy"] = proxy_param
                logger.info(f"Using proxy server: {server}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_args)
            
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()
            
            # Hook resource interceptor to drop heavy assets
            await page.route("**/*", lambda route: 
                route.abort() if route.request.resource_type in ["media", "font", "websocket"] 
                else route.continue_()
            )
            
            try:
                response = await page.goto(url, wait_until="load", timeout=settings.PLAYWRIGHT_TIMEOUT_MS)
                if not response:
                    raise Exception("Failed to get response from URL")
                
                if response.status >= 400:
                    raise Exception(f"HTTP error status: {response.status}")
                
                await page.wait_for_timeout(1500)
                
                title = await page.title()
                html = await page.content()
                final_url = page.url
                
                screenshot_b64 = ""
                if capture_screenshot:
                    screenshot_bytes = await page.screenshot(type="jpeg", quality=60, full_page=False)
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                
                dom_tree = await page.evaluate("""
                    () => {
                        function simplifyNode(node) {
                            if (node.nodeType === Node.TEXT_NODE) {
                                const text = node.textContent.trim();
                                return text ? { type: '#text', text: text } : null;
                            }
                            if (node.nodeType !== Node.ELEMENT_NODE) return null;
                            
                            const tagName = node.tagName.toLowerCase();
                            if (['script', 'style', 'noscript', 'svg', 'iframe', 'head', 'link', 'meta'].includes(tagName)) return null;
                            
                            const rect = node.getBoundingClientRect();
                            const simplified = {
                                type: 'element',
                                tag: tagName,
                                id: node.id || undefined,
                                classes: node.className && typeof node.className === 'string' ? node.className.split(/\\s+/).filter(Boolean) : undefined,
                                href: node.href || undefined,
                                src: node.src || undefined,
                                rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
                                children: []
                            };
                            
                            for (let child of node.childNodes) {
                                const simplifiedChild = simplifyNode(child);
                                if (simplifiedChild) {
                                    simplified.children.push(simplifiedChild);
                                }
                            }
                            
                            if (simplified.children.length === 0 && !simplified.href && !simplified.src) {
                                const text = node.textContent.trim();
                                if (text) {
                                    simplified.text = text;
                                } else {
                                    return null;
                                }
                            }
                            return simplified;
                        }
                        return simplifyNode(document.body);
                    }
                """)
                
                logger.info(f"Thread worker completed crawl successfully for URL: {url}")
                return {
                    "final_url": final_url,
                    "html": html,
                    "title": title,
                    "dom_tree": dom_tree,
                    "screenshot_b64": screenshot_b64
                }
            except Exception as e:
                logger.error(f"Error inside thread crawl run: {str(e)}")
                raise e
            finally:
                await browser.close()
