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
"""Tests for :class:`SuccessPredictor`.

DB calls are mocked via ``unittest.mock.patch`` so these tests run without
infrastructure. Integration coverage with seeded DAG-runs lives in the
api_fastapi simulation endpoint tests.
"""

from __future__ import annotations

import math
from unittest.mock import patch

import pytest

from airflow.simulation.predictors.success_predictor import (
    _DAG_SUCCESS_STATES,
    _TASK_SUCCESS_STATES,
    SuccessPredictor,
    WeightingMethod,
    _compute_weights,
    _weighted_success_rate,
)

DAG_ID = "test_dag"
TASK_ID = "test_task"

_PATCH_TASK_HISTORY = (
    "airflow.simulation.predictors.success_predictor.get_task_state_history"
)
_PATCH_DAG_HISTORY = (
    "airflow.simulation.predictors.success_predictor.get_dag_run_state_history"
)
# Backwards-compat alias for tests that only exercise the per-task path.
_PATCH_HISTORY = _PATCH_TASK_HISTORY


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestComputeWeights:
    def test_none_weighting_uniform(self):
        weights = _compute_weights(4, WeightingMethod.NONE, decay_lambda=0.1)

        assert weights == [1.0, 1.0, 1.0, 1.0]

    def test_linear_weighting_decreases_with_age(self):
        weights = _compute_weights(4, WeightingMethod.LINEAR, decay_lambda=0.1)

        # Newest first: highest weight at index 0, lowest at the end.
        assert weights == [4.0, 3.0, 2.0, 1.0]
        # Strictly decreasing.
        assert all(weights[i] > weights[i + 1] for i in range(len(weights) - 1))

    def test_exponential_weighting_decays(self):
        weights = _compute_weights(3, WeightingMethod.EXPONENTIAL, decay_lambda=1.0)

        # weights[i] = exp(-1.0 * i)
        assert weights[0] == pytest.approx(1.0)
        assert weights[1] == pytest.approx(math.exp(-1.0))
        assert weights[2] == pytest.approx(math.exp(-2.0))
        # Decay rate is steeper than linear for the same length.
        linear = _compute_weights(3, WeightingMethod.LINEAR, decay_lambda=1.0)
        ratio_exp = weights[2] / weights[0]
        ratio_linear = linear[2] / linear[0]
        assert ratio_exp < ratio_linear

    def test_zero_runs_returns_empty(self):
        assert _compute_weights(0, WeightingMethod.NONE, decay_lambda=0.1) == []

    @pytest.mark.parametrize(
        "method", [WeightingMethod.NONE, WeightingMethod.LINEAR, WeightingMethod.EXPONENTIAL]
    )
    def test_all_methods_return_correct_length(self, method):
        weights = _compute_weights(7, method, decay_lambda=0.1)

        assert len(weights) == 7


