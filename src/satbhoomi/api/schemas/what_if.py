"""[STABLE] What-if simulator request and response schemas (blueprint section 8).

Matches the real WhatIfResult from src/satbhoomi/risk/what_if.py (T-08).
Rule 6 Compliance: Every simulation output must carry estimate_label='estimate'
and the causation disclaimer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta
from satbhoomi.risk.loan_suggestions import LimitBand
from satbhoomi.risk.scoring import FIXED_RELIABILITY_NOTE
from satbhoomi.risk.what_if import DISCLAIMER_WHAT_IF


class WhatIfRequest(BaseModel):
    """[STABLE] Payload to project risk score changes under a controllable mitigation."""

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
    """[STABLE] Simulation projection result mirroring WhatIfResult (T-08).

    Provides comparative risk score, risk band, and indicative credit limit
    projections under hypothetical farm management interventions.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "invalid_input"] = Field(
        default="ok",
        description="Simulation status: 'ok' or 'invalid_input'",
        example="ok",
    )
    assessment_id: int | None = Field(
        default=None,
        description="Parent assessment identifier if linked to a persisted evaluation",
        example=1,
    )
    plot_id: int | None = Field(
        default=None,
        description="Plot reference identifier",
        example=1,
    )
    plot_code: str = Field(
        default="PLOT-001",
        description="Synthetic plot code",
        example="PLOT-001",
    )
    season: str = Field(
        default="2024-25",
        description="Evaluated cropping season",
        example="2024-25",
    )
    changed_input: Literal["insured", "irrigation", "supplementary_irrigation"] = Field(
        ...,
        description="Intervention attribute evaluated",
        example="insured",
    )
    old_value: str = Field(..., description="Baseline value before intervention", example="0")
    new_value: str = Field(..., description="Simulated value after intervention", example="1")

    old_score: int = Field(
        ...,
        description="Baseline risk score before intervention",
        example=55,
    )
    new_score: int = Field(
        ...,
        description="Projected risk score after simulated intervention",
        example=45,
    )
    score_delta: int = Field(
        ...,
        description="Score difference (new_score - old_score; negative indicates lower risk)",
        example=-10,
    )
    old_band: Literal["low", "medium", "high"] = Field(
        ...,
        description="Baseline risk band",
        example="medium",
    )
    new_band: Literal["low", "medium", "high"] = Field(
        ...,
        description="Projected risk band under mitigation",
        example="medium",
    )

    old_limit_band: LimitBand | None = Field(
        default=None,
        description="Indicative loan limit band before intervention",
    )
    new_limit_band: LimitBand | None = Field(
        default=None,
        description="Indicative loan limit band after intervention",
    )

    # Mandatory Rule 6 Guardrails
    estimate_label: Literal["estimate"] = Field(
        default="estimate",
        description="Mandatory label identifying output as a model estimate, not causation proof",
        example="estimate",
    )
    effect_basis: Literal["scorer_input", "scenario_assumption", "not_modelled"] = Field(
        default="scorer_input",
        description=(
            "Basis of the simulated effect: 'scorer_input' (direct feature change), "
            "'scenario_assumption' (structural agronomic heuristic), or "
            "'not_modelled' (input has zero effect on current active model)"
        ),
        example="scorer_input",
    )
    assumption: str | None = Field(
        default=None,
        description="Explicit agronomic or economic assumption applied if scenario_assumption",
        example=None,
    )
    rationale: str = Field(
        ...,
        description="Plain-language economic explanation of the simulation effect",
        example=(
            "Crop insurance buffers financial loss; under rule policy, mandatory "
            "haircut is mitigated."
        ),
    )
    disclaimer: str = Field(
        default=DISCLAIMER_WHAT_IF,
        description="Mandatory statistical sensitivity disclaimer",
    )
    reliability_note: str = Field(
        default=FIXED_RELIABILITY_NOTE,
        description="Mandatory validation status disclosure",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Diagnostic simulation execution notes",
    )
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
