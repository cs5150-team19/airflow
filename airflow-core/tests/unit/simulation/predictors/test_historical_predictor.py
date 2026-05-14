# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Tests for the historical data-based runtime predictor."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from airflow.simulation.data.historical_data_extractor import HistoricalRuntime
from airflow.simulation.predictor_interface import (
    _DETERMINISTIC_CONFIDENCE,
    _OPERATOR_RUNTIME_SECONDS,
    OperatorType,
)
from airflow.simulation.predictors.historical_predictor import (
    _OPERATOR_BASE_CONFIDENCE,
    _OPERATOR_MAX_CONFIDENCE,
    AggregationMethod,
    HistoricalPredictor,
    _aggregate,
    _compute_confidence,
    _filter_outliers,
    _percentile,
)

DAG_ID = "test_dag"
TASK_ID = "test_task"
CONTEXT = {"dag_id": DAG_ID}

_PATCH_EXACT = "airflow.simulation.predictors.historical_predictor.get_historical_runtimes"
_PATCH_OPERATOR = "airflow.simulation.predictors.historical_predictor.get_historical_runtimes_by_operator"
_PATCH_FINGERPRINT = (
    "airflow.simulation.predictors.historical_predictor.get_historical_runtimes_by_fingerprint"
)


def _make_runtime(run_id: str, duration: float | None) -> HistoricalRuntime:
    """Helper to build a HistoricalRuntime with only the fields we care about."""
    return HistoricalRuntime(
        run_id=run_id,
        duration=duration,
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 1, 1, 0, 0, 10, tzinfo=timezone.utc),
        state="success",
    )


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestPercentile:
    def test_p50(self):
        assert _percentile([1, 2, 3, 4, 5], 50) == 3.0

    def test_p90(self):
        data = list(range(1, 101))
        assert _percentile(data, 90) == pytest.approx(90.1, abs=0.1)

    def test_p95(self):
        data = list(range(1, 101))
        assert _percentile(data, 95) == pytest.approx(95.05, abs=0.1)

    def test_single_element(self):
        assert _percentile([42], 90) == 42

    def test_two_elements(self):
        assert _percentile([10, 20], 50) == 15.0


class TestFilterOutliers:
    def test_no_outliers(self):
        data = [10.0, 11.0, 12.0, 10.5, 11.5]
        assert _filter_outliers(data) == data

    def test_removes_extreme_value(self):
        data = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10000.0]
        result = _filter_outliers(data)
        assert 10000.0 not in result
        assert len(result) == 9

    def test_too_few_points_returns_unchanged(self):
        data = [10.0, 1000.0]
        assert _filter_outliers(data) == data

    def test_zero_std_returns_unchanged(self):
        data = [5.0, 5.0, 5.0, 5.0]
        assert _filter_outliers(data) == data


class TestAggregate:
    def test_median(self):
        assert _aggregate([1, 2, 3, 4, 100], AggregationMethod.MEDIAN) == 3

    def test_mean(self):
        assert _aggregate([10, 20, 30], AggregationMethod.MEAN) == 20.0

    def test_p90(self):
        data = list(range(1, 11))
        result = _aggregate(data, AggregationMethod.P90)
        assert result == pytest.approx(9.1, abs=0.1)

    def test_p95(self):
        data = list(range(1, 11))
        result = _aggregate(data, AggregationMethod.P95)
        assert result == pytest.approx(9.55, abs=0.1)


class TestComputeConfidence:
    def test_at_min_runs(self):
        assert _compute_confidence(3) == pytest.approx(0.7)

    def test_increases_with_samples(self):
        assert _compute_confidence(30) > _compute_confidence(5)

    def test_capped_at_max(self):
        assert _compute_confidence(1000) == pytest.approx(0.95)

    def test_custom_bounds(self):
        result = _compute_confidence(3, base=0.55, ceiling=0.75)
        assert result == pytest.approx(0.55)

    def test_custom_bounds_capped(self):
        result = _compute_confidence(1000, base=0.55, ceiling=0.75)
        assert result == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# HistoricalPredictor tests — exact match (Level 1)
# ---------------------------------------------------------------------------