class TestWeightedSuccessRate:
    def test_all_success_returns_one(self):
        rate = _weighted_success_rate(["success"] * 4, [1.0] * 4, _TASK_SUCCESS_STATES)

        assert rate == 1.0

    def test_all_failed_returns_zero(self):
        rate = _weighted_success_rate(["failed"] * 4, [1.0] * 4, _TASK_SUCCESS_STATES)

        assert rate == 0.0

    def test_mixed_with_uniform_weights(self):
        rate = _weighted_success_rate(
            ["success", "success", "success", "failed"],
            [1.0, 1.0, 1.0, 1.0],
            _TASK_SUCCESS_STATES,
        )

        assert rate == pytest.approx(0.75)

    def test_task_success_set_includes_skipped_and_removed(self):
        # Per-task semantics: ``skipped`` and ``removed`` count as success.
        # Only ``failed`` and ``upstream_failed`` are real failures.
        rate = _weighted_success_rate(
            ["success", "skipped", "removed", "failed", "upstream_failed"],
            [1.0] * 5,
            _TASK_SUCCESS_STATES,
        )

        # 3 of 5 (success + skipped + removed) counted as success.
        assert rate == pytest.approx(0.6)

    def test_dag_success_set_excludes_skipped(self):
        # DAG-level semantics: only ``success`` counts. There is no DAG-level
        # ``skipped`` state — but feeding one in would correctly count as
        # not-success under the strict DAG set.
        rate = _weighted_success_rate(
            ["success", "success", "failed"],
            [1.0, 1.0, 1.0],
            _DAG_SUCCESS_STATES,
        )

        assert rate == pytest.approx(2 / 3)

    def test_recent_failure_weighs_more_with_linear_weighting(self):
        # Newest run failed, older 3 succeeded — linear weighting should pull
        # the rate below the uniform 0.75.
        states = ["failed", "success", "success", "success"]
        uniform = _weighted_success_rate(states, [1.0, 1.0, 1.0, 1.0], _TASK_SUCCESS_STATES)
        weighted = _weighted_success_rate(
            states,
            _compute_weights(4, WeightingMethod.LINEAR, decay_lambda=0.1),
            _TASK_SUCCESS_STATES,
        )

        assert weighted < uniform

    def test_zero_total_weight_returns_zero(self):
        # Defensive: shouldn't happen in practice (weights are positive), but
        # the function must not divide by zero.
        rate = _weighted_success_rate(["success"], [0.0], _TASK_SUCCESS_STATES)

        assert rate == 0.0


# ---------------------------------------------------------------------------
# SuccessPredictor.predict_task_success
# ---------------------------------------------------------------------------


