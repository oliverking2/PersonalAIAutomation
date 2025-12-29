"""Tests for Substack post module."""

import unittest
from unittest.mock import MagicMock, patch

from src.substack.post import Post


class TestPost(unittest.TestCase):
    """Tests for Post class."""

    def test_init_parses_url_correctly(self) -> None:
        """Test that URL is parsed correctly."""
        post = Post("https://example.substack.com/p/my-post-slug")

        self.assertEqual(post.url, "https://example.substack.com/p/my-post-slug")
        self.assertEqual(post.base_url, "https://example.substack.com")
        self.assertEqual(post.slug, "my-post-slug")

    def test_init_handles_trailing_slash(self) -> None:
        """Test that trailing slashes are stripped when parsing slug."""
        post = Post("https://example.substack.com/p/my-post/")

        self.assertEqual(post.slug, "my-post")

    def test_str_representation(self) -> None:
        """Test string representation."""
        post = Post("https://example.substack.com/p/test-post")

        self.assertEqual(str(post), "Post: https://example.substack.com/p/test-post")

    def test_repr_representation(self) -> None:
        """Test repr representation."""
        post = Post("https://example.substack.com/p/test-post")

        self.assertEqual(repr(post), "Post(url='https://example.substack.com/p/test-post')")

    @patch("src.substack.post.requests.get")
    def test_fetch_post_data_caches_result(self, mock_get: MagicMock) -> None:
        """Test that post data is cached after first fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "Test Post"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")
        post._fetch_post_data()
        post._fetch_post_data()

        mock_get.assert_called_once()

    @patch("src.substack.post.requests.get")
    def test_fetch_post_data_force_refresh(self, mock_get: MagicMock) -> None:
        """Test that force_refresh bypasses cache."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "Test Post"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")
        post._fetch_post_data()
        post._fetch_post_data(force_refresh=True)

        self.assertEqual(mock_get.call_count, 2)

    @patch("src.substack.post.requests.get")
    def test_get_metadata_returns_full_data(self, mock_get: MagicMock) -> None:
        """Test get_metadata returns full post data."""
        expected_data = {
            "title": "Test Post",
            "subtitle": "A subtitle",
            "body_html": "<p>Content</p>",
        }
        mock_response = MagicMock()
        mock_response.json.return_value = expected_data
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")
        result = post.get_metadata()

        self.assertEqual(result, expected_data)

    @patch("src.substack.post.requests.get")
    def test_get_content_returns_html(self, mock_get: MagicMock) -> None:
        """Test get_content returns body HTML."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"body_html": "<p>Post content</p>"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")
        content = post.get_content()

        self.assertEqual(content, "<p>Post content</p>")

    @patch("src.substack.post.requests.get")
    def test_get_content_returns_none_for_paywalled(self, mock_get: MagicMock) -> None:
        """Test get_content returns None for paywalled content without auth."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"body_html": None, "audience": "only_paid"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")
        content = post.get_content()

        self.assertIsNone(content)

    @patch("src.substack.post.requests.get")
    def test_is_paywalled_true(self, mock_get: MagicMock) -> None:
        """Test is_paywalled returns True for paid content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"audience": "only_paid"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")

        self.assertTrue(post.is_paywalled)

    @patch("src.substack.post.requests.get")
    def test_is_paywalled_false(self, mock_get: MagicMock) -> None:
        """Test is_paywalled returns False for free content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"audience": "everyone"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")

        self.assertFalse(post.is_paywalled)

    @patch("src.substack.post.requests.get")
    def test_title_property(self, mock_get: MagicMock) -> None:
        """Test title property returns post title."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "My Great Post"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")

        self.assertEqual(post.title, "My Great Post")

    @patch("src.substack.post.requests.get")
    def test_subtitle_property(self, mock_get: MagicMock) -> None:
        """Test subtitle property returns post subtitle."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"subtitle": "A great subtitle"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")

        self.assertEqual(post.subtitle, "A great subtitle")

    @patch("src.substack.post.requests.get")
    def test_subtitle_returns_none_when_missing(self, mock_get: MagicMock) -> None:
        """Test subtitle returns None when not present."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "Post"}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")

        self.assertIsNone(post.subtitle)

    @patch("src.substack.post.requests.get")
    def test_publication_id_property(self, mock_get: MagicMock) -> None:
        """Test publication_id property returns correct ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"publication_id": 12345}
        mock_get.return_value = mock_response

        post = Post("https://example.substack.com/p/test")

        self.assertEqual(post.publication_id, 12345)

    def test_uses_authenticated_client(self) -> None:
        """Test that authenticated client is used when provided."""
        mock_client = MagicMock()
        mock_client.authenticated = True
        mock_response = MagicMock()
        mock_response.json.return_value = {"title": "Test"}
        mock_client.get.return_value = mock_response

        post = Post("https://example.substack.com/p/test", client=mock_client)
        post._fetch_post_data()

        mock_client.get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
