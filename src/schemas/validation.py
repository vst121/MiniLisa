"""
Invoice Validation Pydantic Schemas.
"""

from pydantic import BaseModel, Field


class ValidationErrorItem(BaseModel):
    field_name: str = Field(description="Name of the invalid or missing field")
    error_type: str = Field(
        description="Type of error e.g. MISSING_FIELD, TOTAL_MISMATCH, VAT_CALCULATION_ERROR, DUPLICATE_INVOICE"
    )
    message: str = Field(description="Human readable explanation of validation error")
    severity: str = Field(default="HIGH", description="Severity level: LOW, MEDIUM, HIGH, CRITICAL")


class ValidationResult(BaseModel):
    is_valid: bool = Field(description="Whether the invoice passed all validation checks")
    missing_fields: list[str] = Field(
        default_factory=list, description="List of required fields missing from invoice"
    )
    math_correct: bool = Field(
        default=True, description="True if subtotal + vat equals total_amount"
    )
    vat_correct: bool = Field(default=True, description="True if VAT calculation is consistent")
    is_duplicate: bool = Field(
        default=False, description="True if this invoice number already exists for supplier"
    )
    errors: list[ValidationErrorItem] = Field(
        default_factory=list, description="Detailed validation error items"
    )
    confidence_score: float = Field(
        default=1.0, description="Validation agent confidence score (0.0 to 1.0)"
    )
