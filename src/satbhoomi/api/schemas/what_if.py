"""[DRAFT] What-if simulator request and response schemas (blueprint section 8).

Tagged DRAFT. Subject to refinement and expansion in Task T-08.
Rule 6 Compliance: Every simulation output must carry estimate_label='estimate'
and the causation disclaimer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta


class WhatIfRequest(BaseModel):
    """[DRAFT] Payload to project risk score changes under a controllable mitigation."""

    model_config = ConfigDict(frozen=True)

    changed_input: Literal["insured", "irrigation", "supplementary_irrigation"] = Field(
        ...,
        description="Controllable intervention attribute to simulate",
        example="insured",
    )
    new_value: str = Field(
        ...,
        description="Hypothetical value to apply (e.g. '1' or 'tube_well')",
        example="1",
    )


class WhatIfResponse(BaseModel):
    """[DRAFT] Simulation projection result for loan officer review.

    Tagged DRAFT: Will be refined in Task T-08.
    """

    model_config = ConfigDict(frozen=True)

    assessment_id: int = Field(..., description="Parent assessment ID", example=1)
    plot_id: int = Field(..., description="Plot identifier", example=1)
    changed_input: str = Field(
        ..., description="Intervention attribute evaluated", example="insured"
    )
    old_value: str = Field(..., description="Baseline value before intervention", example="0")
    new_value: str = Field(..., description="Simulated value after intervention", example="1")

    original_score: int | None = Field(
        ...,
        description="Original baseline risk score",
        example=55,
    )
    simulated_score: int | None = Field(
        ...,
        description="Projected risk score under the simulated mitigation",
        example=45,
    )
    original_band: Literal["low", "medium", "high"] | None = Field(
        ...,
        description="Baseline risk band",
        example="medium",
    )
    simulated_band: Literal["low", "medium", "high"] | None = Field(
        ...,
        description="Projected risk band",
        example="medium",
    )
    score_delta: int | None = Field(
        ...,
        description="Point change in risk score (negative indicates risk reduction)",
        example=-10,
    )

    # Mandatory Rule 6 Guardrails
    estimate_label: Literal["estimate"] = Field(
        default="estimate",
        description="Mandatory label identifying output as a model estimate, not causation proof",
        example="estimate",
    )
    causation_disclaimer: str = Field(
        default=(
            "What-if simulations show model sensitivity under prospective mitigations; "
            "they do not prove causation or guarantee crop outcomes."
        ),
        description="Mandatory statistical disclaimer",
    )
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
