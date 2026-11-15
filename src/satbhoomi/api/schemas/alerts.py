"""[DRAFT] Alert action logging schemas (blueprint section 8).

Tagged DRAFT: Updated in Task T-11C with canon playbook actions and status tracking.
Rule 2 Compliance: Log actions strictly reflect supportive officer interventions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta

# Canonical playbook action types (no recovery pressure, no automated contact)
AlertActionType = Literal[
    "field_visit",
    "insurance_claim_help",
    "extension_support",
    "repayment_timing_discussion",
    "rescheduling_request",
    "senior_or_local_support",
    # Backward compatible aliases
    "supportive_field_visit",
    "check_water_irrigation",
    "harvest_repayment_rescheduling",
]


class AlertActionRequest(BaseModel):
    """[DRAFT] Request payload to record an officer intervention on an alert."""

    model_config = ConfigDict(frozen=True)

    action_type: AlertActionType = Field(
        ...,
        description="Category of supportive officer intervention from the fixed playbook",
        example="field_visit",
    )
    note: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description=(
            "Detailed officer note documenting supportive findings and support needed "
            "(max 500 chars, no PII/numbers)"
        ),
        example=(
            "Conducted field inspection; confirmed tubewell motor repair underway, "
            "repayment stress mitigated."
        ),
    )


class AlertActionResponse(BaseModel):
    """[DRAFT] Audited confirmation of recorded officer intervention."""

    model_config = ConfigDict(frozen=True)

    action_id: int = Field(..., description="Unique action log entry ID", example=1)
    alert_id: int = Field(..., description="Target alert ID", example=1)
    action_type: str = Field(..., example="field_visit")
    note: str = Field(..., example="Conducted field inspection; confirmed tubewell repair.")
    status_before: str | None = Field(default=None, example="open")
    status_after: str | None = Field(default=None, example="in_progress")
    done_by: str = Field(
        ..., description="Identifier of officer logging action", example="Officer-001"
    )
    done_on: str = Field(
        ..., description="Action execution timestamp", example="2026-11-15T10:30:00Z"
    )
    status: str = Field(default="recorded", example="recorded")
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
