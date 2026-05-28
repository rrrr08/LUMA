"""
Unit tests for app.core.security

Covers:
- generate_api_key: format, uniqueness, prefix
- hash_api_key: determinism, output format
- verify_api_key: correct match, wrong-key rejection
"""
import pytest
from app.core.security import generate_api_key, hash_api_key, verify_api_key, API_KEY_PREFIX


class TestGenerateApiKey:
    def test_returns_tuple_of_two_strings(self):
        raw_key, hashed_key = generate_api_key()
        assert isinstance(raw_key, str)
        assert isinstance(hashed_key, str)

    def test_raw_key_has_correct_prefix(self):
        raw_key, _ = generate_api_key()
        assert raw_key.startswith(API_KEY_PREFIX)

    def test_raw_key_has_sufficient_length(self):
        raw_key, _ = generate_api_key()
        # Prefix (8) + at least 32 base64url chars from token_urlsafe(32)
        assert len(raw_key) >= 40

    def test_keys_are_unique_across_calls(self):
        raw1, hash1 = generate_api_key()
        raw2, hash2 = generate_api_key()
        assert raw1 != raw2
        assert hash1 != hash2

    def test_hashed_key_matches_hash_of_raw(self):
        raw_key, hashed_key = generate_api_key()
        assert hashed_key == hash_api_key(raw_key)


class TestHashApiKey:
    def test_returns_hex_string(self):
        result = hash_api_key("test_key")
        # SHA-256 hex digest is always 64 chars
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_is_deterministic(self):
        result1 = hash_api_key("my_api_key")
        result2 = hash_api_key("my_api_key")
        assert result1 == result2

    def test_different_inputs_produce_different_hashes(self):
        hash1 = hash_api_key("key_one")
        hash2 = hash_api_key("key_two")
        assert hash1 != hash2

    def test_empty_string_produces_valid_hash(self):
        result = hash_api_key("")
        assert len(result) == 64


class TestVerifyApiKey:
    def test_correct_key_returns_true(self):
        raw_key, stored_hash = generate_api_key()
        assert verify_api_key(raw_key, stored_hash) is True

    def test_wrong_key_returns_false(self):
        _, stored_hash = generate_api_key()
        assert verify_api_key("sk_live_wrongkey", stored_hash) is False

    def test_empty_key_against_real_hash_returns_false(self):
        _, stored_hash = generate_api_key()
        assert verify_api_key("", stored_hash) is False

    def test_tampered_hash_returns_false(self):
        raw_key, _ = generate_api_key()
        assert verify_api_key(raw_key, "a" * 64) is False
