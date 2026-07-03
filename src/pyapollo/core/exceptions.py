"""Apollo client exceptions."""


class ApolloClientError(Exception):
    """Base exception for Apollo client errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ServerNotResponseException(ApolloClientError):
    """Raised when the Apollo server does not respond."""
