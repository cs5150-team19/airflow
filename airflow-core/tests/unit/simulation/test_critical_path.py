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
"""Tests for ``airflow.simulation.critical_path.get_critical_path``."""

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
    """Build a fake DAG with ``task_dict``/``downstream_task_ids`` duck-typing.

    ``edges`` maps a task_id to its downstream task_ids. Tasks referenced only as
    downstreams are inferred so callers don't have to list every task twice.
    """
    referenced = set(edges) | {downstream for downstreams in edges.values() for downstream in downstreams}
    task_dict = {
        task_id: SimpleNamespace(
            task_id=task_id,
            downstream_task_ids=set(edges.get(task_id, [])),
        )
        for task_id in referenced
    }
    return SimpleNamespace(task_dict=task_dict)


class TestEmptyAndTrivial:
    def test_empty_task_responses_returns_empty_result(self):
        result = get_critical_path(_dag({}), [])

        assert result.critical_path == []
        assert result.critical_edges == []
        assert result.longest_task == ""

    def test_single_task_is_its_own_path(self):
        result = get_critical_path(_dag({"a": []}), [_task("a", 7)])

        assert result.critical_path == ["a"]
        assert result.critical_edges == []
        assert result.longest_task == "a"


class TestLinearChain:
    def test_linear_chain_returns_full_path(self):
        # a -> b -> c, runtimes 1, 2, 3
        dag = _dag({"a": ["b"], "b": ["c"], "c": []})
        tasks = [_task("a", 1), _task("b", 2), _task("c", 3)]

        result = get_critical_path(dag, tasks)

        assert result.critical_path == ["a", "b", "c"]
        assert result.critical_edges == [("a", "b"), ("b", "c")]
        assert result.longest_task == "c"

    def test_linear_chain_longest_task_is_largest_on_path(self):
        # middle node is largest, even though it isn't the terminal task
        dag = _dag({"a": ["b"], "b": ["c"], "c": []})
        tasks = [_task("a", 1), _task("b", 100), _task("c", 1)]

        result = get_critical_path(dag, tasks)

        assert result.critical_path == ["a", "b", "c"]
        assert result.longest_task == "b"


class TestBranchingAndConverging:
    def test_parallel_branches_take_longer_branch(self):
        # a -> b -> d  (b=10)
        # a -> c -> d  (c=1)
        # critical path must go through b, not c.
        dag = _dag({"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []})
        tasks = [_task("a", 1), _task("b", 10), _task("c", 1), _task("d", 1)]

        result = get_critical_path(dag, tasks)

        assert result.critical_path == ["a", "b", "d"]
        assert result.critical_edges == [("a", "b"), ("b", "d")]

    def test_parallel_branches_use_max_not_sum(self):
        # If we summed instead of taking max, total would be 1+5+5+1=12.
        # Correct longest path is 1+5+1=7.
        dag = _dag({"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []})
        tasks = [_task("a", 1), _task("b", 5), _task("c", 5), _task("d", 1)]

        result = get_critical_path(dag, tasks)

        assert len(result.critical_path) == 3  # not 4
        assert result.critical_path[0] == "a"
        assert result.critical_path[-1] == "d"

    def test_converging_dag_picks_longest_predecessor(self):
        # two roots feeding a single sink: a=10, b=1, both -> c
        dag = _dag({"a": ["c"], "b": ["c"], "c": []})
        tasks = [_task("a", 10), _task("b", 1), _task("c", 1)]

        result = get_critical_path(dag, tasks)

        assert result.critical_path == ["a", "c"]
        assert result.longest_task == "a"


class TestEdgesAndTieBreaking:
    def test_critical_edges_are_consecutive_pairs_of_path(self):
        dag = _dag({"a": ["b"], "b": ["c"], "c": ["d"], "d": []})
        tasks = [_task("a", 1), _task("b", 1), _task("c", 1), _task("d", 1)]

        result = get_critical_path(dag, tasks)

        expected = list(zip(result.critical_path, result.critical_path[1:]))
        assert result.critical_edges == expected

    def test_tied_parallel_branches_resolve_deterministically(self):
        # b and c are identical-runtime parallel branches feeding d.
        # Two ties are at play:
        #   - During pred propagation, the first predecessor to claim the max wins
        #     (strict ``>``), and successors are walked in sorted order, so "b"
        #     wins over "c" for d's predecessor.
        #   - The final ``end_task`` tie-break is ``(longest_sum, estimates, task_id)``,
        #     which only matters when multiple terminal tasks tie.
        # Pinning current behavior so a regression here surfaces a deliberate change.
        dag = _dag({"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []})
        tasks = [_task("a", 1), _task("b", 5), _task("c", 5), _task("d", 1)]

        result = get_critical_path(dag, tasks)

        assert result.critical_path == ["a", "b", "d"]
        # Importantly, repeated calls return the same path (no nondeterminism).
        assert get_critical_path(dag, tasks).critical_path == result.critical_path


class TestDefensiveCases:
    def test_task_in_response_but_missing_from_dag_task_dict(self):
        # "orphan" task is in the response set but not in the DAG; should be
        # treated as an isolated node, not crash.
        dag = _dag({"a": ["b"], "b": []})
        tasks = [_task("a", 1), _task("b", 2), _task("orphan", 100)]

        result = get_critical_path(dag, tasks)

        # orphan has the highest standalone estimate, so it wins as a 1-node path
        assert result.critical_path == ["orphan"]
        assert result.longest_task == "orphan"

    def test_dag_without_task_dict_attribute_treats_all_tasks_isolated(self):
        # No `task_dict` attribute at all → no edges discovered.
        bare_dag = SimpleNamespace()
        tasks = [_task("a", 1), _task("b", 5), _task("c", 3)]

        result = get_critical_path(bare_dag, tasks)

        # With no edges, every task is its own component; longest single task wins.
        assert result.critical_path == ["b"]
        assert result.critical_edges == []
        assert result.longest_task == "b"

    def test_only_edges_within_response_set_are_used(self):
        # DAG references a downstream that isn't in the response → that edge is dropped.
        dag = _dag({"a": ["b", "ghost"], "b": []})
        tasks = [_task("a", 1), _task("b", 2)]

        result = get_critical_path(dag, tasks)

        assert "ghost" not in result.critical_path
        assert result.critical_path == ["a", "b"]


@pytest.mark.parametrize(
    ("edges", "runtimes", "expected_path"),
    [
        # linear
        ({"a": ["b"], "b": []}, {"a": 1, "b": 2}, ["a", "b"]),
        # diamond — top branch (b=5) longer than bottom (c=2)
        (
            {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []},
            {"a": 1, "b": 5, "c": 2, "d": 1},
            ["a", "b", "d"],
        ),
        # 3-wide parallel — middle branch (m=10) longest
        (
            {"a": ["x", "m", "y"], "x": ["z"], "m": ["z"], "y": ["z"], "z": []},
            {"a": 1, "x": 1, "m": 10, "y": 1, "z": 1},
            ["a", "m", "z"],
        ),
    ],
)
def test_path_length_across_topologies(edges, runtimes, expected_path):
    dag = _dag(edges)
    tasks = [_task(tid, secs) for tid, secs in runtimes.items()]

    result = get_critical_path(dag, tasks)

    assert result.critical_path == expected_path
