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
"""
Critical-path computation for simulation simulation results.

This module calculates a simple longest-path over the DAG task dependency
graph using estimated runtimes. It produces a critical path, the edges along
that path, and the task with the longest duration on the path.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from airflow.api_fastapi.core_api.datamodels.simulation import CriticalPathResult

if TYPE_CHECKING:
    from airflow.api_fastapi.core_api.datamodels.simulation import TaskSimulationResponse


def get_critical_path(dag: Any, task_responses: list[TaskSimulationResponse]) -> CriticalPathResult:
    """Return a critical-path result from a DAG and task runtime estimates."""
    if not task_responses:
        return CriticalPathResult(
            critical_path=[],
            critical_edges=[],
            longest_task="",
        )

    estimates = {task.task_id: task.estimated_seconds for task in task_responses}
    task_ids = set(estimates)

    dag_task_dict = getattr(dag, "task_dict", {}) or {}
    successors: dict[str, set[str]] = {task_id: set() for task_id in task_ids}
    predecessors: dict[str, set[str]] = {task_id: set() for task_id in task_ids}

    for task_id in task_ids:
        task = dag_task_dict.get(task_id)
        if task is None:
            continue
        for downstream_id in getattr(task, "downstream_task_ids", set()):
            if downstream_id in task_ids:
                successors[task_id].add(downstream_id)
                predecessors[downstream_id].add(task_id)

    in_degree = {task_id: len(predecessors[task_id]) for task_id in task_ids}
    queue = deque(sorted(task_id for task_id, degree in in_degree.items() if degree == 0))
    if not queue:
        queue = deque(sorted(task_ids))

    longest_sum = {task_id: estimates[task_id] for task_id in task_ids}
    predecessor_on_longest: dict[str, str | None] = {task_id: None for task_id in task_ids}

    while queue:
        current = queue.popleft()
        current_sum = longest_sum[current]
        for successor in sorted(successors.get(current, [])):
            candidate_sum = current_sum + estimates[successor]
            if candidate_sum > longest_sum[successor]:
                longest_sum[successor] = candidate_sum
                predecessor_on_longest[successor] = current
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                queue.append(successor)

    end_task = max(task_ids, key=lambda task_id: (longest_sum[task_id], estimates[task_id], task_id))
    critical_path: list[str] = []
    while end_task is not None:
        critical_path.append(end_task)
        end_task = predecessor_on_longest[end_task]
    critical_path.reverse()

    longest_task = max(critical_path, key=lambda task_id: (estimates[task_id], task_id))
    critical_edges = [(critical_path[i], critical_path[i + 1]) for i in range(len(critical_path) - 1)]

    return CriticalPathResult(
        critical_path=critical_path,
        critical_edges=critical_edges,
        longest_task=longest_task,
    )
