"""
Unit tests for Auth and Security validation modules.
"""

from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile

from src.api.deps import get_current_user
from src.auth.jwt import create_access_token, decode_access_token, get_password_hash, verify_password
from src.auth.security import validate_upload_file
from src.config.settings import settings


def test_jwt_token_flow():
    token = create_access_token({"sub": "admin_user", "role": "admin"})
    token_data = decode_access_token(token)
    assert token_data.username == "admin_user"
    assert token_data.role == "admin"


def test_password_hashing():
    raw_pass = "SuperSecret123!"
    hashed = get_password_hash(raw_pass)
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


@pytest.mark.asyncio
async def test_get_current_user_requires_authorization_header():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(None)

    assert exc_info.value.status_code == 401
    assert "Authorization header is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validate_upload_file_valid():
    valid_pdf_content = b"%PDF-1.4 header text sample invoice content"
    file = UploadFile(filename="sample_invoice.pdf", file=BytesIO(valid_pdf_content))
    content = await validate_upload_file(file)
    assert content == valid_pdf_content


@pytest.mark.asyncio
async def test_validate_upload_file_invalid_header():
    invalid_content = b"NOT_A_PDF_FILE_PLAIN_TEXT"
    file = UploadFile(filename="bad_file.pdf", file=BytesIO(invalid_content))
    with pytest.raises(HTTPException) as exc_info:
        await validate_upload_file(file)
    assert exc_info.value.status_code == 400
    assert "Invalid PDF magic byte header" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validate_upload_file_rejects_empty_and_non_pdf_extension():
    empty_pdf = UploadFile(filename="empty.pdf", file=BytesIO())
    with pytest.raises(HTTPException) as empty_error:
        await validate_upload_file(empty_pdf)
    assert empty_error.value.status_code == 400
    assert "empty" in empty_error.value.detail.lower()

    text_file = UploadFile(filename="invoice.txt", file=BytesIO(b"%PDF-1.4"))
    with pytest.raises(HTTPException) as extension_error:
        await validate_upload_file(text_file)
    assert extension_error.value.status_code == 400
    assert "Invalid file extension" in extension_error.value.detail


@pytest.mark.asyncio
async def test_validate_upload_file_virus():
    virus_content = b"%PDF-1.4 EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
    file = UploadFile(filename="infected_invoice.pdf", file=BytesIO(virus_content))
    with pytest.raises(HTTPException) as exc_info:
        await validate_upload_file(file)
    assert exc_info.value.status_code == 422
    assert "Malware detected" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validate_upload_file_fails_closed_without_scanner():
    original_value = settings.ALLOW_MOCK_VIRUS_SCANNER
    settings.ALLOW_MOCK_VIRUS_SCANNER = False
    try:
        file = UploadFile(filename="invoice.pdf", file=BytesIO(b"%PDF-1.4 content"))
        with pytest.raises(HTTPException) as exc_info:
            await validate_upload_file(file)
        assert exc_info.value.status_code == 503
        assert "scanner is not configured" in exc_info.value.detail
    finally:
        settings.ALLOW_MOCK_VIRUS_SCANNER = original_value
