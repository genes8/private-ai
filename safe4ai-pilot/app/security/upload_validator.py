"""Upload validator: enforce extension, MIME type, magic bytes, and file size."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import magic

from app.config import settings
from app.models import GuardResult

ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".xlsx", ".txt"}
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
}

MAX_SIZE_BYTES: int = settings.max_upload_size_mb * 1024 * 1024


class UploadValidator:
    def validate(
        self,
        filename: str,
        content_type: str,
        file_bytes: bytes,
    ) -> GuardResult:
        """Validate an uploaded file.

        Checks (in order):
        1. File extension must be in ALLOWED_EXTENSIONS.
        2. Declared Content-Type must be in ALLOWED_MIME_TYPES.
        3. Actual MIME type (magic bytes) must be in ALLOWED_MIME_TYPES.
        4. File size must not exceed MAX_SIZE_BYTES.
        """
        # 1. Extension check
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            return GuardResult(allowed=False, reason=f"File extension '{suffix}' is not allowed")

        # 2. Declared content-type check
        if content_type not in ALLOWED_MIME_TYPES:
            return GuardResult(
                allowed=False,
                reason=f"Content-Type '{content_type}' is not allowed",
            )

        # 3. Magic-bytes check
        detected_mime = magic.from_buffer(file_bytes, mime=True)
        if detected_mime not in ALLOWED_MIME_TYPES:
            return GuardResult(
                allowed=False,
                reason=f"Detected MIME type '{detected_mime}' is not allowed",
            )

        # 4. Size check
        if len(file_bytes) > MAX_SIZE_BYTES:
            return GuardResult(
                allowed=False,
                reason=(
                    f"File size {len(file_bytes)} bytes exceeds maximum {MAX_SIZE_BYTES} bytes"
                ),
            )

        return GuardResult(allowed=True, reason="ok")

    def safe_filename(self) -> str:
        """Return a safe, random storage filename (never trust client filename)."""
        return str(uuid4())
