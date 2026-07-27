"""Deterministic adapters shared by tests; they never make network calls."""

from typing import Any, TypeVar

from pydantic import BaseModel

from src.schemas.invoice import InvoiceExtraction, InvoiceItemSchema

T = TypeVar("T", bound=BaseModel)


class DeterministicLLMClient:
    """Minimal LLM port fake returning realistic invoice extraction data."""

    async def generate_structured(self, _messages: list[dict[str, str]], response_schema: type[T]) -> T:
        if response_schema is InvoiceExtraction:
            return InvoiceExtraction(
                invoice_number="INV-1001",
                supplier_name="Acme Industrial Supplies",
                supplier_tax_id="TAX-VALID-100",
                subtotal=300.0,
                vat_amount=50.0,
                total_amount=350.0,
                currency="USD",
                items=[
                    InvoiceItemSchema(
                        description="Widget A",
                        quantity=2,
                        unit_price=150.0,
                        total_price=300.0,
                    )
                ],
            )  # type: ignore[return-value]
        return response_schema.model_construct()  # type: ignore[return-value]