class TestPredictTaskSuccess:
    def test_returns_default_when_below_min_runs(self):
        predictor = SuccessPredictor(min_runs=3, default_probability=0.42)

        with patch(_PATCH_HISTORY, return_value=["success", "success"]):
            assert predictor.predict_task_success(DAG_ID, TASK_ID) == 0.42

    def test_returns_one_when_all_runs_succeeded(self):
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_HISTORY, return_value=["success"] * 5):
            assert predictor.predict_task_success(DAG_ID, TASK_ID) == 1.0

    def test_returns_zero_when_all_runs_failed(self):
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_HISTORY, return_value=["failed"] * 5):
            assert predictor.predict_task_success(DAG_ID, TASK_ID) == 0.0

    def test_skipped_runs_count_as_success(self):
        # Branching DAGs steer around tasks; ``skipped`` is normal operation,
        # not a failure mode. Pinning this explicitly because the original
        # implementation treated everything-but-success as failure and made
        # branched-around tasks score very low.
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_HISTORY, return_value=["skipped"] * 5):
            assert predictor.predict_task_success(DAG_ID, TASK_ID) == 1.0

    def test_mixed_success_and_skipped_returns_one(self):
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_HISTORY, return_value=["success", "skipped", "skipped", "success"]):
            assert predictor.predict_task_success(DAG_ID, TASK_ID) == 1.0

    def test_failed_states_still_lower_score(self):
        # ``failed`` and ``upstream_failed`` are the only states that should
        # bring per-task probability below 1.0.
        predictor = SuccessPredictor(min_runs=3)

        with patch(
            _PATCH_HISTORY, return_value=["success", "skipped", "failed", "upstream_failed"]
        ):
            # 2 of 4 (success + skipped) count; failed + upstream_failed do not.
            assert predictor.predict_task_success(DAG_ID, TASK_ID) == pytest.approx(0.5)

    def test_uniform_weighting_returns_simple_ratio(self):
        # 3 of 4 = 0.75
        predictor = SuccessPredictor(min_runs=3, weighting=WeightingMethod.NONE)

        with patch(_PATCH_HISTORY, return_value=["success", "success", "success", "failed"]):
            assert predictor.predict_task_success(DAG_ID, TASK_ID) == pytest.approx(0.75)

    def test_linear_weighting_biases_toward_recent(self):
        predictor_linear = SuccessPredictor(
            min_runs=3, weighting=WeightingMethod.LINEAR
        )
        predictor_uniform = SuccessPredictor(min_runs=3, weighting=WeightingMethod.NONE)
        # Newest run failed; oldest 3 succeeded.
        states = ["failed", "success", "success", "success"]

        with patch(_PATCH_HISTORY, return_value=states):
            linear_prob = predictor_linear.predict_task_success(DAG_ID, TASK_ID)
        with patch(_PATCH_HISTORY, return_value=states):
            uniform_prob = predictor_uniform.predict_task_success(DAG_ID, TASK_ID)

        assert linear_prob < uniform_prob

    def test_exponential_weighting_more_aggressive_than_linear(self):
        states = ["failed", "success", "success", "success"]
        linear = SuccessPredictor(min_runs=3, weighting=WeightingMethod.LINEAR)
        exponential = SuccessPredictor(
            min_runs=3, weighting=WeightingMethod.EXPONENTIAL, decay_lambda=1.0
        )

        with patch(_PATCH_HISTORY, return_value=states):
            linear_prob = linear.predict_task_success(DAG_ID, TASK_ID)
        with patch(_PATCH_HISTORY, return_value=states):
            exp_prob = exponential.predict_task_success(DAG_ID, TASK_ID)

        # Both penalize recent failure, but exponential weighs the recent run more.
        assert exp_prob < linear_prob

    def test_lookback_none_passes_no_start_date(self):
        # When lookback_days is None, get_task_state_history should be called
        # with start_date=None (i.e. no time-window restriction).
        predictor = SuccessPredictor(lookback_days=None, min_runs=3)

        with patch(_PATCH_HISTORY, return_value=["success"] * 3) as mock_history:
            predictor.predict_task_success(DAG_ID, TASK_ID)

            mock_history.assert_called_once()
            assert mock_history.call_args.kwargs["start_date"] is None

    def test_lookback_days_passes_start_date(self):
        predictor = SuccessPredictor(lookback_days=14, min_runs=3)

        with patch(_PATCH_HISTORY, return_value=["success"] * 3) as mock_history:
            predictor.predict_task_success(DAG_ID, TASK_ID)

            assert mock_history.call_args.kwargs["start_date"] is not None

    def test_query_uses_max_runs_as_limit(self):
        predictor = SuccessPredictor(max_runs=42, min_runs=3)

        with patch(_PATCH_HISTORY, return_value=["success"] * 3) as mock_history:
            predictor.predict_task_success(DAG_ID, TASK_ID)

            assert mock_history.call_args.kwargs["limit"] == 42


# ---------------------------------------------------------------------------
# SuccessPredictor.predict_dag_success
# ---------------------------------------------------------------------------


class TestPredictDagSuccessRate:
    """``predict_dag_success_rate`` reads DagRun.state history directly."""

    def test_returns_default_when_below_min_runs(self):
        predictor = SuccessPredictor(min_runs=3, default_probability=0.42)

        with patch(_PATCH_DAG_HISTORY, return_value=["success", "success"]):
            assert predictor.predict_dag_success_rate(DAG_ID) == 0.42

    def test_all_success_returns_one(self):
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_DAG_HISTORY, return_value=["success"] * 5):
            assert predictor.predict_dag_success_rate(DAG_ID) == 1.0

    def test_all_failed_returns_zero(self):
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_DAG_HISTORY, return_value=["failed"] * 5):
            assert predictor.predict_dag_success_rate(DAG_ID) == 0.0

    def test_mixed_returns_simple_ratio(self):
        # 3 of 4 = 0.75
        predictor = SuccessPredictor(min_runs=3)

        with patch(
            _PATCH_DAG_HISTORY,
            return_value=["success", "success", "success", "failed"],
        ):
            assert predictor.predict_dag_success_rate(DAG_ID) == pytest.approx(0.75)

    def test_uses_max_runs_as_limit_for_dag_query(self):
        predictor = SuccessPredictor(max_runs=42, min_runs=3)

        with patch(_PATCH_DAG_HISTORY, return_value=["success"] * 3) as mock_history:
            predictor.predict_dag_success_rate(DAG_ID)

            assert mock_history.call_args.kwargs["limit"] == 42