class TestHistoricalPredictorExactMatch:
    """Tests for Level 1: exact dag_id + task_id match."""

    def test_sufficient_data_returns_historical_estimate(self):
        """With enough exact-match runs, uses historical median."""
        runtimes = [_make_runtime(f"run_{i}", 10.0 + i) for i in range(5)]
        predictor = HistoricalPredictor(filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == 12  # median of [10,11,12,13,14]
        assert result.confidence >= 0.7

    def test_subsecond_history_preserves_fractional_seconds(self):
        """Sub-second historical runtimes are not rounded down to zero."""
        runtimes = [_make_runtime(f"run_{i}", duration) for i, duration in enumerate([0.1, 0.2, 0.3])]
        predictor = HistoricalPredictor(filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == pytest.approx(0.2)

    def test_null_durations_ignored(self):
        """Runs with None duration are excluded from aggregation."""
        runtimes = [
            _make_runtime("run_0", 10.0),
            _make_runtime("run_1", None),
            _make_runtime("run_2", 20.0),
            _make_runtime("run_3", 30.0),
        ]
        predictor = HistoricalPredictor(filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == 20  # median of [10, 20, 30]

    @pytest.mark.parametrize(
        ("method", "expected"),
        [
            (AggregationMethod.MEDIAN, 30),
            (AggregationMethod.MEAN, 30),
            (AggregationMethod.P90, 46.0),
            (AggregationMethod.P95, 48.0),
        ],
    )
    def test_aggregation_methods(self, method, expected):
        """All aggregation methods produce correct estimates."""
        runtimes = [_make_runtime(f"run_{i}", d) for i, d in enumerate([10, 20, 30, 40, 50])]
        predictor = HistoricalPredictor(aggregation=method, filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == expected

    def test_outlier_filtering_applied(self):
        """Outlier is removed and does not skew the estimate."""
        runtimes = [_make_runtime(f"run_{i}", d) for i, d in enumerate([10, 11, 12, 13, 10000])]
        predictor = HistoricalPredictor(aggregation=AggregationMethod.MEAN, filter_outliers=True)

        with patch(_PATCH_EXACT, return_value=runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds < 20

    def test_outlier_filtering_disabled(self):
        """When disabled, outliers are kept."""
        runtimes = [_make_runtime(f"run_{i}", d) for i, d in enumerate([10, 11, 12, 13, 10000])]
        predictor = HistoricalPredictor(aggregation=AggregationMethod.MEAN, filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds > 1000

    def test_no_context_uses_empty_dag_id(self):
        """Calling without context still works (uses empty dag_id)."""
        runtimes = [_make_runtime(f"run_{i}", 10.0) for i in range(5)]
        predictor = HistoricalPredictor(filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=runtimes) as mock_get:
            predictor.estimate_task(TASK_ID, OperatorType.PYTHON, None)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs[0][0] == ""  # dag_id defaults to ""

    def test_confidence_higher_than_heuristic(self):
        """Historical estimates have higher confidence than heuristic."""
        runtimes = [_make_runtime(f"run_{i}", 10.0 + i) for i in range(20)]
        predictor = HistoricalPredictor(filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.confidence > _DETERMINISTIC_CONFIDENCE

    def test_estimate_dag(self):
        """estimate_dag aggregates per-task estimates correctly."""
        runtimes = [_make_runtime(f"run_{i}", 10.0) for i in range(5)]
        predictor = HistoricalPredictor(filter_outliers=False)
        tasks = [
            {"task_id": "task_a", "operator_type": OperatorType.PYTHON},
            {"task_id": "task_b", "operator_type": OperatorType.BASH},
        ]

        with patch(_PATCH_EXACT, return_value=runtimes):
            result = predictor.estimate_dag(DAG_ID, tasks, CONTEXT)

        assert len(result.task_estimates) == 2
        assert result.total_task_seconds == 20  # 10 + 10


# ---------------------------------------------------------------------------
# HistoricalPredictor tests — operator-type fallback (Level 2)
# ---------------------------------------------------------------------------


class TestHistoricalPredictorOperatorFallback:
    """Tests for Level 2: operator-type cross-DAG fallback."""

    def test_uses_operator_data_when_no_exact_match(self):
        """Falls to operator-type data when exact match has no history."""
        operator_runtimes = [_make_runtime(f"op_run_{i}", 25.0 + i) for i in range(5)]
        predictor = HistoricalPredictor(filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=[]), patch(_PATCH_OPERATOR, return_value=operator_runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == 27  # median of [25,26,27,28,29]
        assert _OPERATOR_BASE_CONFIDENCE <= result.confidence <= _OPERATOR_MAX_CONFIDENCE

    def test_operator_confidence_lower_than_exact(self):
        """Operator-type estimates have lower confidence than exact-match."""
        exact_runtimes = [_make_runtime(f"run_{i}", 10.0) for i in range(20)]
        operator_runtimes = [_make_runtime(f"op_run_{i}", 10.0) for i in range(20)]
        predictor = HistoricalPredictor(filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=exact_runtimes):
            exact_result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        with patch(_PATCH_EXACT, return_value=[]), patch(_PATCH_OPERATOR, return_value=operator_runtimes):
            operator_result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert exact_result.confidence > operator_result.confidence

    def test_operator_fallback_insufficient_data_goes_to_heuristic(self):
        """If operator-type data is also insufficient, falls to heuristic."""
        operator_runtimes = [_make_runtime("op_run_0", 25.0)]
        predictor = HistoricalPredictor(min_runs=3, filter_outliers=False)

        with patch(_PATCH_EXACT, return_value=[]), patch(_PATCH_OPERATOR, return_value=operator_runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == _OPERATOR_RUNTIME_SECONDS[OperatorType.PYTHON]
        assert result.confidence == _DETERMINISTIC_CONFIDENCE

    def test_operator_fallback_with_outlier_filtering(self):
        """Outlier filtering applies to operator-type data too."""
        operator_runtimes = [_make_runtime(f"op_run_{i}", d) for i, d in enumerate([20, 21, 22, 23, 20000])]
        predictor = HistoricalPredictor(
            aggregation=AggregationMethod.MEAN,
            filter_outliers=True,
        )

        with patch(_PATCH_EXACT, return_value=[]), patch(_PATCH_OPERATOR, return_value=operator_runtimes):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds < 30

    def test_exact_match_preferred_over_operator(self):
        """Exact match is used even when operator data exists."""
        exact_runtimes = [_make_runtime(f"run_{i}", 10.0) for i in range(5)]
        operator_runtimes = [_make_runtime(f"op_run_{i}", 99.0) for i in range(5)]
        predictor = HistoricalPredictor(filter_outliers=False)

        with (
            patch(_PATCH_EXACT, return_value=exact_runtimes),
            patch(_PATCH_OPERATOR, return_value=operator_runtimes) as mock_op,
        ):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == 10
        mock_op.assert_not_called()


# ---------------------------------------------------------------------------
# HistoricalPredictor tests — full fallback chain (Level 1 → 2 → 3)
# ---------------------------------------------------------------------------


class TestHistoricalPredictorFullFallback:
    """Tests for the complete fallback chain."""

    def test_no_data_anywhere_falls_to_heuristic(self):
        """No exact match, no operator data → DeterministicPredictor."""
        predictor = HistoricalPredictor()

        with patch(_PATCH_EXACT, return_value=[]), patch(_PATCH_OPERATOR, return_value=[]):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == _OPERATOR_RUNTIME_SECONDS[OperatorType.PYTHON]
        assert result.confidence == _DETERMINISTIC_CONFIDENCE

    def test_all_none_durations_falls_through(self):
        """All None durations at both levels falls to heuristic."""
        none_runtimes = [_make_runtime(f"run_{i}", None) for i in range(5)]
        predictor = HistoricalPredictor()

        with (
            patch(_PATCH_EXACT, return_value=none_runtimes),
            patch(_PATCH_OPERATOR, return_value=none_runtimes),
        ):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.confidence == _DETERMINISTIC_CONFIDENCE

    def test_exact_insufficient_operator_sufficient(self):
        """Exact match has 2 runs (insufficient), operator has 5 → uses operator."""
        exact_runtimes = [_make_runtime(f"run_{i}", 10.0) for i in range(2)]
        operator_runtimes = [_make_runtime(f"op_run_{i}", 50.0) for i in range(5)]
        predictor = HistoricalPredictor(min_runs=3, filter_outliers=False)

        with (
            patch(_PATCH_EXACT, return_value=exact_runtimes),
            patch(_PATCH_OPERATOR, return_value=operator_runtimes),
        ):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        assert result.estimated_seconds == 50
        assert _OPERATOR_BASE_CONFIDENCE <= result.confidence <= _OPERATOR_MAX_CONFIDENCE

    def test_custom_min_runs_affects_all_levels(self):
        """Custom min_runs threshold applies to both exact and operator levels."""
        exact_runtimes = [_make_runtime(f"run_{i}", 10.0) for i in range(5)]
        operator_runtimes = [_make_runtime(f"op_run_{i}", 50.0) for i in range(5)]
        predictor = HistoricalPredictor(min_runs=10, filter_outliers=False)

        with (
            patch(_PATCH_EXACT, return_value=exact_runtimes),
            patch(_PATCH_OPERATOR, return_value=operator_runtimes),
        ):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        # Both have 5 runs < min_runs=10, falls to heuristic
        assert result.confidence == _DETERMINISTIC_CONFIDENCE


# ---------------------------------------------------------------------------
# Level 2: cross-DAG fingerprint match
# ---------------------------------------------------------------------------


_FINGERPRINT_CONTEXT = {"dag_id": DAG_ID, "task_fingerprint": "abc123"}


class TestHistoricalPredictorFingerprintFallback:
    """Pin the fingerprint fallback's position between exact match and operator-only."""

    def test_fingerprint_used_when_exact_insufficient(self):
        # Exact match has only 1 run (below min_runs); fingerprint has plenty.
        exact_runtimes = [_make_runtime("r1", 10.0)]
        fp_runtimes = [_make_runtime(f"r{i}", 100.0) for i in range(5)]

        predictor = HistoricalPredictor(filter_outliers=False)

        with (
            patch(_PATCH_EXACT, return_value=exact_runtimes),
            patch(_PATCH_FINGERPRINT, return_value=fp_runtimes) as fp_mock,
            patch(_PATCH_OPERATOR, return_value=[]) as op_mock,
        ):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, _FINGERPRINT_CONTEXT)

        # Result reflects fingerprint data (median=100), not exact (10).
        assert result.estimated_seconds == 100
        # Operator query should not even be reached.
        op_mock.assert_not_called()
        # Fingerprint query was called with the fingerprint from context.
        fp_mock.assert_called_once()
        assert fp_mock.call_args.args[0] == "abc123"

    def test_fingerprint_skipped_when_context_lacks_fingerprint(self):
        # Context has no "task_fingerprint" key — predictor must skip Level 2
        # and fall through to operator-type without ever calling the
        # fingerprint extractor.
        exact_runtimes = [_make_runtime("r1", 10.0)]
        operator_runtimes = [_make_runtime(f"r{i}", 50.0) for i in range(5)]

        predictor = HistoricalPredictor(filter_outliers=False)

        with (
            patch(_PATCH_EXACT, return_value=exact_runtimes),
            patch(_PATCH_FINGERPRINT, return_value=[]) as fp_mock,
            patch(_PATCH_OPERATOR, return_value=operator_runtimes),
        ):
            predictor.estimate_task(TASK_ID, OperatorType.PYTHON, CONTEXT)

        fp_mock.assert_not_called()

    def test_fingerprint_skipped_when_fingerprint_is_none(self):
        # An explicit None fingerprint (the helper's "no signal" return) should
        # also skip Level 2.
        predictor = HistoricalPredictor(filter_outliers=False)

        with (
            patch(_PATCH_EXACT, return_value=[]),
            patch(_PATCH_FINGERPRINT, return_value=[]) as fp_mock,
            patch(_PATCH_OPERATOR, return_value=[]),
        ):
            predictor.estimate_task(
                TASK_ID,
                OperatorType.PYTHON,
                {"dag_id": DAG_ID, "task_fingerprint": None},
            )

        fp_mock.assert_not_called()

    def test_fingerprint_falls_through_when_below_min_runs(self):
        # Fingerprint level returns 1 run (below min_runs); predictor should
        # fall through to operator-type instead of using bad data.
        operator_runtimes = [_make_runtime(f"r{i}", 50.0) for i in range(5)]

        predictor = HistoricalPredictor(filter_outliers=False)

        with (
            patch(_PATCH_EXACT, return_value=[]),
            patch(_PATCH_FINGERPRINT, return_value=[_make_runtime("only", 100.0)]),
            patch(_PATCH_OPERATOR, return_value=operator_runtimes),
        ):
            result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, _FINGERPRINT_CONTEXT)

        # Result should reflect the operator-level estimate (50), not the
        # singleton fingerprint match (100).
        assert result.estimated_seconds == 50

    def test_fingerprint_confidence_is_between_exact_and_operator(self):
        # Same number of samples at fingerprint and operator levels — verify
        # the confidence ordering: exact > fingerprint > operator > heuristic.
        runtimes = [_make_runtime(f"r{i}", 50.0) for i in range(5)]

        predictor = HistoricalPredictor(filter_outliers=False)

        with (
            patch(_PATCH_EXACT, return_value=runtimes),
            patch(_PATCH_FINGERPRINT, return_value=[]),
            patch(_PATCH_OPERATOR, return_value=[]),
        ):
            exact_result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, _FINGERPRINT_CONTEXT)
        with (
            patch(_PATCH_EXACT, return_value=[]),
            patch(_PATCH_FINGERPRINT, return_value=runtimes),
            patch(_PATCH_OPERATOR, return_value=[]),
        ):
            fp_result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, _FINGERPRINT_CONTEXT)
        with (
            patch(_PATCH_EXACT, return_value=[]),
            patch(_PATCH_FINGERPRINT, return_value=[]),
            patch(_PATCH_OPERATOR, return_value=runtimes),
        ):
            op_result = predictor.estimate_task(TASK_ID, OperatorType.PYTHON, _FINGERPRINT_CONTEXT)

        assert exact_result.confidence > fp_result.confidence > op_result.confidence
        assert op_result.confidence > _DETERMINISTIC_CONFIDENCE
