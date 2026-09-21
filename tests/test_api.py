"""API integration tests using application dependency overrides only."""

import asyncio
from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_db_session, get_workflow_engine
from src.auth.jwt import create_access_token
from src.config.settings import settings
from src.events.event_bus import InMemoryEventBus
from src.infrastructure.pdf_parser import ExtractedDocument
from src.main import app
from src.workflows.workflow_engine import WorkflowEngine
from tests.fakes import DeterministicLLMClient


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Provide a fully isolated API client without Postgres or Redis."""
    session = AsyncMock()
    workflow_engine = WorkflowEngine(event_bus=InMemoryEventBus())
    workflow_engine.invoice_agent.llm_client = DeterministicLLMClient()
    original_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = tmp_path / "uploads"
    asyncio.run(workflow_engine.register_subscribers())

    async def override_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_workflow_engine] = lambda: workflow_engine
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
    settings.UPLOAD_DIR = original_upload_dir


def test_health_endpoint(client: TestClient):
    response = client.get("/api/v1/health", headers={"X-Correlation-ID": "correlation-test-123"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "Procurement AI Assistant"
    assert response.headers["X-Correlation-ID"] == "correlation-test-123"


def test_api_upload_flow(client: TestClient):
    auth_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': 'procurement_manager', 'role': 'admin'})}"
    }
    pdf_content = b"%PDF-1.4 Header\nINVOICE #99001\nSupplier: Acme Industrial Supplies\nTax ID: TAX-VALID-100\nTotal: 350.00"
    file_payload = {"file": ("test_invoice.pdf", BytesIO(pdf_content), "application/pdf")}

    parsed_document = ExtractedDocument(
        raw_text="INVOICE #99001\nSupplier: Acme\nTotal: 350.00",
        page_count=1,
        tables=[],
    )
    with patch(
        "src.workflows.workflow_engine.DocumentParser.parse_pdf", return_value=parsed_document
    ):
        upload_res = client.post("/api/v1/upload", files=file_payload, headers=auth_headers)
    assert upload_res.status_code == 202
    data = upload_res.json()
    invoice_id = data["invoice_id"]
    assert invoice_id is not None
    assert data["status"] == "UPLOADED"

    # GET /invoice/{id}
    inv_res = client.get(f"/api/v1/invoice/{invoice_id}", headers=auth_headers)
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    assert inv_data["id"] == invoice_id

    # GET /recommendation/{id}
    rec_res = client.get(f"/api/v1/recommendation/{invoice_id}", headers=auth_headers)
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["invoice_id"] == invoice_id

    # POST /approve
    approve_res = client.post(
        "/api/v1/approve",
        json={
            "invoice_id": invoice_id,
            "recommendation_id": f"rec-{invoice_id}",
            "action": "APPROVE",
            "comments": "Approved by senior architect",
        },
        headers=auth_headers,
    )
    assert approve_res.status_code == 200
    approve_data = approve_res.json()
    assert approve_data["invoice_id"] == invoice_id


def test_api_rejects_non_pdf_upload(client: TestClient):
    auth_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': 'procurement_manager', 'role': 'admin'})}"
    }
    file_payload = {"file": ("invoice.txt", BytesIO(b"not a pdf"), "text/plain")}

    response = client.post("/api/v1/upload", files=file_payload, headers=auth_headers)

    assert response.status_code == 400
    assert "Invalid file extension" in response.json()["detail"]


def test_api_rejects_invalid_bearer_token(client: TestClient):
    response = client.get(
        "/api/v1/invoice/does-not-matter",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )

    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


def test_api_sanitizes_uploaded_filename(client: TestClient):
    auth_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': 'procurement_manager', 'role': 'admin'})}"
    }
    pdf_content = b"%PDF-1.4 Header\nINVOICE #99002\nTotal: 100.00"
    file_payload = {"file": ("..\\outside\\invoice.pdf", BytesIO(pdf_content), "application/pdf")}

    parsed_document = ExtractedDocument(
        raw_text="INVOICE #99002\nTotal: 100.00", page_count=1, tables=[]
    )
    with patch(
        "src.workflows.workflow_engine.DocumentParser.parse_pdf", return_value=parsed_document
    ):
        response = client.post("/api/v1/upload", files=file_payload, headers=auth_headers)

    assert response.status_code == 202
    assert response.json()["file_name"] == "invoice.pdf"
