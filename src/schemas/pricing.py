"""
Pricing & Anomaly Agent Pydantic Schemas.
"""

from pydantic import BaseModel, Field


class PriceAnomaly(BaseModel):
    item_description: str = Field(description="Description of line item with price variation")
    current_unit_price: float = Field(description="Unit price on current invoice")
    historical_avg_price: float = Field(
        description="Historical average price for this item/category"
    )
    percentage_change: float = Field(description="Percentage price increase or decrease")
    is_anomaly: bool = Field(description="True if change exceeds risk threshold (e.g. >15%)")
    explanation: str = Field(description="Explanation of pricing anomaly analysis")


class PricingComparison(BaseModel):
    has_pricing_anomalies: bool = Field(
        description="True if any line item price anomaly was detected"
    )
    max_price_variance_pct: float = Field(
        default=0.0, description="Highest percentage variance detected"
    )
    anomalies: list[PriceAnomaly] = Field(
        default_factory=list, description="List of detected line item price anomalies"
    )
    pricing_score: float = Field(
        default=100.0, description="Pricing score from 0 (extreme anomaly) to 100 (normal)"
    )
    summary: str = Field(
        default="", description="Summary of pricing comparison against historical POs/invoices"
    )
