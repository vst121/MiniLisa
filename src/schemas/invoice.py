"""
Invoice Pydantic Schemas for Structured Output from LLM and API endpoints.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.domain.entities import InvoiceStatus


class InvoiceItemSchema(BaseModel):
    description: str = Field(description="Description of the goods or services provided")
    quantity: float = Field(default=1.0, description="Quantity of items purchased")
    unit_price: float = Field(default=0.0, description="Price per unit of item")
    total_price: float = Field(default=0.0, description="Total price for this line item")
    item_code: Optional[str] = Field(default=None, description="SKU or product/item code if available")


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    invoice_number: Optional[str] = Field(default=None, description="Unique invoice number identifier")
    invoice_date: Optional[str] = Field(default=None, description="Invoice issue date in YYYY-MM-DD format if possible")
    due_date: Optional[str] = Field(default=None, description="Invoice due date")
    supplier_name: Optional[str] = Field(default=None, description="Name of the supplier or vendor issuing the invoice")
    supplier_tax_id: Optional[str] = Field(default=None, description="Tax ID, VAT number, or EIN of the supplier")
    supplier_address: Optional[str] = Field(default=None, description="Address of the supplier")
    customer_name: Optional[str] = Field(default=None, description="Billed customer name")
    total_amount: float = Field(default=0.0, description="Grand total amount billed on invoice including tax")
    vat_amount: float = Field(default=0.0, description="Total VAT or sales tax amount")
    subtotal: float = Field(default=0.0, description="Total before taxes")
    currency: str = Field(default="USD", description="Currency ISO code (USD, EUR, GBP, etc.)")
    payment_terms: Optional[str] = Field(default=None, description="Payment terms like Net 30, Due on Receipt")
    items: List[InvoiceItemSchema] = Field(default_factory=list, description="Extracted line items from invoice")


class InvoiceUploadResponse(BaseModel):
    invoice_id: str
    file_name: str
    status: InvoiceStatus
    message: str


class InvoiceDetailResponse(BaseModel):
    id: str
    file_name: str
    status: InvoiceStatus
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    total_amount: float
    vat_amount: float
    currency: str
    items: List[InvoiceItemSchema]
    created_at: datetime
    updated_at: datetime
