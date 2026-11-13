"""Public Pydantic schema models for SatBhoomi API contract v1 (blueprint section 8)."""

from satbhoomi.api.schemas.alerts import AlertActionRequest, AlertActionResponse
from satbhoomi.api.schemas.assessments import (
    AssessmentCreateRequest,
    AssessmentResponse,
    DraftLoanSuggestion,
    ReasonItem,
)
from satbhoomi.api.schemas.auth import LoginRequest, TokenResponse
from satbhoomi.api.schemas.common import ErrorDetail, ErrorResponse, ResponseMeta
from satbhoomi.api.schemas.farmer_summary import FarmerSummaryResponse
from satbhoomi.api.schemas.monitoring import AlertSummary, PlotMonitoringResponse, TimelinePoint
from satbhoomi.api.schemas.plots import PlotCreateRequest, PlotListResponse, PlotResponse
from satbhoomi.api.schemas.relief import ReliefReportResponse
from satbhoomi.api.schemas.what_if import WhatIfRequest, WhatIfResponse

__all__ = [
    "AlertActionRequest",
    "AlertActionResponse",
    "AlertSummary",
    "AssessmentCreateRequest",
    "AssessmentResponse",
    "DraftLoanSuggestion",
    "ErrorDetail",
    "ErrorResponse",
    "FarmerSummaryResponse",
    "LoginRequest",
    "PlotCreateRequest",
    "PlotListResponse",
    "PlotMonitoringResponse",
    "PlotResponse",
    "ReasonItem",
    "ReliefReportResponse",
    "ResponseMeta",
    "TimelinePoint",
    "TokenResponse",
    "WhatIfRequest",
    "WhatIfResponse",
]
