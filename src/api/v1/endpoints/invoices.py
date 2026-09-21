"""
Invoice API Endpoints: Upload and Retrieval.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db_session, get_workflow_engine
from src.auth.jwt import TokenData
from src.auth.security import validate_upload_file
from src.config.settings import settings
from src.domain.entities import InvoiceStatus
from src.domain.events import InvoiceUploadedEvent
from src.models.invoice import InvoiceModel
from src.repositories.outbox_repository import OutboxRepository
from src.schemas.invoice import InvoiceDetailResponse, InvoiceItemSchema, InvoiceUploadResponse

router = APIRouter(tags=["Invoices"])


@router.post(
    "/upload",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Supplier Invoice PDF",
    description="Uploads a PDF invoice, performs security validation, saves to storage, and initiates the event-driven AI workflow.",
)
async def upload_invoice(
    request: Request,
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    workflow_engine=Depends(get_workflow_engine),
):
    # Security validation & scan
    file_bytes = await validate_upload_file(file)

    invoice_id = str(uuid.uuid4())
    filename = Path(file.filename or f"invoice_{invoice_id[:8]}.pdf").name

    # Save file to upload directory
    settings.create_upload_dir()
    saved_path = settings.UPLOAD_DIR / f"{invoice_id}_{filename}"
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    # Create initial database record
    db_invoice = InvoiceModel(
        id=invoice_id,
        file_name=filename,
        file_path=str(saved_path),
        status=InvoiceStatus.UPLOADED.value,
        total_amount=0.0,
        vat_amount=0.0,
    )
    session.add(db_invoice)
    upload_event = InvoiceUploadedEvent(
        invoice_id=invoice_id,
        file_path=str(saved_path),
        file_name=filename,
        correlation_id=request.state.correlation_id,
    )
    outbox_record = await OutboxRepository(session).enqueue(
        {
            "event_id": upload_event.event_id,
            "event_type": upload_event.event_type,
            "correlation_id": upload_event.correlation_id,
            "payload": upload_event.model_dump(mode="json"),
        }
    )
    await session.commit()

    # Publish after the invoice and outbox record are committed.
    await workflow_engine.event_bus.publish(upload_event)
    await OutboxRepository(session).mark_published(outbox_record)
    await session.commit()

    return InvoiceUploadResponse(
        invoice_id=invoice_id,
        file_name=filename,
        status=InvoiceStatus.UPLOADED,
        message="Invoice uploaded successfully. AI processing pipeline started.",
    )


@router.get(
    "/invoice/{id}",
    response_model=InvoiceDetailResponse,
    summary="Get Invoice Detail",
    description="Retrieves the detailed status, extracted fields, and line items for an invoice by ID.",
)
async def get_invoice(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    workflow_engine=Depends(get_workflow_engine),
):
    checkpoint = workflow_engine.get_checkpoint(id)
    if not checkpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID '{id}' not found.",
        )

    extraction = checkpoint.state_data.get("invoice_extraction", {})
    items_raw = extraction.get("items", [])
    items = [InvoiceItemSchema(**it) for it in items_raw]

    return InvoiceDetailResponse(
        id=id,
        file_name=f"invoice_{id[:8]}.pdf",
        status=checkpoint.status,
        invoice_number=extraction.get("invoice_number"),
        invoice_date=extraction.get("invoice_date"),
        supplier_id=checkpoint.state_data.get("supplier_risk", {}).get("supplier_id"),
        supplier_name=extraction.get("supplier_name"),
        total_amount=extraction.get("total_amount", 0.0),
        vat_amount=extraction.get("vat_amount", 0.0),
        currency=extraction.get("currency", "USD"),
        items=items,
        created_at=checkpoint.updated_at,
        updated_at=checkpoint.updated_at,
    )