class TestPredictDagSuccess:
    """``predict_dag_success`` returns (dag_prob, per_task_probs).

    DAG probability comes from DagRun history, NOT from multiplying per-task
    probabilities — this prevents geometric decay across many tasks and lets
    branching DAGs (where many tasks are routinely skipped) score correctly.
    """

    def test_empty_task_list_still_returns_dag_probability(self):
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_DAG_HISTORY, return_value=["success"] * 3):
            dag_prob, per_task = predictor.predict_dag_success(DAG_ID, [])

        assert dag_prob == 1.0
        assert per_task == {}

    def test_dag_probability_independent_of_per_task_probabilities(self):
        # Per-task data says everything fails; DagRun data says everything
        # succeeded. The DAG-level number must reflect the DagRun history.
        # This is the bug fix for branching DAGs scoring as failure.
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_TASK_HISTORY, return_value=["failed"] * 3):
            with patch(_PATCH_DAG_HISTORY, return_value=["success"] * 5):
                dag_prob, per_task = predictor.predict_dag_success(DAG_ID, ["a", "b", "c"])

        assert dag_prob == 1.0
        # Per-task probabilities are still surfaced for the UI, just not
        # multiplied into the DAG number.
        assert per_task == {"a": 0.0, "b": 0.0, "c": 0.0}

    def test_branching_dag_scenario_scores_high(self):
        # Regression test for the example_branch_operator_decorator bug:
        # tasks routinely skipped should not pull DAG probability to zero,
        # because (a) skipped now counts as task-level success and (b) the
        # DAG number is computed from DagRun history.
        predictor = SuccessPredictor(min_runs=3)

        def fake_task_history(dag_id, task_id, **_kwargs):
            del dag_id
            # ``branch_b`` is routinely skipped because branching steers
            # around it; older skipped runs + 1 success on a recent pick.
            if task_id == "branch_b":
                return ["skipped", "skipped", "skipped", "success", "skipped"]
            return ["success"] * 5

        with patch(_PATCH_TASK_HISTORY, side_effect=fake_task_history):
            with patch(_PATCH_DAG_HISTORY, return_value=["success"] * 10):
                dag_prob, per_task = predictor.predict_dag_success(
                    DAG_ID, ["branch_a", "branch_b", "branch_c"]
                )

        assert dag_prob == 1.0
        # branch_b: 5/5 (skipped + success both count) → 1.0
        assert per_task["branch_b"] == pytest.approx(1.0)
        assert per_task["branch_a"] == pytest.approx(1.0)
        assert per_task["branch_c"] == pytest.approx(1.0)

    def test_per_task_dict_includes_every_requested_task_id(self):
        predictor = SuccessPredictor(min_runs=3)

        with patch(_PATCH_TASK_HISTORY, return_value=["success"] * 3):
            with patch(_PATCH_DAG_HISTORY, return_value=["success"] * 3):
                _, per_task = predictor.predict_dag_success(DAG_ID, ["a", "b", "c"])

        assert set(per_task) == {"a", "b", "c"}


class TestConstructorValidation:
    @pytest.mark.parametrize("invalid", [-0.1, 1.1, 2.0, -1.0])
    def test_default_probability_must_be_in_unit_interval(self, invalid):
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            SuccessPredictor(default_probability=invalid)

    def test_min_runs_clamped_to_at_least_one(self):
        # Defensive: a 0 or negative min_runs would let a zero-history task
        # produce a divide-by-zero or a 0-of-0 reading.
        predictor = SuccessPredictor(min_runs=0)

        assert predictor.min_runs == 1
