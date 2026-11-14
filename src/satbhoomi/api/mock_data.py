"""Deterministic synthetic sample datasets for Mock API mode (blueprint section 8).

Strictly tagged as synthetic data. Zero PII, zero real farmer records.
Rule 2 Compliance: All text describes farm/repayment stress and support needed.
"""

from __future__ import annotations

from satbhoomi.api.schemas.assessments import (
    AssessmentResponse,
    LoanSuggestionResponse,
    ReasonItem,
)
from satbhoomi.api.schemas.common import ResponseMeta
from satbhoomi.api.schemas.farmer_summary import FarmerSummaryResponse
from satbhoomi.api.schemas.monitoring import AlertSummary, PlotMonitoringResponse, TimelinePoint
from satbhoomi.api.schemas.plots import PlotResponse
from satbhoomi.api.schemas.relief import ReliefReportResponse
from satbhoomi.risk.loan_suggestions import (
    DISCLAIMER_LOAN_SUGGESTION,
    LimitBand,
    RepaymentSchedule,
)
from satbhoomi.risk.scoring import (
    FIXED_INTERPRETATION,
    FIXED_RELIABILITY_NOTE,
    RULES_BASELINE_VERSION,
)

FAKE_MOCK_TOKEN = "mock-officer-token-xyz"
SYNTHETIC_META = ResponseMeta(synthetic=True, version="0.2.0")

# ---------------------------------------------------------------------------
# Synthetic Plots
# ---------------------------------------------------------------------------
MOCK_PLOTS: list[PlotResponse] = [
    PlotResponse(
        id=1,
        plot_code="PLOT-001",
        farmer_id=1,
        farmer_display_name="Farmer-001",
        district="Anand",
        village="Boriavi",
        crop="wheat",
        area_acre=2.5,
        lat=22.5645,
        lon=72.9289,
        irrigation="tube_well",
        insured=1,
        created_at="2026-11-01T09:00:00Z",
        meta=SYNTHETIC_META,
    ),
    PlotResponse(
        id=2,
        plot_code="PLOT-002",
        farmer_id=2,
        farmer_display_name="Farmer-002",
        district="Anand",
        village="Mogar",
        crop="wheat",
        area_acre=7.0,  # Large plot exceeding collateral-free cap
        lat=22.5412,
        lon=72.9610,
        irrigation="canal",
        insured=0,
        created_at="2026-11-02T10:15:00Z",
        meta=SYNTHETIC_META,
    ),
    PlotResponse(
        id=3,
        plot_code="PLOT-003",
        farmer_id=3,
        farmer_display_name="Farmer-003",
        district="Anand",
        village="Napad",
        crop="wheat",
        area_acre=1.8,
        lat=22.4920,
        lon=72.8850,
        irrigation="rainfed",
        insured=0,
        created_at="2026-11-03T11:30:00Z",
        meta=SYNTHETIC_META,
    ),
    PlotResponse(
        id=4,
        plot_code="PLOT-004",
        farmer_id=4,
        farmer_display_name="Farmer-004",
        district="Anand",
        village="Tarapur",
        crop="wheat",
        area_acre=3.2,
        lat=22.4830,
        lon=72.6520,
        irrigation="tube_well",
        insured=1,
        created_at="2026-11-04T14:00:00Z",
        meta=SYNTHETIC_META,
    ),
    PlotResponse(
        id=5,
        plot_code="PLOT-005",
        farmer_id=5,
        farmer_display_name="Farmer-005",
        district="Anand",
        village="Petlad",
        crop="wheat",
        area_acre=2.0,
        lat=22.4710,
        lon=72.8020,
        irrigation="tube_well",
        insured=1,
        created_at="2026-11-05T16:45:00Z",
        meta=SYNTHETIC_META,
    ),
]

