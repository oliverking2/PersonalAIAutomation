"""Tests for Substack newsletter module."""

import unittest
from unittest.mock import MagicMock, patch

from src.substack.newsletter import Newsletter, _host_from_url, _match_publication


class TestHostFromUrl(unittest.TestCase):
    """Tests for _host_from_url function."""

    def test_extracts_host_from_full_url(self) -> None:
        """Test extraction from full URL."""
        result = _host_from_url("https://example.substack.com/p/post")

        self.assertEqual(result, "example.substack.com")

    def test_handles_url_without_scheme(self) -> None:
        """Test extraction from URL without scheme."""
        result = _host_from_url("example.substack.com")

        self.assertEqual(result, "example.substack.com")

    def test_lowercases_host(self) -> None:
        """Test that host is lowercased."""
        result = _host_from_url("EXAMPLE.Substack.COM")

        self.assertEqual(result, "example.substack.com")


class TestMatchPublication(unittest.TestCase):
    """Tests for _match_publication function."""

    def test_matches_by_custom_domain(self) -> None:
        """Test matching by custom domain."""
        search_results = {
            "publications": [
                {"id": 1, "custom_domain": "example.com", "subdomain": "other"},
            ]
        }

        result = _match_publication(search_results, "example.com")

        self.assertEqual(result["id"], 1)

    def test_matches_by_subdomain(self) -> None:
        """Test matching by subdomain."""
        search_results = {
            "publications": [
                {"id": 2, "custom_domain": None, "subdomain": "mynewsletter"},
            ]
        }

        result = _match_publication(search_results, "mynewsletter.substack.com")

        self.assertEqual(result["id"], 2)

    def test_returns_none_when_no_match(self) -> None:
        """Test returns None when no match found."""
        search_results = {"publications": []}

        result = _match_publication(search_results, "unknown.substack.com")

        self.assertIsNone(result)


class TestNewsletter(unittest.TestCase):
    """Tests for Newsletter class."""

    def test_init_strips_trailing_slash(self) -> None:
        """Test that trailing slash is stripped from URL."""
        with patch("src.substack.newsletter._client"):
            newsletter = Newsletter("https://example.substack.com/")

        self.assertEqual(newsletter.url, "https://example.substack.com")

    def test_str_representation(self) -> None:
        """Test string representation."""
        with patch("src.substack.newsletter._client"):
            newsletter = Newsletter("https://example.substack.com")

        self.assertEqual(str(newsletter), "Newsletter: https://example.substack.com")

    def test_repr_representation(self) -> None:
        """Test repr representation."""
        with patch("src.substack.newsletter._client"):
            newsletter = Newsletter("https://example.substack.com")

        self.assertEqual(repr(newsletter), "Newsletter(url='https://example.substack.com')")

    def test_get_posts_returns_post_objects(self) -> None:
        """Test get_posts returns Post objects."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = [
            {"canonical_url": "https://example.substack.com/p/post-1"},
            {"canonical_url": "https://example.substack.com/p/post-2"},
        ]

        newsletter = Newsletter("https://example.substack.com", client=mock_client)
        posts = newsletter.get_posts(limit=2)

        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].url, "https://example.substack.com/p/post-1")

    def test_get_posts_with_limit(self) -> None:
        """Test get_posts respects limit parameter."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = [
            {"canonical_url": f"https://example.substack.com/p/post-{i}"} for i in range(10)
        ]

        newsletter = Newsletter("https://example.substack.com", client=mock_client)
        posts = newsletter.get_posts(limit=3)

        self.assertEqual(len(posts), 3)

    def test_search_posts(self) -> None:
        """Test search_posts returns matching posts."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = [
            {"canonical_url": "https://example.substack.com/p/matching-post"},
        ]

        newsletter = Newsletter("https://example.substack.com", client=mock_client)
        posts = newsletter.search_posts("test query")

        self.assertEqual(len(posts), 1)
        # Verify search param was included in the call
        call_kwargs = mock_client.get_json.call_args.kwargs
        self.assertIn("search", call_kwargs["params"])

    def test_get_podcasts(self) -> None:
        """Test get_podcasts returns podcast posts."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = [
            {"canonical_url": "https://example.substack.com/p/episode-1"},
        ]

        newsletter = Newsletter("https://example.substack.com", client=mock_client)
        podcasts = newsletter.get_podcasts()

        self.assertEqual(len(podcasts), 1)
        # Verify type param was included
        call_kwargs = mock_client.get_json.call_args.kwargs
        self.assertEqual(call_kwargs["params"]["type"], "podcast")

    def test_get_authors(self) -> None:
        """Test get_authors returns User objects."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = [
            {"handle": "author1"},
            {"handle": "author2"},
        ]

        newsletter = Newsletter("https://example.substack.com", client=mock_client)
        authors = newsletter.get_authors()

        self.assertEqual(len(authors), 2)
        self.assertEqual(authors[0].username, "author1")

    def test_resolve_publication_id(self) -> None:
        """Test _resolve_publication_id finds ID via search."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = {
            "publications": [
                {"id": 12345, "subdomain": "example", "custom_domain": None},
            ]
        }

        newsletter = Newsletter("https://example.substack.com", client=mock_client)
        pub_id = newsletter._resolve_publication_id()

        self.assertEqual(pub_id, 12345)

    def test_get_recommendations(self) -> None:
        """Test get_recommendations returns Newsletter objects."""
        mock_client = MagicMock()

        # First call returns publication search results, second returns recommendations
        mock_client.get_json.side_effect = [
            {"publications": [{"id": 123, "subdomain": "example", "custom_domain": None}]},
            [
                {"recommendedPublication": {"subdomain": "rec1", "custom_domain": None}},
                {"recommendedPublication": {"subdomain": None, "custom_domain": "rec2.com"}},
            ],
        ]

        newsletter = Newsletter("https://example.substack.com", client=mock_client)
        recommendations = newsletter.get_recommendations()

        self.assertEqual(len(recommendations), 2)
        self.assertIn("rec1.substack.com", recommendations[0].url)
        self.assertIn("rec2.com", recommendations[1].url)

    def test_uses_provided_client(self) -> None:
        """Test that provided client is used."""
        mock_client = MagicMock()
        mock_client.get_json.return_value = []

        newsletter = Newsletter("https://example.substack.com", client=mock_client)
        newsletter.get_posts()

        mock_client.get_json.assert_called()


if __name__ == "__main__":
    unittest.main()
