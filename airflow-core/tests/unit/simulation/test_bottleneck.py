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
"""Tests for bottleneck (longest_task) extraction inside ``get_critical_path``.

The "bottleneck" is the single longest task on the critical path. It is
populated as ``CriticalPathResult.longest_task`` by ``get_critical_path``;
these tests exercise the extraction rule independently of overall path
correctness (which is covered in ``test_critical_path``).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from airflow.api_fastapi.core_api.datamodels.simulation import TaskSimulationResponse
from airflow.simulation.critical_path import get_critical_path


def _task(task_id: str, seconds: int) -> TaskSimulationResponse:
    return TaskSimulationResponse(
        task_id=task_id,
        operator_type="PythonOperator",
        estimated_seconds=seconds,
        confidence=1.0,
    )


def _dag(edges: dict[str, list[str]]) -> SimpleNamespace:
    referenced = set(edges) | {downstream for downstreams in edges.values() for downstream in downstreams}
    task_dict = {
        task_id: SimpleNamespace(
            task_id=task_id,
            downstream_task_ids=set(edges.get(task_id, [])),
        )
        for task_id in referenced
    }
    return SimpleNamespace(task_dict=task_dict)


@pytest.mark.parametrize(
    ("label", "edges", "runtimes", "expected_bottleneck"),
    [
        # Single task — it's trivially its own bottleneck.
        (
            "single_task",
            {"a": []},
            {"a": 7},
            "a",
        ),
        # Linear chain — bottleneck is the longest task on the path.
        (
            "linear_chain_picks_max_on_path",
            {"a": ["b"], "b": ["c"], "c": []},
            {"a": 1, "b": 100, "c": 10},
            "b",
        ),
        # Off-path task with the largest single runtime must NOT become the
        # bottleneck. Here "x" is 10s but lives on a shorter parallel branch
        # (a→x = 11) than the main chain (a→b→c→d = 12). Bottleneck is taken
        # from the critical path itself, never from the full response set.
        (
            "off_path_task_is_not_a_bottleneck",
            {"a": ["b", "x"], "b": ["c"], "c": ["d"], "d": [], "x": []},
            {"a": 1, "b": 5, "c": 5, "d": 1, "x": 10},
            # critical path is [a, b, c, d]; bottleneck ties b/c, lex max → "c".
            "c",
        ),
        # Tie between two tasks on the path — ``max(..., key=(estimate, task_id))``
        # breaks ties by lexically larger task_id.
        (
            "tied_runtimes_break_by_task_id",
            {"a": ["b"], "b": ["c"], "c": []},
            {"a": 5, "b": 5, "c": 5},
            "c",
        ),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_bottleneck_extraction(label, edges, runtimes, expected_bottleneck):
    dag = _dag(edges)
    tasks = [_task(tid, seconds) for tid, seconds in runtimes.items()]

    result = get_critical_path(dag, tasks)

    assert result.longest_task == expected_bottleneck, (
        f"[{label}] expected {expected_bottleneck!r} on path {result.critical_path}, "
        f"got {result.longest_task!r}"
    )
    # Sanity invariant: the bottleneck is always on the critical path itself.
    assert result.longest_task in result.critical_path


def test_empty_input_yields_empty_bottleneck():
    """Empty task list should produce an empty bottleneck, not raise."""
    result = get_critical_path(_dag({}), [])

    assert result.longest_task == ""
    assert result.critical_path == []