# ---------------------------------------------------------------------------
# Synthetic Assessments
# ---------------------------------------------------------------------------
MOCK_ASSESSMENTS: dict[int, AssessmentResponse] = {
    1: AssessmentResponse(
        id=1,
        plot_id=1,
        plot_code="PLOT-001",
        season="2024-25",
        status="ok",
        score=18,
        band="low",
        reasons=[
            ReasonItem(
                feature_name="ndvi_trend_pre_cutoff",
                text="Vegetative canopy vigor expanded steadily through January cut-off.",
            ),
            ReasonItem(
                feature_name="rain_pre_cutoff_deficit_pct",
                text="Winter precipitation was supplemented by assured tubewell irrigation.",
            ),
            ReasonItem(
                feature_name="prev_season_ndvi_peak",
                text="Historical peak vegetative resilience was sustained across previous cycles.",
            ),
        ],
        protective_factor=(
            "Assured tubewell irrigation buffers plot from winter precipitation deficit."
        ),
        model_version=RULES_BASELINE_VERSION,
        scorer="rules_baseline",
        cutoff_date="January 31",
        data_warnings=[],
        interpretation=FIXED_INTERPRETATION,
        reliability_note=FIXED_RELIABILITY_NOTE,
        loan_suggestion=LoanSuggestionResponse(
            status="ok",
            plot_code="PLOT-001",
            season="2024-25",
            crop="wheat",
            area_acre=2.5,
            irrigation="tube_well",
            risk_band="low",
            risk_score=18,
            limit_band=LimitBand(
                min_amount_inr=72000,
                max_amount_inr=80000,
                scale_of_finance_per_acre_inr=32000,
                gross_scale_limit_inr=80000,
                collateral_free_cap_applied=False,
                haircut_percentage_range="0%–10%",
            ),
            repayment_schedule=RepaymentSchedule(
                repayment_month="May",
                schedule_type="bullet_post_harvest",
                harvest_window="March–April",
                marketing_window="April–May",
                rationale=(
                    "Bullet repayment scheduled in May aligned with peak wheat mandi arrivals."
                ),
            ),
            insurance_required=False,
            insurance_note="Low risk: crop insurance optional under standard KCC guidelines.",
            disclaimer=DISCLAIMER_LOAN_SUGGESTION,
            notes=["Scale of finance ₹32,000/acre applied for irrigated wheat in Anand district."],
        ),
        created_at="2026-11-13T10:00:00Z",
        meta=SYNTHETIC_META,
    ),
    2: AssessmentResponse(
        id=2,
        plot_id=2,
        plot_code="PLOT-002",
        season="2024-25",
        status="ok",
        score=45,
        band="medium",
        reasons=[
            ReasonItem(
                feature_name="ndvi_trend_pre_cutoff",
                text="Vegetation vigor exhibited slight mid-season canopy drag.",
            ),
            ReasonItem(
                feature_name="rain_pre_cutoff_deficit_pct",
                text="Moderate winter rainfall deficit observed during vegetative growth.",
            ),
            ReasonItem(
                feature_name="insured",
                text="Uninsured plot status increases farm repayment stress risk.",
            ),
        ],
        protective_factor="Canal irrigation network provides supplemental water supply.",
        model_version=RULES_BASELINE_VERSION,
        scorer="rules_baseline",
        cutoff_date="January 31",
        data_warnings=[],
        interpretation=FIXED_INTERPRETATION,
        reliability_note=FIXED_RELIABILITY_NOTE,
        loan_suggestion=LoanSuggestionResponse(
            status="ok",
            plot_code="PLOT-002",
            season="2024-25",
            crop="wheat",
            area_acre=7.0,
            irrigation="canal",
            risk_band="medium",
            risk_score=45,
            limit_band=LimitBand(
                min_amount_inr=130000,
                max_amount_inr=160000,
                scale_of_finance_per_acre_inr=32000,
                gross_scale_limit_inr=224000,  # 7.0 * 32,000 = 224,000 > 2,00,000
                collateral_free_cap_applied=True,
                haircut_percentage_range="20%–35%",
            ),
            repayment_schedule=RepaymentSchedule(
                repayment_month="May",
                schedule_type="bullet_post_harvest",
                harvest_window="March–April",
                marketing_window="April–May",
                rationale=(
                    "Bullet repayment scheduled in May aligned with post-harvest cash realization."
                ),
            ),
            insurance_required=True,
            insurance_note="Medium risk: PMFBY crop insurance mandatory to safeguard repayment.",
            disclaimer=DISCLAIMER_LOAN_SUGGESTION,
            notes=[
                "Gross scale limit ₹2,24,000 capped at RBI ₹2,00,000 collateral-free threshold.",
                "Haircut range 20%–35% applied for medium risk band.",
            ],
        ),
        created_at="2026-11-13T10:15:00Z",
        meta=SYNTHETIC_META,
    ),
    3: AssessmentResponse(
        id=3,
        plot_id=3,
        plot_code="PLOT-003",
        season="2024-25",
        status="ok",
        score=85,
        band="high",
        reasons=[
            ReasonItem(
                feature_name="ndvi_trend_pre_cutoff",
                text="Severe vegetative drag and canopy stunting observed on rainfed plot.",
            ),
            ReasonItem(
                feature_name="rain_pre_cutoff_deficit_pct",
                text=(
                    "Severe winter moisture deficit without irrigation buffering indicates "
                    "support needed."
                ),
            ),
            ReasonItem(
                feature_name="insured",
                text="Absence of crop insurance elevates potential repayment stress.",
            ),
        ],
        protective_factor=None,
        model_version=RULES_BASELINE_VERSION,
        scorer="rules_baseline",
        cutoff_date="January 31",
        data_warnings=[],
        interpretation=FIXED_INTERPRETATION,
        reliability_note=FIXED_RELIABILITY_NOTE,
        loan_suggestion=LoanSuggestionResponse(
            status="ok",
            plot_code="PLOT-003",
            season="2024-25",
            crop="wheat",
            area_acre=1.8,
            irrigation="rainfed",
            risk_band="high",
            risk_score=85,
            limit_band=LimitBand(
                min_amount_inr=15840,
                max_amount_inr=19800,
                scale_of_finance_per_acre_inr=22000,
                gross_scale_limit_inr=39600,
                collateral_free_cap_applied=False,
                haircut_percentage_range="50%–60%",
            ),
            repayment_schedule=RepaymentSchedule(
                repayment_month="May",
                schedule_type="bullet_post_harvest",
                harvest_window="March–April",
                marketing_window="April–May",
                rationale="Bullet repayment scheduled in May aligned with wheat harvest window.",
            ),
            insurance_required=True,
            insurance_note="High risk: PMFBY crop insurance mandatory for loan disbursement.",
            disclaimer=DISCLAIMER_LOAN_SUGGESTION,
            notes=[
                "Scale of finance ₹22,000/acre applied for rainfed wheat.",
                "Conservative 50%–60% haircut applied to prevent over-indebtedness.",
            ],
        ),
        created_at="2026-11-13T10:30:00Z",
        meta=SYNTHETIC_META,
    ),
    4: AssessmentResponse(
        id=4,
        plot_id=4,
        plot_code="PLOT-004",
        season="2024-25",
        status="insufficient_data",
        score=None,
        band=None,
        reasons=[
            ReasonItem(
                feature_name="ndvi_early",
                text="Early vegetative observation unavailable due to persistent cloud cover.",
            ),
            ReasonItem(
                feature_name="ndvi_pre_cutoff_mean",
                text="Fewer than 2 clear observations before January 31 cut-off barrier.",
            ),
            ReasonItem(
                feature_name="past_stressed_seasons_count",
                text="Prior historical track record unavailable for new plot.",
            ),
        ],
        protective_factor=None,
        model_version=RULES_BASELINE_VERSION,
        scorer="rules_baseline",
        cutoff_date="January 31",
        data_warnings=[
            "Cloud cover exceeded 80% on multiple satellite passes.",
            "Recorded as data gap without guessing or imputation.",
        ],
        insufficient_data_reason=(
            "Insufficient clear satellite observations during early tillering "
            "window (< 2 valid scenes)."
        ),
        interpretation=FIXED_INTERPRETATION,
        reliability_note=FIXED_RELIABILITY_NOTE,
        loan_suggestion=LoanSuggestionResponse(
            status="manual_appraisal_required",
            plot_code="PLOT-004",
            season="2024-25",
            crop="wheat",
            area_acre=3.2,
            irrigation="tube_well",
            risk_band=None,
            risk_score=None,
            limit_band=None,
            repayment_schedule=None,
            insurance_required=True,
            insurance_note="Manual appraisal required: crop insurance enrollment must be verified.",
            disclaimer=DISCLAIMER_LOAN_SUGGESTION,
            notes=[
                "Score not evaluable due to satellite data gap. Manual physical appraisal required."
            ],
        ),
        created_at="2026-11-13T10:45:00Z",
        meta=SYNTHETIC_META,
    ),
    5: AssessmentResponse(
        id=5,
        plot_id=5,
        plot_code="PLOT-005",
        season="2024-25",
        status="ok",
        score=28,
        band="low",
        reasons=[
            ReasonItem(
                feature_name="ndvi_trend_pre_cutoff",
                text="Normal vegetative development following late December irrigation.",
            ),
            ReasonItem(
                feature_name="rain_pre_cutoff_deficit_pct",
                text="Dry winter conditions buffered by private tubewell.",
            ),
            ReasonItem(
                feature_name="past_stressed_seasons_count",
                text="Zero past stressed seasons on historical record.",
            ),
        ],
        protective_factor="Tubewell infrastructure mitigates winter rainfall shortage.",
        model_version=RULES_BASELINE_VERSION,
        scorer="rules_baseline",
        cutoff_date="January 31",
        data_warnings=["Single scene cloud gap on Jan 10; clear scene recorded on Jan 15."],
        interpretation=FIXED_INTERPRETATION,
        reliability_note=FIXED_RELIABILITY_NOTE,
        loan_suggestion=LoanSuggestionResponse(
            status="ok",
            plot_code="PLOT-005",
            season="2024-25",
            crop="wheat",
            area_acre=2.0,
            irrigation="tube_well",
            risk_band="low",
            risk_score=28,
            limit_band=LimitBand(
                min_amount_inr=57600,
                max_amount_inr=64000,
                scale_of_finance_per_acre_inr=32000,
                gross_scale_limit_inr=64000,
                collateral_free_cap_applied=False,
                haircut_percentage_range="0%–10%",
            ),
            repayment_schedule=RepaymentSchedule(
                repayment_month="May",
                schedule_type="bullet_post_harvest",
                harvest_window="March–April",
                marketing_window="April–May",
                rationale="Bullet repayment in May aligned with mandi sales.",
            ),
            insurance_required=False,
            insurance_note="Low risk: crop insurance optional under standard guidelines.",
            disclaimer=DISCLAIMER_LOAN_SUGGESTION,
            notes=["Standard irrigated Scale of Finance applied."],
        ),
        created_at="2026-11-13T11:00:00Z",
        meta=SYNTHETIC_META,
    ),
}

