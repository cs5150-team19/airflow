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
"""Stub critical-path computation for simulation results.

Real implementation is tracked as Story D (bottleneck detection / critical path
via topological sort + dynamic programming). Until that lands, this module
returns an empty CriticalPathResult so the simulation API endpoint can boot
and return non-critical-path fields correctly.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from airflow.api_fastapi.core_api.datamodels.simulation import CriticalPathResult

if TYPE_CHECKING:
    from airflow.api_fastapi.core_api.datamodels.simulation import TaskSimulationResponse


def get_critical_path(dag: Any, task_responses: list[TaskSimulationResponse]) -> CriticalPathResult:
    """Return a placeholder critical-path result.

    TODO: replace with real critical-path + bottleneck algorithm (Story D).
    Current behavior: empty path/edges, longest_task set to the first estimate
    as a harmless non-empty default.
    """
    longest_task = task_responses[0].task_id if task_responses else ""
    return CriticalPathResult(
        critical_path=[],
        critical_edges=[],
        longest_task=longest_task,
    )
