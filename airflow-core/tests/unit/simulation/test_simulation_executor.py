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
"""Tests for ``SimulationExecutor``.

These tests stub the predictor and BaseExecutor side-effecting hooks
(``success``, ``fail``, ``log_task_event``) so that pure dispatch and state
management can be exercised without standing up Airflow infrastructure. The
predictor itself is covered in ``test_predictor_interface``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from airflow.executors import workloads
from airflow.simulation.predictor_interface import (
    DeterministicPredictor,
    PredictedOutcome,
    TaskRuntimeEstimate,
)
from airflow.simulation.simulation_executor import SimulationExecutor


def _fake_estimate() -> TaskRuntimeEstimate:
    return TaskRuntimeEstimate(
        task_id="t",
        operator_type="PythonOperator",
        estimated_seconds=42,
        confidence=0.5,
    )


def _fake_task_workload(*, key="ti-key-1", predicted_outcome="success") -> SimpleNamespace:
    """Build a ``ExecuteTask``-shaped duck-typed object.

    Tests that exercise ``isinstance(workload, workloads.ExecuteTask)`` should
    use ``Mock(spec=workloads.ExecuteTask)`` instead — see ``test_dispatch_*``.
    """
    return SimpleNamespace(
        ti=SimpleNamespace(
            key=key,
            task_id="t",
            dag_id="d",
            run_id="r",
            map_index=-1,
            operator="PythonOperator",
            predicted_outcome=predicted_outcome,
        ),
    )


def _make_executor(*, predictor=None) -> SimulationExecutor:
    """Build an executor with the side-effecting BaseExecutor hooks stubbed out."""
    executor = SimulationExecutor(predictor=predictor or MagicMock(spec=DeterministicPredictor))
    executor.success = MagicMock()
    executor.fail = MagicMock()
    executor.log_task_event = MagicMock()
    return executor


class TestInit:
    def test_defaults_to_deterministic_predictor(self):
        executor = SimulationExecutor()

        assert isinstance(executor.predictor, DeterministicPredictor)

    def test_accepts_custom_predictor(self):
        predictor = MagicMock(spec=DeterministicPredictor)

        executor = SimulationExecutor(predictor=predictor)

        assert executor.predictor is predictor

    def test_executor_flags(self):
        executor = SimulationExecutor()

        assert executor.is_local is True
        assert executor.is_production is False
        assert executor.supports_callbacks is True


class TestProcessWorkloadsDispatch:
    def test_task_workload_dispatched_to_task_handler(self):
        executor = _make_executor()
        executor._process_task_workload = MagicMock()
        executor._process_callback_workload = MagicMock()
        task_workload = Mock(spec=workloads.ExecuteTask)

        executor._process_workloads([task_workload])

        executor._process_task_workload.assert_called_once_with(task_workload)
        executor._process_callback_workload.assert_not_called()

    def test_callback_workload_dispatched_to_callback_handler(self):
        executor = _make_executor()
        executor._process_task_workload = MagicMock()
        executor._process_callback_workload = MagicMock()
        callback_workload = Mock(spec=workloads.ExecuteCallback)

        executor._process_workloads([callback_workload])

        executor._process_callback_workload.assert_called_once_with(callback_workload)
        executor._process_task_workload.assert_not_called()

    def test_unknown_workload_type_raises_value_error(self):
        executor = _make_executor()
        unknown_workload = SimpleNamespace()  # not ExecuteTask, not ExecuteCallback

        with pytest.raises(ValueError, match="does not know how to handle"):
            executor._process_workloads([unknown_workload])


class TestProcessTaskWorkload:
    def test_success_outcome_calls_success_with_info_dict(self):
        predictor = MagicMock()
        predictor.estimate_task.return_value = _fake_estimate()
        executor = _make_executor(predictor=predictor)
        workload = _fake_task_workload(predicted_outcome="success")
        executor.queued_tasks[workload.ti.key] = "anything"  # simulate queued state

        executor._process_task_workload(workload)

        executor.success.assert_called_once()
        executor.fail.assert_not_called()
        info = executor.success.call_args.kwargs["info"]
        assert info == {
            "simulated": True,
            "estimated_runtime": 42,
            "confidence": 0.5,
            "predicted_outcome": "success",
        }
        # State transitions: dequeued + added to running.
        assert workload.ti.key not in executor.queued_tasks
        assert workload.ti.key in executor.running

    def test_failure_outcome_calls_fail(self):
        predictor = MagicMock()
        predictor.estimate_task.return_value = _fake_estimate()
        executor = _make_executor(predictor=predictor)
        workload = _fake_task_workload(predicted_outcome="failure")

        executor._process_task_workload(workload)

        executor.fail.assert_called_once()
        executor.success.assert_not_called()
        assert executor.fail.call_args.kwargs["info"]["predicted_outcome"] == "failure"

    def test_unknown_outcome_treated_as_non_failure_so_success_is_called(self):
        # Per ``_check_outcome``: anything that doesn't parse to FAILURE falls
        # through to the success branch. Pin that contract.
        predictor = MagicMock()
        predictor.estimate_task.return_value = _fake_estimate()
        executor = _make_executor(predictor=predictor)
        workload = _fake_task_workload(predicted_outcome="garbage_value")

        executor._process_task_workload(workload)

        executor.success.assert_called_once()
        executor.fail.assert_not_called()

    def test_logs_simulation_event_with_predictor_metadata(self):
        predictor = MagicMock()
        predictor.estimate_task.return_value = _fake_estimate()
        executor = _make_executor(predictor=predictor)
        workload = _fake_task_workload()

        executor._process_task_workload(workload)

        executor.log_task_event.assert_called_once()
        call = executor.log_task_event.call_args
        assert call.kwargs["event"] == "simulation"
        assert call.kwargs["ti_key"] == workload.ti.key
        assert "estimated_runtime=42s" in call.kwargs["extra"]
        assert "confidence=0.5" in call.kwargs["extra"]

    def test_predictor_called_with_task_metadata(self):
        predictor = MagicMock()
        predictor.estimate_task.return_value = _fake_estimate()
        executor = _make_executor(predictor=predictor)
        workload = _fake_task_workload()

        executor._process_task_workload(workload)

        predictor.estimate_task.assert_called_once_with(
            task_id=workload.ti.task_id,
            operator_type=workload.ti.operator,
            context={
                "dag_id": workload.ti.dag_id,
                "run_id": workload.ti.run_id,
                "map_index": workload.ti.map_index,
            },
        )


class TestProcessCallbackWorkload:
    def test_callback_workload_marks_event_buffer_simulated_success(self):
        executor = _make_executor()
        callback_workload = SimpleNamespace(callback=SimpleNamespace(id="cb-1"))
        executor.queued_callbacks["cb-1"] = "anything"

        executor._process_callback_workload(callback_workload)

        assert "cb-1" not in executor.queued_callbacks
        # event_buffer is keyed by callback id.
        from airflow.utils.state import CallbackState

        assert executor.event_buffer["cb-1"] == (CallbackState.SUCCESS, {"simulated": True})


class TestCheckOutcome:
    @pytest.mark.parametrize(
        ("input_value", "expected"),
        [
            (PredictedOutcome.SUCCESS, PredictedOutcome.SUCCESS),
            (PredictedOutcome.FAILURE, PredictedOutcome.FAILURE),
            ("success", PredictedOutcome.SUCCESS),
            ("failure", PredictedOutcome.FAILURE),
            ("unknown", PredictedOutcome.UNKNOWN),
            ("not-a-real-outcome", PredictedOutcome.UNKNOWN),
            (None, PredictedOutcome.UNKNOWN),
            (42, PredictedOutcome.UNKNOWN),
        ],
    )
    def test_check_outcome_normalization(self, input_value, expected):
        assert SimulationExecutor._check_outcome(input_value) is expected


class TestTerminateAndRevoke:
    def test_terminate_clears_in_memory_state(self):
        executor = _make_executor()
        executor.queued_tasks["a"] = "x"
        executor.queued_callbacks["b"] = "y"
        executor.running.add("c")

        executor.terminate()

        assert executor.queued_tasks == {}
        assert executor.queued_callbacks == {}
        assert executor.running == set()

    def test_revoke_task_removes_ti_from_queued_and_running(self):
        executor = _make_executor()
        ti = SimpleNamespace(key="ti-99")
        executor.queued_tasks["ti-99"] = "x"
        executor.running.add("ti-99")

        executor.revoke_task(ti=ti)

        assert "ti-99" not in executor.queued_tasks
        assert "ti-99" not in executor.running

    def test_revoke_task_is_idempotent_when_ti_not_present(self):
        # Should not raise if the ti was never queued/running.
        executor = _make_executor()
        ti = SimpleNamespace(key="ghost")

        executor.revoke_task(ti=ti)  # should not raise
