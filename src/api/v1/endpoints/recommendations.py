"""
Recommendation and Human Approval API Endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_current_user, get_workflow_engine
from src.auth.jwt import TokenData
from src.domain.entities import RecommendationAction
from src.domain.events import HumanApprovedEvent
from src.schemas.recommendation import HumanApprovalRequest, RecommendationDetailResponse

router = APIRouter(tags=["Recommendations & Approvals"])


@router.get(
    "/recommendation/{id}",
    response_model=RecommendationDetailResponse,
    summary="Get Recommendation Detail",
    description="Retrieves the AI recommendation result, confidence score, and explanation for an invoice.",
)
async def get_recommendation(
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

    rec_data = checkpoint.state_data.get("recommendation_result")
    if not rec_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation for invoice '{id}' is pending or not ready yet.",
        )

    return RecommendationDetailResponse(
        id=f"rec-{id}",
        invoice_id=id,
        action=RecommendationAction(rec_data.get("action", "NEEDS_HUMAN")),
        confidence_score=rec_data.get("confidence_score", 0.0),
        explanation=rec_data.get("explanation", ""),
        reasoning_summary=rec_data.get("reasoning_summary", ""),
        created_at=checkpoint.updated_at.isoformat(),
    )


@router.post(
    "/approve",
    status_code=status.HTTP_200_OK,
    summary="Submit Human Approval / Rejection",
    description="Submits a human decision (APPROVE/REJECT) for an invoice awaiting human approval and resumes the workflow.",
)
async def approve_recommendation(
    payload: HumanApprovalRequest,
    current_user: TokenData = Depends(get_current_user),
    workflow_engine=Depends(get_workflow_engine),
):
    checkpoint = workflow_engine.get_checkpoint(payload.invoice_id)
    if not checkpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID '{payload.invoice_id}' not found.",
        )

    # Publish HumanApproved event to resume workflow engine
    approved_event = HumanApprovedEvent(
        invoice_id=payload.invoice_id,
        recommendation_id=payload.recommendation_id,
        user_id=current_user.username or "human_approver",
        action=payload.action.value,
        comments=payload.comments,
    )
    await workflow_engine.event_bus.publish(approved_event)

    return {
        "invoice_id": payload.invoice_id,
        "action_recorded": payload.action,
        "message": f"Human decision '{payload.action.value}' submitted successfully. Workflow resumed.",
    }