# ---------------------------------------------------------------------------
# Synthetic Monitoring & Timeline
# ---------------------------------------------------------------------------
MOCK_MONITORING: dict[int, PlotMonitoringResponse] = {
    1: PlotMonitoringResponse(
        plot_id=1,
        plot_code="PLOT-001",
        season="2024-25",
        status="ok",
        checkpoint_label="January 31",
        evaluation_date="2025-01-31",
        timeline=[
            TimelinePoint(date="2024-11-15", ndvi=0.28, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2024-12-01", ndvi=0.42, rainfall_mm=2.5, data_gap=False),
            TimelinePoint(date="2024-12-15", ndvi=0.55, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2025-01-01", ndvi=0.68, rainfall_mm=1.0, data_gap=False),
            TimelinePoint(date="2025-01-15", ndvi=0.74, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2025-01-31", ndvi=0.76, rainfall_mm=0.0, data_gap=False),
        ],
        active_alerts=[],
        meta=SYNTHETIC_META,
    ),
    3: PlotMonitoringResponse(
        plot_id=3,
        plot_code="PLOT-003",
        season="2024-25",
        status="ok",
        checkpoint_label="January 15",
        evaluation_date="2025-01-15",
        timeline=[
            TimelinePoint(date="2024-11-15", ndvi=0.22, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2024-12-01", ndvi=0.30, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2024-12-15", ndvi=0.34, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2025-01-01", ndvi=0.38, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2025-01-15", ndvi=0.40, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2025-01-31", ndvi=0.41, rainfall_mm=0.0, data_gap=False),
        ],
        active_alerts=[
            AlertSummary(
                id=101,
                plot_code="PLOT-003",
                season="2024-25",
                checkpoint_label="January 15",
                detected_on="2025-01-15",
                type="crop_health_drop",
                severity="high",
                status="open",
                headline="Vegetation vigor decline (38% drop below plot prior baseline)",
                detail=(
                    "Rainfed plot recorded severe vegetative drag during jointing "
                    "stage; support needed."
                ),
                supportive_action=(
                    "Schedule supportive field visit to inspect soil moisture and assist with "
                    "PMFBY insurance claim."
                ),
                data_gap_warning=None,
            )
        ],
        meta=SYNTHETIC_META,
    ),
    5: PlotMonitoringResponse(
        plot_id=5,
        plot_code="PLOT-005",
        season="2024-25",
        status="data_gap",
        data_gap_reason=(
            "Insufficient clear satellite scenes (< 2 observations) before Jan 15 checkpoint."
        ),
        checkpoint_label="January 15",
        evaluation_date="2025-01-15",
        timeline=[
            TimelinePoint(date="2024-11-15", ndvi=0.26, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2024-12-01", ndvi=0.39, rainfall_mm=1.0, data_gap=False),
            TimelinePoint(date="2024-12-15", ndvi=0.51, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2025-01-01", ndvi=0.62, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2025-01-10", ndvi=None, rainfall_mm=0.0, data_gap=True),
            TimelinePoint(date="2025-01-15", ndvi=0.69, rainfall_mm=0.0, data_gap=False),
        ],
        active_alerts=[
            AlertSummary(
                id=102,
                plot_code="PLOT-005",
                season="2024-25",
                checkpoint_label="January 15",
                detected_on="2025-01-15",
                type="crop_health_drop",
                severity="medium",
                status="open",
                headline="Vegetation monitoring notice (temporary optical data gap)",
                detail=(
                    "Cloud cover obscured Jan 10 Sentinel-2 pass; nearest clear observation "
                    "was evaluated."
                ),
                supportive_action=(
                    "Verify field irrigation status during routine supportive branch contact."
                ),
                data_gap_warning=(
                    "Baseline impacted by single cloud scene. Data gap recorded without guessing."
                ),
            )
        ],
        meta=SYNTHETIC_META,
    ),
}

# ---------------------------------------------------------------------------
# Synthetic Relief Reports
# ---------------------------------------------------------------------------
MOCK_RELIEF_REPORTS: dict[int, ReliefReportResponse] = {
    3: ReliefReportResponse(
        plot_id=3,
        plot_code="PLOT-003",
        season="2024-25",
        baseline_ndvi_mean=0.66,
        current_ndvi_mean=0.39,
        ndvi_drop_pct=40.9,
        estimated_loss_band="33% to 50% loss",
        exceeds_rbi_33_threshold=True,
        supporting_evidence_summary=(
            "Plot recorded a 40.9% drop in vegetative vigor relative to its historical baseline "
            "following zero winter rainfall on rainfed land. Evidence supports loan "
            "restructuring review."
        ),
        disclaimer=(
            "Official crop loss assessment and calamity declaration remain strictly with "
            "government and bank relief committees. This evidence report is for decision "
            "support only."
        ),
        meta=SYNTHETIC_META,
    ),
    1: ReliefReportResponse(
        plot_id=1,
        plot_code="PLOT-001",
        season="2024-25",
        baseline_ndvi_mean=0.72,
        current_ndvi_mean=0.74,
        ndvi_drop_pct=0.0,
        estimated_loss_band="< 33% normal",
        exceeds_rbi_33_threshold=False,
        supporting_evidence_summary=(
            "Normal crop vigor sustained throughout season under tubewell irrigation."
        ),
        disclaimer=(
            "Official crop loss assessment and calamity declaration remain strictly with "
            "government and bank relief committees. This evidence report is for decision "
            "support only."
        ),
        meta=SYNTHETIC_META,
    ),
}

# ---------------------------------------------------------------------------
# Synthetic Farmer Vernacular Summaries
# ---------------------------------------------------------------------------
MOCK_FARMER_SUMMARIES: dict[tuple[int, str], FarmerSummaryResponse] = {
    (1, "en"): FarmerSummaryResponse(
        assessment_id=1,
        plot_code="PLOT-001",
        lang="en",
        source="template",
        summary_text=(
            "Your wheat crop shows strong vegetative health with assured tubewell water. "
            "Your suggested credit limit is ₹80,000 with repayment scheduled in May after harvest."
        ),
        key_points=[
            "Vegetative health is normal.",
            "Tubewell water availability protects against winter dry spells.",
            "Suggested repayment date aligns with wheat harvest in May.",
        ],
        meta=SYNTHETIC_META,
    ),
    (1, "gu"): FarmerSummaryResponse(
        assessment_id=1,
        plot_code="PLOT-001",
        lang="gu",
        source="template",
        summary_text=(
            "તમારા ઘઉંના પાકની સ્થિતિ સારી છે અને બોરવેલનું પાણી ઉપલબ્ધ છે. "
            "પાક માટે ₹૮૦,૦૦૦ ની ધિરાણ મર્યાદા સૂચવવામાં આવી છે, જેની ચુકવણી લણણી પછી મે મહિનામાં થશે."
        ),
        key_points=[
            "પાકનો વિકાસ સામાન્ય અને સારો છે.",
            "બોરવેલનું પાણી શિયાળાના સૂકા સમયમાં પાકનું રક્ષણ કરે છે.",
            "ચુકવણી મે મહિનામાં લણણી પછી રાખવામાં આવી છે.",
        ],
        meta=SYNTHETIC_META,
    ),
    (1, "hi"): FarmerSummaryResponse(
        assessment_id=1,
        plot_code="PLOT-001",
        lang="hi",
        source="template",
        summary_text=(
            "आपकी गेहूं की फसल की स्थिति अच्छी है और नलकूप का पानी उपलब्ध है। "
            "₹80,000 की ऋण सीमा का सुझाव दिया गया है, जिसका भुगतान कटाई के बाद मई में होगा।"
        ),
        key_points=[
            "फसल का वानस्पतिक विकास सामान्य है।",
            "नलकूप सिंचाई से फसल को पानी की कमी से सुरक्षा मिलती है।",
            "ऋण भुगतान की तारीख मई में फसल कटाई के अनुकूल रखी गई है।",
        ],
        meta=SYNTHETIC_META,
    ),
}
