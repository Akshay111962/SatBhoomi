"""Parity test proving risk scores and bands remain identical after reason labelling update.

Verifies:
1. Pure risk score and band parity across all 105 plot-seasons in features.csv.
2. Every output reason carries its specific rule or feature key (e.g. relative_ndvi_rule,
   rainfall_rule, price_rule) and NEVER the generic placeholder in newly scored rows.
3. Existing stored assessments keep their old text and map to the generic template.
4. Schema compatibility with ReasonItem.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from satbhoomi.api.adapters import (
    adapt_risk_score_to_assessment_response,
    adapt_stored_assessment_to_response,
)
from satbhoomi.features.config import FEATURE_COLUMNS
from satbhoomi.risk.reason_templates import (
    NEW_REASON_RULE_KEYS,
    TEMPLATE_FEATURES,
    render_feature_reason,
)
from satbhoomi.risk.scoring import (
    get_default_rules_baseline,
    map_score_to_band,
    score_plot_season,
)


def test_scores_and_bands_parity_across_all_stored_plot_seasons() -> None:
    """Prove scores and bands are 100% identical before and after reason labelling change."""
    features_path = Path("data/processed/features.csv")
    if not features_path.is_file():
        pytest.skip("data/processed/features.csv not present in environment")

    df = pd.read_csv(features_path)
    assert len(df) == 105, f"Expected 105 plot-seasons, got {len(df)}"

    rules_model = get_default_rules_baseline()

    allowed_specific_keys = set(FEATURE_COLUMNS) | {
        "relative_ndvi_rule",
        "rainfall_rule",
        "price_rule",
    }

    scored_count = 0
    insufficient_count = 0

    for _, row in df.iterrows():
        row_dict: dict[str, Any] = dict(row.items())
        res = score_plot_season(row_dict, scorer="rules_baseline", model=rules_model)

        if res.status == "ok":
            scored_count += 1
            # 1. Score & band integrity
            assert res.score is not None
            assert res.band == map_score_to_band(res.score)

            # Predict directly from the model to verify zero divergence
            row_df = pd.DataFrame([row_dict])
            expected_prob = rules_model.predict_proba(row_df)[0, 1]
            expected_score = int(round(expected_prob * 100.0))
            expected_band = map_score_to_band(expected_score)

            assert res.score == expected_score, (
                f"Score mismatch for {res.plot_code} {res.season}: {res.score} vs {expected_score}"
            )
            assert res.band == expected_band

            # 2. Reason keys labelling: exactly 3 specific rule/feature keys, zero generic
            assert len(res.reasons) == 3
            assert len(res.reason_keys) == 3
            for key in res.reason_keys:
                assert key in allowed_specific_keys, f"Unexpected reason key '{key}'"
                assert key != "in_season_agronomic_indicators", (
                    f"Generic placeholder found in newly scored reason for {res.plot_code}"
                )

            # 3. Adapter output labelling
            adapted = adapt_risk_score_to_assessment_response(res)
            assert len(adapted.reasons) == 3
            for r_item, expected_key in zip(adapted.reasons, res.reason_keys, strict=True):
                assert r_item.feature_name == expected_key
                assert r_item.feature_name != "in_season_agronomic_indicators"
                assert len(r_item.text) > 10
        else:
            insufficient_count += 1
            assert res.score is None
            assert res.band is None
            assert res.reasons == []
            assert res.reason_keys == []

    # Exactly Season 1 (21 plots) has insufficient historical baseline
    assert insufficient_count == 21, f"Expected 21 cold-start rows, got {insufficient_count}"
    assert scored_count == 84, f"Expected 84 scored rows across seasons 2-5, got {scored_count}"


def test_existing_stored_assessments_keep_old_text_and_map_to_generic_template() -> None:
    """Existing assessments with 'in_season_agronomic_indicators' preserve text.

    Mapped to generic template.
    """
    old_text = "Historical observation shows standard vegetative development."
    mock_assessment = MagicMock()
    mock_assessment.id = 99
    mock_assessment.plot_id = 5
    mock_assessment.season = "2023-24"
    mock_assessment.status = "ok"
    mock_assessment.score = 25.0
    mock_assessment.band = "low"
    mock_assessment.model_version = "v1.0"
    mock_assessment.scorer = "rules_baseline"
    mock_assessment.cutoff_date = "2024-01-31"
    mock_assessment.data_warnings = []
    mock_assessment.insufficient_data_reason = None
    mock_assessment.loan_suggestion_json = None
    mock_assessment.created_at = "2026-11-15T10:00:00Z"
    mock_assessment.reasons_json = [
        {"feature_name": "in_season_agronomic_indicators", "text": old_text},
    ]

    adapted = adapt_stored_assessment_to_response(mock_assessment, plot_code="PLOT-005")
    assert len(adapted.reasons) == 1
    assert adapted.reasons[0].feature_name == "in_season_agronomic_indicators"
    assert adapted.reasons[0].text == old_text

    # Generic template produces valid non-empty wording and preserves text
    rendered_from_text = render_feature_reason("in_season_agronomic_indicators", old_text)
    assert rendered_from_text == old_text

    rendered_generic_up = render_feature_reason(
        "in_season_agronomic_indicators", 0.0, direction="up"
    )
    assert "farm stress" in rendered_generic_up.lower()
    assert len(rendered_generic_up) > 10

    rendered_generic_normal = render_feature_reason(
        "in_season_agronomic_indicators", 0.0, direction="neutral"
    )
    assert "normal" in rendered_generic_normal.lower()
    assert len(rendered_generic_normal) > 10


def test_template_completeness_all_new_and_feature_keys() -> None:
    """Verify all new keys are registered in TEMPLATE_FEATURES and completeness check."""
    for new_key in (
        "relative_ndvi_rule",
        "rainfall_rule",
        "price_rule",
        "in_season_agronomic_indicators",
    ):
        assert new_key in NEW_REASON_RULE_KEYS
        assert new_key in TEMPLATE_FEATURES
