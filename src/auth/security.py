"""
Security & File Validation Module.
Provides upload size limits, MIME verification, and ClamAV virus scanner abstraction.
"""

from abc import ABC, abstractmethod
import logging
from typing import Tuple
from fastapi import HTTPException, UploadFile, status
from src.config.settings import settings

logger = logging.getLogger(__name__)


class VirusScanner(ABC):
    """Abstract Virus Scanner Adapter Interface."""

    @abstractmethod
    async def scan_bytes(self, content: bytes, filename: str) -> Tuple[bool, str]:
        """Scan file content for malware. Returns (is_clean, virus_name)."""
        pass


class MockClamAVScanner(VirusScanner):
    """ClamAV Virus Scanner mock implementation for dev/test."""

    async def scan_bytes(self, content: bytes, filename: str) -> Tuple[bool, str]:
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content or "virus" in filename.lower():
            logger.warning(f"[VirusScanner] MALWARE DETECTED in file '{filename}'!")
            return False, "Win32.TestMalware.EICAR"
        return True, "CLEAN"


async def validate_upload_file(
    file: UploadFile,
    virus_scanner: VirusScanner | None = None,
) -> bytes:
    """
    Validates uploaded PDF file against security controls:
    1. Extension check (.pdf)
    2. Size check (<= MAX_UPLOAD_SIZE_MB)
    3. PDF magic byte header check (%PDF-)
    4. Virus scan check
    """
    scanner = virus_scanner or MockClamAVScanner()

    # 1. File extension validation
    filename = file.filename or "unknown.pdf"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '.{ext}'. Allowed file types: {settings.ALLOWED_FILE_TYPES}",
        )

    # Read bytes
    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # 2. File size limit
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({len(content)} bytes) exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    # 3. Magic header byte check (%PDF-)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF magic byte header. File is not a valid PDF document.",
        )

    # 4. Virus scan clearance
    is_clean, scan_msg = await scanner.scan_bytes(content, filename)
    if not is_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Security scan rejected file: Malware detected ({scan_msg})",
        )

    return content
