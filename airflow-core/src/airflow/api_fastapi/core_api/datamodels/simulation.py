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
from __future__ import annotations

from airflow.api_fastapi.core_api.base import BaseModel


class TaskSimulationResponse(BaseModel):
    """Response for a single task simulation estimate."""

    task_id: str
    operator_type: str
    estimated_seconds: float
    confidence: float
    # Counts of historical (dag_id, task_id) entries the predictors used —
    # same lookback window as the SuccessPredictor. ``historical_total`` is the
    # number of records available; ``historical_success`` and
    # ``historical_failed`` count the ``success`` and ``failed``/``upstream_failed``
    # subsets. Other terminal states (``skipped``, ``removed``) are included in
    # the total but not in either subset, so the two columns will not generally
    # add up to the total.
    historical_total: int = 0
    historical_success: int = 0
    historical_failed: int = 0


class CriticalPathResult(BaseModel):
    """Critical-path info for a DAG simulation."""

    critical_path: list[str]
    critical_edges: list[tuple[str, str]]
    longest_task: str


class SimulationResponse(BaseModel):
    """Response for a DAG simulation."""

    simulation_id: str
    dag_id: str
    task_estimates: list[TaskSimulationResponse]
    total_estimated_seconds: float
    critical_path: CriticalPathResult
    predicted_outcome: str
    # Probability in [0.0, 1.0] that every task in the DAG would succeed,
    # computed by SuccessPredictor from historical task-state data.
    success_probability: float
    # Per-task success probabilities keyed by task_id.
    task_success_probabilities: dict[str, float]
