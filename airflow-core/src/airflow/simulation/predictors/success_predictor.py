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

from airflow.simulation.data.historical_data_extractor import get_task_state_history

# Only ``success`` counts as a success outcome — everything else (failed,
# upstream_failed, skipped, ...) reduces the probability.
_SUCCESS_STATE: str = "success"

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


def _weighted_success_rate(states: list[str], weights: list[float]) -> float:
    """Compute the weighted fraction of states equal to ``success``."""
    total = sum(weights)
    if total <= 0:
        return 0.0
    success = sum(weight for state, weight in zip(states, weights) if state == _SUCCESS_STATE)
    return success / total


class SuccessPredictor:
    """
    Predict success probability for tasks and DAGs from historical state data.

    The probability is computed as the (optionally weighted) fraction of
    historical runs in the ``success`` state. DAG-level probability assumes
    independent task outcomes — ``P(DAG) = product(P(task_i))`` — which is
    conservative; correlated failure modes (e.g. shared upstream) make the
    real DAG-level probability higher.

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

    def predict_task_success(self, dag_id: str, task_id: str) -> float:
        """Return the success probability for a single task in ``[0.0, 1.0]``."""
        start_date = None
        if self.lookback_days is not None:
            start_date = datetime.now(tz=timezone.utc) - timedelta(days=self.lookback_days)

        states = get_task_state_history(
            dag_id,
            task_id,
            start_date=start_date,
            limit=self.max_runs,
        )

        if len(states) < self.min_runs:
            return self.default_probability

        weights = _compute_weights(len(states), self.weighting, self.decay_lambda)
        return _weighted_success_rate(states, weights)

    def predict_dag_success(
        self,
        dag_id: str,
        task_ids: list[str],
    ) -> tuple[float, dict[str, float]]:
        """
        Return ``(dag_probability, per_task_probabilities)``.

        Each task's probability is computed independently; the DAG-level
        probability is the product, treating tasks as independent. Returns
        ``(default_probability, {})`` when ``task_ids`` is empty.
        """
        if not task_ids:
            return self.default_probability, {}

        per_task = {
            task_id: self.predict_task_success(dag_id, task_id) for task_id in task_ids
        }
        dag_probability = math.prod(per_task.values())
        return dag_probability, per_task
