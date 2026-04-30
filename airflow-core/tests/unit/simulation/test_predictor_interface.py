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
"""Tests for ``DeterministicPredictor`` and the predictor interface contract.

The deterministic predictor is the bottom of the fallback chain — it has no
DB dependencies and returns a constant per operator type, so historical and
similar-DAG predictors are tested elsewhere via mocks. This file pins the
operator → seconds mapping, the confidence value, and the ``estimate_dag``
aggregation contract that all predictors inherit.
"""

from __future__ import annotations

import pytest

from airflow.simulation.predictor_interface import (
    _DETERMINISTIC_CONFIDENCE,
    _OPERATOR_RUNTIME_SECONDS,
    DeterministicPredictor,
    OperatorType,
    PredictedOutcome,
    PredictorInterface,
    SimulationEstimate,
    TaskRuntimeEstimate,
)


class TestDeterministicEstimateTask:
    @pytest.fixture
    def predictor(self) -> DeterministicPredictor:
        return DeterministicPredictor()

    @pytest.mark.parametrize(
        ("operator_type", "expected_seconds"),
        [
            (OperatorType.PYTHON, 30),
            (OperatorType.BASH, 10),
            (OperatorType.MYSQL, 60),
            (OperatorType.POSTGRES, 60),
            (OperatorType.S3_KEY, 300),
            (OperatorType.UNKNOWN, 30),
        ],
    )
    def test_known_operator_returns_mapped_runtime(self, predictor, operator_type, expected_seconds):
        estimate = predictor.estimate_task("t1", operator_type)

        assert estimate.estimated_seconds == expected_seconds

    def test_known_operator_table_matches_implementation_table(self, predictor):
        # Guards against the public mapping silently drifting from the source-of-truth dict.
        for operator_type, expected_seconds in _OPERATOR_RUNTIME_SECONDS.items():
            estimate = predictor.estimate_task("t1", operator_type)
            assert estimate.estimated_seconds == expected_seconds

    def test_unknown_operator_falls_back_to_default(self, predictor):
        estimate = predictor.estimate_task("t1", "TotallyMadeUpOperator")

        # The implementation defaults to 30s for unmapped operator strings.
        assert estimate.estimated_seconds == 30

    def test_confidence_is_constant_heuristic_value(self, predictor):
        estimate = predictor.estimate_task("t1", OperatorType.PYTHON)

        assert estimate.confidence == _DETERMINISTIC_CONFIDENCE

    @pytest.mark.parametrize(
        "operator_type",
        [OperatorType.PYTHON, OperatorType.BASH, OperatorType.UNKNOWN, "MysteryOperator"],
    )
    def test_confidence_is_within_unit_interval(self, predictor, operator_type):
        estimate = predictor.estimate_task("t1", operator_type)

        assert 0.0 <= estimate.confidence <= 1.0

    def test_estimate_preserves_task_and_operator_metadata(self, predictor):
        estimate = predictor.estimate_task("my_task", OperatorType.PYTHON)

        assert estimate.task_id == "my_task"
        assert estimate.operator_type == OperatorType.PYTHON

    def test_context_is_accepted_but_ignored(self, predictor):
        # Deterministic predictor takes ``context`` for interface parity but
        # must not let context perturb the result.
        without_ctx = predictor.estimate_task("t1", OperatorType.PYTHON)
        with_ctx = predictor.estimate_task(
            "t1", OperatorType.PYTHON, context={"run_history": [1, 2, 3], "input_bytes": 999}
        )

        assert without_ctx == with_ctx

    def test_returns_task_runtime_estimate_dataclass(self, predictor):
        estimate = predictor.estimate_task("t1", OperatorType.PYTHON)

        assert isinstance(estimate, TaskRuntimeEstimate)


class TestEstimateDagAggregation:
    """``estimate_dag`` is final on the interface — every predictor inherits it."""

    def test_total_equals_sum_of_task_estimates(self):
        predictor = DeterministicPredictor()
        tasks = [
            {"task_id": "a", "operator_type": OperatorType.PYTHON},  # 30
            {"task_id": "b", "operator_type": OperatorType.BASH},  # 10
            {"task_id": "c", "operator_type": OperatorType.S3_KEY},  # 300
        ]

        estimate = predictor.estimate_dag("my_dag", tasks)

        assert isinstance(estimate, SimulationEstimate)
        assert estimate.dag_id == "my_dag"
        assert estimate.total_task_seconds == 30 + 10 + 300
        assert estimate.total_task_seconds == sum(e.estimated_seconds for e in estimate.task_estimates)

    def test_predicted_outcome_defaults_to_success(self):
        predictor = DeterministicPredictor()
        estimate = predictor.estimate_dag("d", [{"task_id": "t", "operator_type": OperatorType.PYTHON}])

        assert estimate.predicted_outcome is PredictedOutcome.SUCCESS

    def test_empty_dag_yields_zero_total(self):
        predictor = DeterministicPredictor()

        estimate = predictor.estimate_dag("empty", [])

        assert estimate.task_estimates == []
        assert estimate.total_task_seconds == 0

    def test_missing_operator_type_treated_as_unknown(self):
        predictor = DeterministicPredictor()
        # task entry omits "operator_type" entirely
        tasks = [{"task_id": "t1"}]

        estimate = predictor.estimate_dag("d", tasks)

        # Falls back to OperatorType.UNKNOWN → 30s.
        assert estimate.task_estimates[0].estimated_seconds == 30


class TestInterfaceContract:
    def test_deterministic_is_a_predictor(self):
        assert isinstance(DeterministicPredictor(), PredictorInterface)

    def test_abstract_predictor_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            PredictorInterface()  # type: ignore[abstract]
