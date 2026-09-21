"""
Invoice Pydantic Schemas for Structured Output from LLM and API endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.domain.entities import InvoiceStatus


class InvoiceItemSchema(BaseModel):
    description: str = Field(description="Description of the goods or services provided")
    quantity: float = Field(default=1.0, description="Quantity of items purchased")
    unit_price: float = Field(default=0.0, description="Price per unit of item")
    total_price: float = Field(default=0.0, description="Total price for this line item")
    item_code: str | None = Field(default=None, description="SKU or product/item code if available")


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    invoice_number: str | None = Field(default=None, description="Unique invoice number identifier")
    invoice_date: str | None = Field(
        default=None, description="Invoice issue date in YYYY-MM-DD format if possible"
    )
    due_date: str | None = Field(default=None, description="Invoice due date")
    supplier_name: str | None = Field(
        default=None, description="Name of the supplier or vendor issuing the invoice"
    )
    supplier_tax_id: str | None = Field(
        default=None, description="Tax ID, VAT number, or EIN of the supplier"
    )
    supplier_address: str | None = Field(default=None, description="Address of the supplier")
    customer_name: str | None = Field(default=None, description="Billed customer name")
    total_amount: float = Field(
        default=0.0, description="Grand total amount billed on invoice including tax"
    )
    vat_amount: float = Field(default=0.0, description="Total VAT or sales tax amount")
    subtotal: float = Field(default=0.0, description="Total before taxes")
    currency: str = Field(default="USD", description="Currency ISO code (USD, EUR, GBP, etc.)")
    payment_terms: str | None = Field(
        default=None, description="Payment terms like Net 30, Due on Receipt"
    )
    items: list[InvoiceItemSchema] = Field(
        default_factory=list, description="Extracted line items from invoice"
    )


class InvoiceUploadResponse(BaseModel):
    invoice_id: str
    file_name: str
    status: InvoiceStatus
    message: str


class InvoiceDetailResponse(BaseModel):
    id: str
    file_name: str
    status: InvoiceStatus
    invoice_number: str | None = None
    invoice_date: str | None = None
    supplier_id: str | None = None
    supplier_name: str | None = None
    total_amount: float
    vat_amount: float
    currency: str
    items: list[InvoiceItemSchema]
    created_at: datetime
    updated_at: datetime
