"""Custom exceptions for the Notion API client."""


class NotionClientError(Exception):
    """Raised when a Notion API request fails.

    This exception covers HTTP errors, API-level errors returned by Notion,
    and configuration issues such as missing authentication tokens.
    """

    pass
