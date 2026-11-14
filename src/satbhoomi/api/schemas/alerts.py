"""[DRAFT] Alert action logging schemas (blueprint section 8).

Tagged DRAFT: Preliminary action log schema. Will be finalised in Task T-12 (Playbooks).
Rule 2 Compliance: Log actions strictly reflect supportive interventions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta


class AlertActionRequest(BaseModel):
    """[DRAFT] Request payload to record an officer intervention on an alert.

    Tagged DRAFT: Will be finalised in Task T-12 (Playbooks).
    """

    model_config = ConfigDict(frozen=True)

    action_type: Literal[
        "supportive_field_visit",
        "check_water_irrigation",
        "insurance_claim_help",
        "harvest_repayment_rescheduling",
    ] = Field(
        ...,
        description="Category of supportive officer intervention",
        example="supportive_field_visit",
    )
    note: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Detailed officer note documenting supportive findings and support needed",
        example=(
            "Conducted field inspection; confirmed tubewell motor repair underway, "
            "repayment stress mitigated."
        ),
    )


class AlertActionResponse(BaseModel):
    """[DRAFT] Audited confirmation of recorded officer intervention.

    Tagged DRAFT: Will be finalised in Task T-12 (Playbooks).
    """

    model_config = ConfigDict(frozen=True)

    action_id: int = Field(..., description="Unique action log entry ID", example=1)
    alert_id: int = Field(..., description="Target alert ID", example=1)
    action_type: str = Field(..., example="supportive_field_visit")
    note: str = Field(..., example="Field visit logged.")
    done_by: str = Field(
        ..., description="Identifier of officer logging action", example="Officer-001"
    )
    done_on: str = Field(
        ..., description="Action execution timestamp", example="2026-11-13T10:30:00Z"
    )
    status: str = Field(default="recorded", example="recorded")
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
