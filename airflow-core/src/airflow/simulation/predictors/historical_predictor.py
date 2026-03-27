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
"""Historical data-based runtime predictor."""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from enum import Enum

from airflow.simulation.data.historical_data_extractor import get_historical_runtimes
from airflow.simulation.predictor_interface import (
    DeterministicPredictor,
    PredictorInterface,
    TaskRuntimeEstimate,
)

# Minimum confidence assigned to historical estimates.
_HISTORICAL_BASE_CONFIDENCE: float = 0.7
# Maximum confidence ceiling.
_HISTORICAL_MAX_CONFIDENCE: float = 0.95
# Default minimum number of runs required before using historical data.
_DEFAULT_MIN_RUNS: int = 3


class AggregationMethod(str, Enum):
    """Supported statistical aggregation methods."""

    MEDIAN = "median"
    MEAN = "mean"
    P90 = "p90"
    P95 = "p95"


def _percentile(data: list[float], pct: float) -> float:
    """Compute a percentile value from sorted data."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def _filter_outliers(durations: list[float], num_mad: float = 3.0) -> list[float]:
    """Remove outliers using the median absolute deviation (MAD).

    Unlike mean/stdev, the median and MAD are robust to outliers — a
    single extreme value cannot inflate the spread enough to hide itself.

    Values more than *num_mad* scaled MADs from the median are removed.
    Returns the original list unchanged when there are fewer than 3 data
    points or when the MAD is zero (all values are identical).
    """
    if len(durations) < 3:
        return durations
    med = statistics.median(durations)
    abs_devs = [abs(d - med) for d in durations]
    mad = statistics.median(abs_devs)
    if mad == 0:
        # All central values are identical; keep only those equal to the median.
        return [d for d in durations if d == med]
    # Scale factor 1.4826 makes MAD consistent with std dev for normal data.
    scaled_mad = mad * 1.4826
    return [d for d in durations if abs(d - med) <= num_mad * scaled_mad]


def _aggregate(durations: list[float], method: AggregationMethod) -> float:
    """Aggregate a list of durations using the specified method."""
    if method == AggregationMethod.MEDIAN:
        return statistics.median(durations)
    if method == AggregationMethod.MEAN:
        return statistics.mean(durations)
    if method == AggregationMethod.P90:
        return _percentile(durations, 90)
    if method == AggregationMethod.P95:
        return _percentile(durations, 95)
    return statistics.median(durations)


def _compute_confidence(sample_size: int) -> float:
    """Scale confidence based on how many data points were used.

    More data points → higher confidence, capped at
    :data:`_HISTORICAL_MAX_CONFIDENCE`.
    """
    # Simple logarithmic scaling: confidence grows with more samples but
    # quickly saturates.  At 3 samples we start at _HISTORICAL_BASE_CONFIDENCE
    # and approach _HISTORICAL_MAX_CONFIDENCE around 50+ samples.
    bonus = min((sample_size - _DEFAULT_MIN_RUNS) / 50.0, 1.0) * (
        _HISTORICAL_MAX_CONFIDENCE - _HISTORICAL_BASE_CONFIDENCE
    )
    return min(_HISTORICAL_BASE_CONFIDENCE + max(bonus, 0.0), _HISTORICAL_MAX_CONFIDENCE)


class HistoricalPredictor(PredictorInterface):
    """Predicts task runtime from historical execution data.

    Falls back to :class:`DeterministicPredictor` when insufficient
    history is available.

    Args:
        aggregation: The statistical method used to aggregate durations.
        min_runs: Minimum number of historical runs required.  Below this
            threshold the predictor falls back to the deterministic
            heuristic.
        max_runs: Maximum number of recent runs to fetch.
        lookback_days: Only consider runs from the last *lookback_days*
            days.  ``None`` means no time restriction.
        filter_outliers: When *True*, remove values beyond 3 standard
            deviations before aggregating.
    """

    def __init__(
        self,
        *,
        aggregation: AggregationMethod = AggregationMethod.MEDIAN,
        min_runs: int = _DEFAULT_MIN_RUNS,
        max_runs: int = 100,
        lookback_days: int | None = 30,
        filter_outliers: bool = True,
    ) -> None:
        self.aggregation = aggregation
        self.min_runs = max(min_runs, 1)
        self.max_runs = max_runs
        self.lookback_days = lookback_days
        self.filter_outliers_enabled = filter_outliers
        self._fallback = DeterministicPredictor()

    def estimate_task(
        self,
        task_id: str,
        operator_type: str,
        context: dict | None = None,
    ) -> TaskRuntimeEstimate:
        dag_id = (context or {}).get("dag_id", "")

        start_date = None
        if self.lookback_days is not None:
            start_date = datetime.now(tz=timezone.utc) - timedelta(days=self.lookback_days)

        runtimes = get_historical_runtimes(
            dag_id,
            task_id,
            start_date=start_date,
            limit=self.max_runs,
        )

        durations = [r.duration for r in runtimes if r.duration is not None]

        if len(durations) < self.min_runs:
            return self._fallback.estimate_task(task_id, operator_type, context)

        if self.filter_outliers_enabled:
            durations = _filter_outliers(durations)
            # After filtering we may have dropped below min_runs.
            if len(durations) < self.min_runs:
                return self._fallback.estimate_task(task_id, operator_type, context)

        estimated_seconds = _aggregate(durations, self.aggregation)

        return TaskRuntimeEstimate(
            task_id=task_id,
            operator_type=operator_type,
            estimated_seconds=int(round(estimated_seconds)),
            confidence=_compute_confidence(len(durations)),
        )
