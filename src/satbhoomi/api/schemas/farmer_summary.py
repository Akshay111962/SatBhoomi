"""[DRAFT] Farmer-facing vernacular summary schemas (blueprint section 8).

Tagged DRAFT: Preliminary vernacular summary structure. Will be finalised in Task T-12.
Includes language enums and source provenance ('template' or 'reviewed').
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta


class FarmerSummaryResponse(BaseModel):
    """[DRAFT] Vernacular plain-language credit summary for farmer communication.

    Tagged DRAFT: Will be finalised in Task T-12.
    """

    model_config = ConfigDict(frozen=True)

    assessment_id: int = Field(..., description="Parent assessment identifier", example=1)
    plot_code: str = Field(..., description="Synthetic plot code", example="PLOT-001")
    lang: Literal["en", "gu", "hi"] = Field(
        default="en",
        description="Language code: en (English), gu (Gujarati), hi (Hindi)",
        example="en",
    )
    source: Literal["template", "reviewed"] = Field(
        default="template",
        description=(
            "Text generation provenance: deterministic template or human-reviewed translation"
        ),
        example="template",
    )
    summary_text: str = Field(
        ...,
        description="Plain-language assessment explanation in selected language",
        example=(
            "Your wheat crop shows strong vegetative health with assured tubewell water. "
            "Your suggested credit limit is ₹80,000 with repayment scheduled in May after harvest."
        ),
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Bulleted highlights explaining limit basis and support needed",
        example=[
            "Vegetative health is normal.",
            "Tubewell water availability protects against winter dry spells.",
            "Crop insurance is active.",
        ],
    )
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
