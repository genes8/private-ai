"""Domain exceptions for settings validation.

Services raise these; route handlers translate them to HTTP responses.
This keeps FastAPI imports out of the service layer so the logic can
be called from CLI scripts, background jobs, or tests without triggering
HTTP-specific behaviour.
"""
from __future__ import annotations


class SettingsValidationError(Exception):
    """A field value or configuration invariant failed validation.

    Route handlers translate this to HTTP 422.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class EmbeddingDimensionConflict(Exception):
    """New embedding model's vector dimension conflicts with the Qdrant collection.

    Route handlers translate this to HTTP 409.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
