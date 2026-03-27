"""Simulation executor that resolves workloads without running real tasks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from airflow.executors import workloads
from airflow.executors.base_executor import PARALLELISM, BaseExecutor
from airflow.executors.executor_utils import ExecutorName
from airflow.utils.state import CallbackState

from airflow.simulation.predictor_interface import (
    DeterministicPredictor,
    OperatorType,
    PredictedOutcome,
    PredictorInterface,
    TaskRuntimeEstimate,
)

if TYPE_CHECKING:
    from airflow.models.taskinstance import TaskInstance


class SimulationExecutor(BaseExecutor):
    """
    Executor that simulates task completion instead of running real work.
    """

    is_local = True
    is_production = False
    supports_callbacks = True

    def __init__(
        self,
        predictor: PredictorInterface | None = None,
        parallelism: int = PARALLELISM,
        team_name: str | None = None,
    ) -> None:
        self.predictor = predictor or DeterministicPredictor()
        
        super().__init__(parallelism=parallelism, team_name=team_name)

    def _process_workloads(self, workload_list: Sequence[workloads.All]):
        """Resolve queued workloads immediately using simulated results."""
        for workload in workload_list:
            if isinstance(workload, workloads.ExecuteTask):
                self._process_task_workload(workload)
            elif isinstance(workload, workloads.ExecuteCallback):
                self._process_callback_workload(workload)
            else:
                raise ValueError(f"SimulationExecutor does not know how to handle {type(workload).__name__}")

    def _process_task_workload(self, workload: workloads.ExecuteTask):
        ti_key = workload.ti.key
        self.queued_tasks.pop(ti_key, None)
        self.running.add(ti_key)

        outcome = self._get_task_outcome(workload)
        estimate = self._get_task_estimate(workload)
        info = {
            "simulated": True,
            "estimated_runtime": estimate.estimated_seconds,
            "confidence": estimate.confidence,
            "predicted_outcome": outcome.value,
        }

        self.log_task_event(
            event="simulation",
            extra=(
                f"predicted_outcome={outcome.value}, "
                f"estimated_runtime={estimate.estimated_seconds}s, "
                f"confidence={estimate.confidence}"
            ),
            ti_key=ti_key,
        )

        if outcome == PredictedOutcome.FAILURE:
            self.fail(ti_key, info=info)
        else:
            self.success(ti_key, info=info)

    def _process_callback_workload(self, workload: workloads.ExecuteCallback):
        callback_id = workload.callback.id
        self.queued_callbacks.pop(callback_id, None)
        self.event_buffer[callback_id] = (CallbackState.SUCCESS, {"simulated": True})

    def _get_task_estimate(self, workload: workloads.ExecuteTask) -> TaskRuntimeEstimate:
        operator_type = getattr(workload.ti, "operator", OperatorType.UNKNOWN)
        context = {
            "dag_id": workload.ti.dag_id,
            "run_id": workload.ti.run_id,
            "map_index": workload.ti.map_index,
        }
        return self.predictor.estimate_task(
            task_id=workload.ti.task_id,
            operator_type=operator_type,
            context=context,
        )

    def _get_task_outcome(self, workload: workloads.ExecuteTask) -> PredictedOutcome:
        predicted_outcome = getattr(workload.ti, "predicted_outcome", PredictedOutcome.SUCCESS.value)
        return self._check_outcome(predicted_outcome)

    @staticmethod
    def _check_outcome(predicted_outcome: Any) -> PredictedOutcome:
        if isinstance(predicted_outcome, PredictedOutcome):
            return predicted_outcome
        if isinstance(predicted_outcome, str):
            try:
                return PredictedOutcome(predicted_outcome)
            except ValueError:
                return PredictedOutcome.UNKNOWN
        return PredictedOutcome.UNKNOWN

    def terminate(self):
        """Drop queued/running in-memory state without affecting the DB."""
        self.queued_tasks.clear()
        self.queued_callbacks.clear()
        self.running.clear()

    def revoke_task(self, *, ti: TaskInstance):
        """Remove a simulated task from internal executor."""
        self.queued_tasks.pop(ti.key, None)
        self.running.discard(ti.key)
