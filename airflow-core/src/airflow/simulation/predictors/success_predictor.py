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
"""Historical success-rate predictor for tasks and DAGs."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from enum import Enum

from airflow.simulation.data.historical_data_extractor import (
    get_dag_run_state_history,
    get_task_state_history,
)

# Per-task success states. ``skipped`` and ``removed`` indicate the DAG ran
# normally — branching logic chose another path or the task was removed from
# the DAG since the run was created. Treating them as failures would make
# branching DAGs always score very low.
_TASK_SUCCESS_STATES: frozenset[str] = frozenset({"success", "skipped", "removed"})

# DAG-level success states. Only a fully-successful run counts; ``failed``
# is a clear failure, and in-flight states (``running``, ``queued``) are
# filtered upstream by the extractor.
_DAG_SUCCESS_STATES: frozenset[str] = frozenset({"success"})

_DEFAULT_LOOKBACK_DAYS: int = 30
_DEFAULT_MAX_RUNS: int = 100
_DEFAULT_MIN_RUNS: int = 3
_DEFAULT_PROBABILITY: float = 0.5
_DEFAULT_DECAY_LAMBDA: float = 0.1


class WeightingMethod(str, Enum):
    """How to weight historical runs by recency."""

    NONE = "none"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


def _compute_weights(
    num_runs: int,
    method: WeightingMethod,
    decay_lambda: float,
) -> list[float]:
    """
    Return weights for runs ordered newest-first.

    Index 0 is the most recent run; higher indices are older. Newer runs
    receive equal-or-greater weight than older runs.
    """
    if num_runs <= 0:
        return []
    if method == WeightingMethod.LINEAR:
        # Newest gets weight num_runs, oldest gets weight 1.
        return [float(num_runs - i) for i in range(num_runs)]
    if method == WeightingMethod.EXPONENTIAL:
        return [math.exp(-decay_lambda * i) for i in range(num_runs)]
    # WeightingMethod.NONE — uniform weights.
    return [1.0] * num_runs


def _weighted_success_rate(
    states: list[str],
    weights: list[float],
    success_states: frozenset[str],
) -> float:
    """
    Compute the weighted fraction of states that count as success.

    ``success_states`` lets callers distinguish between per-task success
    semantics (``skipped`` counts) and DAG-level semantics (only ``success``
    counts).
    """
    total = sum(weights)
    if total <= 0:
        return 0.0
    success = sum(weight for state, weight in zip(states, weights) if state in success_states)
    return success / total


class SuccessPredictor:
    """
    Predict success probability for tasks and DAGs from historical state data.

    Per-task probability is the (optionally weighted) fraction of historical
    TaskInstance runs that ended in a non-failure state — ``success``,
    ``skipped``, or ``removed``. DAG-level probability is computed
    independently from historical ``DagRun.state`` values (success vs failed),
    not by multiplying per-task probabilities — this matches "did the run
    finish in SUCCESS" and avoids geometric decay across many tasks.

    When fewer than ``min_runs`` historical executions exist, the predictor
    returns ``default_probability`` (0.5 by default — a neutral signal).

    Args:
        lookback_days: Only consider runs from the last *lookback_days* days.
            ``None`` disables the time filter.
        max_runs: Maximum number of recent runs to fetch per task.
        min_runs: Minimum runs required to compute a probability from data.
        default_probability: Returned when insufficient history exists. Must
            be in ``[0.0, 1.0]``.
        weighting: How to weight runs by recency. Defaults to ``NONE``.
        decay_lambda: Decay rate for exponential weighting. Ignored for
            other weighting modes.
    """

    def __init__(
        self,
        *,
        lookback_days: int | None = _DEFAULT_LOOKBACK_DAYS,
        max_runs: int = _DEFAULT_MAX_RUNS,
        min_runs: int = _DEFAULT_MIN_RUNS,
        default_probability: float = _DEFAULT_PROBABILITY,
        weighting: WeightingMethod = WeightingMethod.NONE,
        decay_lambda: float = _DEFAULT_DECAY_LAMBDA,
    ) -> None:
        if not 0.0 <= default_probability <= 1.0:
            raise ValueError("default_probability must be in [0.0, 1.0]")
        self.lookback_days = lookback_days
        self.max_runs = max_runs
        self.min_runs = max(min_runs, 1)
        self.default_probability = default_probability
        self.weighting = weighting
        self.decay_lambda = decay_lambda

    def _start_date(self) -> datetime | None:
        if self.lookback_days is None:
            return None
        return datetime.now(tz=timezone.utc) - timedelta(days=self.lookback_days)

    def predict_task_success(self, dag_id: str, task_id: str) -> float:
        """
        Return the success probability for a single task in ``[0.0, 1.0]``.

        Treats ``skipped`` and ``removed`` states as success — they indicate
        the DAG ran normally (e.g. branching steered around the task) and
        should not lower the task's score.
        """
        states = get_task_state_history(
            dag_id,
            task_id,
            start_date=self._start_date(),
            limit=self.max_runs,
        )

        if len(states) < self.min_runs:
            return self.default_probability

        weights = _compute_weights(len(states), self.weighting, self.decay_lambda)
        return _weighted_success_rate(states, weights, _TASK_SUCCESS_STATES)

    def predict_dag_success_rate(self, dag_id: str) -> float:
        """
        Return the DAG-level success probability in ``[0.0, 1.0]``.

        Computed from historical ``DagRun.state`` values rather than by
        multiplying per-task probabilities. This matches the user's actual
        question ("did the run finish in SUCCESS?") and avoids geometric
        decay from independent-task multiplication.
        """
        states = get_dag_run_state_history(
            dag_id,
            start_date=self._start_date(),
            limit=self.max_runs,
        )

        if len(states) < self.min_runs:
            return self.default_probability

        weights = _compute_weights(len(states), self.weighting, self.decay_lambda)
        return _weighted_success_rate(states, weights, _DAG_SUCCESS_STATES)

    def count_task_outcomes(self, dag_id: str, task_id: str) -> tuple[int, int, int]:
        """
        Return ``(total, success, failed)`` counts of historical task instances.

        Uses the same lookback window and limit as :meth:`predict_task_success`,
        so the counts reflect exactly the data the predictor sees. ``failed``
        counts both ``failed`` and ``upstream_failed`` states; the difference
        between ``total`` and ``success + failed`` is made up of other
        terminal states (``skipped``, ``removed``).
        """
        states = get_task_state_history(
            dag_id,
            task_id,
            start_date=self._start_date(),
            limit=self.max_runs,
        )
        total = len(states)
        success = sum(1 for state in states if state == "success")
        failed = sum(1 for state in states if state in {"failed", "upstream_failed"})
        return total, success, failed

    def predict_dag_success(
        self,
        dag_id: str,
        task_ids: list[str],
    ) -> tuple[float, dict[str, float]]:
        """
        Return ``(dag_probability, per_task_probabilities)``.

        DAG probability comes from :meth:`predict_dag_success_rate` (DagRun
        history). Per-task probabilities are computed independently from
        :meth:`predict_task_success` and exposed for the UI table — they no
        longer feed into the DAG-level number.
        """
        per_task = {
            task_id: self.predict_task_success(dag_id, task_id) for task_id in task_ids
        }
        dag_probability = self.predict_dag_success_rate(dag_id)
        return dag_probability, per_task
