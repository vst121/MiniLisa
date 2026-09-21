"""
Supplier Intelligence Pydantic Schemas.
"""

from pydantic import BaseModel, Field

from src.domain.entities import RiskLevel


class PastPurchaseSummary(BaseModel):
    invoice_number: str
    date: str
    total_amount: float
    status: str


class SupplierRisk(BaseModel):
    supplier_found: bool = Field(description="Whether the supplier exists in database")
    supplier_id: str | None = Field(default=None, description="Database ID of matching supplier")
    supplier_name: str = Field(description="Matched or identified supplier name")
    tax_id: str | None = Field(default=None, description="Tax ID or VAT number")
    risk_score: float = Field(
        default=0.0, description="Risk score from 0.0 (safe) to 100.0 (high risk)"
    )
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Categorized risk level")
    rating: float = Field(default=5.0, description="Supplier quality rating (1.0 to 5.0)")
    payment_history_status: str = Field(
        default="GOOD", description="Payment history flag e.g. GOOD, DELINQUENT, NEW"
    )
    past_purchases_count: int = Field(default=0, description="Total past purchase invoices on file")
    risk_factors: list[str] = Field(
        default_factory=list, description="List of identified risk factors"
    )
    summary: str = Field(
        default="", description="Executive summary of supplier intelligence assessment"
    )
