"""Tests for newsletter service module."""

import unittest

from src.database.base import compute_url_hash


class TestComputeUrlHash(unittest.TestCase):
    """Tests for URL hash computation."""

    def test_computes_consistent_hash(self) -> None:
        """Test that the same URL produces the same hash."""
        url = "https://example.com/article/123"
        hash1 = compute_url_hash(url)
        hash2 = compute_url_hash(url)

        self.assertEqual(hash1, hash2)

    def test_hash_is_64_characters(self) -> None:
        """Test that hash is SHA256 hex (64 characters)."""
        url = "https://example.com/article"
        result = compute_url_hash(url)

        self.assertEqual(len(result), 64)

    def test_normalises_trailing_slash(self) -> None:
        """Test that trailing slashes are normalised."""
        url1 = "https://example.com/article/"
        url2 = "https://example.com/article"

        hash1 = compute_url_hash(url1)
        hash2 = compute_url_hash(url2)

        self.assertEqual(hash1, hash2)

    def test_normalises_case(self) -> None:
        """Test that URL case is normalised."""
        url1 = "HTTPS://EXAMPLE.COM/ARTICLE"
        url2 = "https://example.com/article"

        hash1 = compute_url_hash(url1)
        hash2 = compute_url_hash(url2)

        self.assertEqual(hash1, hash2)

    def test_normalises_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        url1 = "  https://example.com/article  "
        url2 = "https://example.com/article"

        hash1 = compute_url_hash(url1)
        hash2 = compute_url_hash(url2)

        self.assertEqual(hash1, hash2)

    def test_different_urls_produce_different_hashes(self) -> None:
        """Test that different URLs produce different hashes."""
        url1 = "https://example.com/article/1"
        url2 = "https://example.com/article/2"

        hash1 = compute_url_hash(url1)
        hash2 = compute_url_hash(url2)

        self.assertNotEqual(hash1, hash2)


if __name__ == "__main__":
    unittest.main()
