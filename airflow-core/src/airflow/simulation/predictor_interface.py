from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import final

class OperatorType(str, Enum):
    PYTHON = "PythonOperator"
    BASH = "BashOperator"
    MYSQL = "MySqlOperator"
    POSTGRES = "PostgresOperator"
    S3_KEY = "S3KeySensor"
    UNKNOWN = "Unknown"

_OPERATOR_RUNTIME_SECONDS: dict[str, int] = {
    OperatorType.PYTHON: 30,
    OperatorType.BASH: 10,
    OperatorType.MYSQL: 60,
    OperatorType.POSTGRES: 60,
    OperatorType.S3_KEY: 300,
    OperatorType.UNKNOWN: 30
}

# Confidence value for the deterministic heuristic predictor (no historical data)
_DETERMINISTIC_CONFIDENCE: float = 0.5

class PredictedOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"

@dataclass
class TaskRuntimeEstimate:
    task_id: str
    operator_type: str
    estimated_seconds: int
    confidence: float  # 0.0 to 1.0

@dataclass
class SimulationEstimate:
    dag_id: str
    task_estimates: list[TaskRuntimeEstimate]
    total_task_seconds: int
    predicted_outcome: PredictedOutcome

class PredictorInterface(ABC):
    """
    Base class for all runtime predictors.

    Sprint 2: DeterministicPredictor (constant-based heuristic)
    Final Implementation: HistoricalPredictor, InputSizePredictor
    """

    @abstractmethod
    def estimate_task(
        self,
        task_id: str,
        operator_type: str,
        context: dict | None = None
    ) -> TaskRuntimeEstimate:
        """
        Return a runtime estimate for a single task.
        Subclasses must implement this method.

        Args:
            task_id: Unique identifier for the task.
            operator_type: One of the OperatorType enum values.
            context: Optional metadata for the estimate. Supported keys vary
                by subclass — e.g. HistoricalPredictor may use
                {"run_history": [...]} and InputSizePredictor may use
                {"input_bytes": int}.
        """
        ...

    @final
    def estimate_dag(
        self,
        dag_id: str,
        tasks: list[dict],
        context: dict | None = None
    ) -> SimulationEstimate:
        """
        Return a full simulation estimate for a DAG.

        'tasks' is a list of dicts with at minimum:
            {"task_id": str, "operator_type": str}

        'context' is passed through to each estimate_task call.
        """
        task_estimates = [
            self.estimate_task(
                t["task_id"],
                t.get("operator_type", OperatorType.UNKNOWN),
                context
            )
            for t in tasks
        ]

        total_seconds = sum(e.estimated_seconds for e in task_estimates)

        return SimulationEstimate(
            dag_id=dag_id,
            task_estimates=task_estimates,
            total_task_seconds=total_seconds,
            predicted_outcome=PredictedOutcome.SUCCESS  # TODO: replace with model prediction in future implementation
        )

# Sprint 2 Implementation
class DeterministicPredictor(PredictorInterface):
    """
    Estimates runtime using a constant-based heuristic.
    No historical data required.
    """

    def estimate_task(
        self,
        task_id: str,
        operator_type: str,
        context: dict | None = None
    ) -> TaskRuntimeEstimate:
        seconds = _OPERATOR_RUNTIME_SECONDS.get(operator_type, 30) # Default when operator_type is not found
        return TaskRuntimeEstimate(
            task_id=task_id,
            operator_type=operator_type,
            estimated_seconds=seconds,
            confidence=_DETERMINISTIC_CONFIDENCE
        )