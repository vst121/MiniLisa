"""
Recommendation Agent and Approval Pydantic Schemas.
"""

from pydantic import BaseModel, Field

from src.domain.entities import RecommendationAction


class RecommendationResult(BaseModel):
    action: RecommendationAction = Field(
        description="Recommended action: APPROVE, REJECT, or NEEDS_HUMAN"
    )
    confidence_score: float = Field(
        default=0.0, description="Recommendation confidence score (0.0 to 1.0)"
    )
    explanation: str = Field(
        description="Clear human-readable justification for the recommended action"
    )
    reasoning_summary: str = Field(
        description="Detailed breakdown of validation, supplier risk, and pricing findings"
    )
    flagged_issues: list[str] = Field(
        default_factory=list, description="Key issues triggering rejection or human review"
    )
    requires_human_approval: bool = Field(
        default=False, description="True if workflow must pause for human decision"
    )


class HumanApprovalRequest(BaseModel):
    invoice_id: str = Field(description="Invoice ID being approved or rejected")
    recommendation_id: str = Field(description="Recommendation ID reference")
    action: RecommendationAction = Field(
        description="Final action chosen by human: APPROVE or REJECT"
    )
    comments: str | None = Field(
        default=None, description="Optional notes or comments from the approver"
    )


class RecommendationDetailResponse(BaseModel):
    id: str
    invoice_id: str
    action: RecommendationAction
    confidence_score: float
    explanation: str
    reasoning_summary: str
    created_at: str
