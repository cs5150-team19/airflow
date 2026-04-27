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
"""Critical-path computation for simulation simulation results.

This module calculates a simple longest-path over the DAG task dependency
graph using estimated runtimes. It produces a critical path, the edges along
that path, and the task with the longest duration on the path.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from airflow.api_fastapi.core_api.datamodels.simulation import CriticalPathResult

if TYPE_CHECKING:
    from airflow.api_fastapi.core_api.datamodels.simulation import TaskSimulationResponse


def get_critical_path(
    dag: DAG,
    task_responses: list[TaskSimulationResponse],
) -> CriticalPathResult:
    # --- Build lookup: task_id -> estimated_seconds ---
    duration: dict[str, float] = {t.task_id: t.estimated_seconds for t in task_responses}

    # --- Pull dependency graph from Airflow DAG ---
    downstream: dict[str, list[str]] = defaultdict(list)
    upstream: dict[str, list[str]] = defaultdict(list)
    all_task_ids: set[str] = {t.task_id for t in task_responses}

    for task_id in all_task_ids:
        task = dag.get_task(task_id)
        for ds in task.downstream_task_ids:
            if ds in all_task_ids:
                downstream[task_id].append(ds)
                upstream[ds].append(task_id)

    # --- Topological sort (Kahn's algorithm) ---
    in_degree = {t: len(upstream[t]) for t in all_task_ids}
    queue = deque([t for t in all_task_ids if in_degree[t] == 0])
    topo_order: list[str] = []

    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for ds in downstream[node]:
            in_degree[ds] -= 1
            if in_degree[ds] == 0:
                queue.append(ds)

    if len(topo_order) != len(all_task_ids):
        raise ValueError("DAG contains a cycle — cannot compute critical path")

    # --- Forward pass: Earliest Start (ES) ---
    es: dict[str, float] = {t: 0.0 for t in all_task_ids}
    for node in topo_order:
        for ds in downstream[node]:
            es[ds] = max(es[ds], es[node] + duration[node])

    # --- Backward pass: Latest Start (LS) ---
    max_es = max(es[t] + duration[t] for t in all_task_ids)
    ls: dict[str, float] = {t: max_es - duration[t] for t in all_task_ids}
    for node in reversed(topo_order):
        for us in upstream[node]:
            ls[us] = min(ls[us], ls[node] - duration[us])

    # --- Slack & critical path nodes ---
    slack: dict[str, float] = {t: ls[t] - es[t] for t in all_task_ids}
    on_critical_path: set[str] = {t for t in all_task_ids if abs(slack[t]) < 1e-9}

    # --- Order critical path nodes by ES ---
    critical_path = sorted(on_critical_path, key=lambda t: es[t])

    # --- Longest task by estimated_seconds ---
    longest_task: str = max(task_responses, key=lambda t: t.estimated_seconds).task_id

    # --- Parallel edges ---
    all_edges = [(u, ds) for u in all_task_ids for ds in downstream[u]]
    parallel_edges = [
        (u, ds) for u, ds in all_edges
        if u not in on_critical_path or ds not in on_critical_path
    ]

    return CriticalPathResult(
        critical_path=critical_path,
        parallel_edges=parallel_edges,
        longest_task=longest_task,
    )
