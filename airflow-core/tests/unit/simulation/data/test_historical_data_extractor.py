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
"""Tests for the historical data extractor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from airflow.simulation.data.historical_data_extractor import (
    DEFAULT_LIMIT,
    HistoricalRuntime,
    get_historical_runtimes,
)
from airflow.utils.state import TaskInstanceState

pytestmark = pytest.mark.db_test

DAG_ID = "test_dag"
TASK_ID = "test_task"


def _create_ti(dag_maker, session, *, dag_id=DAG_ID, task_id=TASK_ID, run_id, state, start, duration):
    """Helper to create a task instance with specified properties."""
    from airflow.providers.standard.operators.empty import EmptyOperator

    with dag_maker(dag_id, session=session):
        EmptyOperator(task_id=task_id)
    dr = dag_maker.create_dagrun(run_id=run_id, logical_date=start, run_after=start)
    ti = dr.get_task_instance(task_id=task_id, session=session)
    ti.state = state
    ti.start_date = start
    ti.duration = duration
    ti.end_date = start + timedelta(seconds=duration) if duration else None
    session.flush()
    return ti


class TestGetHistoricalRuntimes:
    """Tests for get_historical_runtimes."""

    def test_basic_retrieval(self, dag_maker, session):
        """Successful runs are returned with correct fields."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            run_id="run1", state=TaskInstanceState.SUCCESS.value,
            start=start, duration=10.0,
        )

        results = get_historical_runtimes(DAG_ID, TASK_ID, session=session)

        assert len(results) == 1
        r = results[0]
        assert r.run_id == "run1"
        assert r.duration == 10.0
        assert r.start_date == start
        assert r.end_date == start + timedelta(seconds=10)
        assert r.state == TaskInstanceState.SUCCESS.value

    def test_empty_history(self, dag_maker, session):
        """Returns empty list for a task with no history."""
        results = get_historical_runtimes("nonexistent_dag", "nonexistent_task", session=session)
        assert results == []

    def test_default_filters_success_only(self, dag_maker, session):
        """By default, only successful runs are returned."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            run_id="success_run", state=TaskInstanceState.SUCCESS.value,
            start=start, duration=5.0,
        )
        _create_ti(
            dag_maker, session,
            run_id="failed_run", state=TaskInstanceState.FAILED.value,
            start=start + timedelta(hours=1), duration=3.0,
        )

        results = get_historical_runtimes(DAG_ID, TASK_ID, session=session)

        assert len(results) == 1
        assert results[0].run_id == "success_run"

    def test_filter_by_state(self, dag_maker, session):
        """Explicit state filter returns matching runs."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            run_id="success_run", state=TaskInstanceState.SUCCESS.value,
            start=start, duration=5.0,
        )
        _create_ti(
            dag_maker, session,
            run_id="failed_run", state=TaskInstanceState.FAILED.value,
            start=start + timedelta(hours=1), duration=3.0,
        )

        results = get_historical_runtimes(
            DAG_ID, TASK_ID,
            states=[TaskInstanceState.FAILED.value],
            session=session,
        )

        assert len(results) == 1
        assert results[0].run_id == "failed_run"

    def test_filter_multiple_states(self, dag_maker, session):
        """Multiple states in filter returns all matching runs."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            run_id="success_run", state=TaskInstanceState.SUCCESS.value,
            start=start, duration=5.0,
        )
        _create_ti(
            dag_maker, session,
            run_id="failed_run", state=TaskInstanceState.FAILED.value,
            start=start + timedelta(hours=1), duration=3.0,
        )

        results = get_historical_runtimes(
            DAG_ID, TASK_ID,
            states=[TaskInstanceState.SUCCESS.value, TaskInstanceState.FAILED.value],
            session=session,
        )

        assert len(results) == 2

    def test_only_failed_runs(self, dag_maker, session):
        """Task with only failed runs returns empty with default state filter."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            run_id="failed1", state=TaskInstanceState.FAILED.value,
            start=start, duration=2.0,
        )
        _create_ti(
            dag_maker, session,
            run_id="failed2", state=TaskInstanceState.FAILED.value,
            start=start + timedelta(hours=1), duration=1.0,
        )

        results = get_historical_runtimes(DAG_ID, TASK_ID, session=session)
        assert results == []

    def test_date_range_filter(self, dag_maker, session):
        """Start and end date filters narrow the result set."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            _create_ti(
                dag_maker, session,
                run_id=f"run_{i}", state=TaskInstanceState.SUCCESS.value,
                start=base + timedelta(days=i), duration=10.0,
            )

        results = get_historical_runtimes(
            DAG_ID, TASK_ID,
            start_date=base + timedelta(days=1),
            end_date=base + timedelta(days=3),
            session=session,
        )

        run_ids = {r.run_id for r in results}
        assert run_ids == {"run_1", "run_2", "run_3"}

    def test_start_date_filter_only(self, dag_maker, session):
        """Only start_date filter returns runs from that date onward."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            _create_ti(
                dag_maker, session,
                run_id=f"run_{i}", state=TaskInstanceState.SUCCESS.value,
                start=base + timedelta(days=i), duration=10.0,
            )

        results = get_historical_runtimes(
            DAG_ID, TASK_ID,
            start_date=base + timedelta(days=1),
            session=session,
        )

        run_ids = {r.run_id for r in results}
        assert run_ids == {"run_1", "run_2"}

    def test_ordering_most_recent_first(self, dag_maker, session):
        """Results are ordered by start_date descending."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            _create_ti(
                dag_maker, session,
                run_id=f"run_{i}", state=TaskInstanceState.SUCCESS.value,
                start=base + timedelta(days=i), duration=10.0,
            )

        results = get_historical_runtimes(DAG_ID, TASK_ID, session=session)

        assert [r.run_id for r in results] == ["run_2", "run_1", "run_0"]

    def test_limit(self, dag_maker, session):
        """Limit caps the number of returned records."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            _create_ti(
                dag_maker, session,
                run_id=f"run_{i}", state=TaskInstanceState.SUCCESS.value,
                start=base + timedelta(days=i), duration=10.0,
            )

        results = get_historical_runtimes(DAG_ID, TASK_ID, limit=2, session=session)

        assert len(results) == 2
        # Most recent first
        assert results[0].run_id == "run_4"
        assert results[1].run_id == "run_3"

    def test_offset(self, dag_maker, session):
        """Offset skips the specified number of records."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(5):
            _create_ti(
                dag_maker, session,
                run_id=f"run_{i}", state=TaskInstanceState.SUCCESS.value,
                start=base + timedelta(days=i), duration=10.0,
            )

        results = get_historical_runtimes(DAG_ID, TASK_ID, limit=2, offset=2, session=session)

        assert len(results) == 2
        assert results[0].run_id == "run_2"
        assert results[1].run_id == "run_1"

    def test_limit_capped_at_default(self, dag_maker, session):
        """Limit values above DEFAULT_LIMIT are capped."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            run_id="run_0", state=TaskInstanceState.SUCCESS.value,
            start=base, duration=10.0,
        )

        # Should not raise, just cap at DEFAULT_LIMIT
        results = get_historical_runtimes(DAG_ID, TASK_ID, limit=DEFAULT_LIMIT + 500, session=session)
        assert len(results) == 1

    def test_negative_limit_becomes_one(self, dag_maker, session):
        """Negative limit is clamped to 1."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            _create_ti(
                dag_maker, session,
                run_id=f"run_{i}", state=TaskInstanceState.SUCCESS.value,
                start=base + timedelta(days=i), duration=10.0,
            )

        results = get_historical_runtimes(DAG_ID, TASK_ID, limit=-5, session=session)
        assert len(results) == 1

    def test_negative_offset_becomes_zero(self, dag_maker, session):
        """Negative offset is clamped to 0."""
        base = datetime(2025, 1, 1, tzinfo=timezone.utc)
        for i in range(3):
            _create_ti(
                dag_maker, session,
                run_id=f"run_{i}", state=TaskInstanceState.SUCCESS.value,
                start=base + timedelta(days=i), duration=10.0,
            )

        results = get_historical_runtimes(DAG_ID, TASK_ID, offset=-10, session=session)
        assert len(results) == 3

    def test_isolates_by_dag_id(self, dag_maker, session):
        """Only returns task instances for the specified dag_id."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            dag_id="dag_a", run_id="run_a",
            state=TaskInstanceState.SUCCESS.value,
            start=start, duration=10.0,
        )
        _create_ti(
            dag_maker, session,
            dag_id="dag_b", run_id="run_b",
            state=TaskInstanceState.SUCCESS.value,
            start=start + timedelta(hours=1), duration=20.0,
        )

        results = get_historical_runtimes("dag_a", TASK_ID, session=session)

        assert len(results) == 1
        assert results[0].run_id == "run_a"

    def test_isolates_by_task_id(self, dag_maker, session):
        """Only returns instances for the specified task_id."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        with dag_maker(DAG_ID, session=session):
            from airflow.providers.standard.operators.empty import EmptyOperator

            EmptyOperator(task_id="task_a")
            EmptyOperator(task_id="task_b")
        dr = dag_maker.create_dagrun(run_id="run1")
        ti_a = dr.get_task_instance(task_id="task_a", session=session)
        ti_a.state = TaskInstanceState.SUCCESS.value
        ti_a.start_date = start
        ti_a.duration = 10.0
        ti_a.end_date = start + timedelta(seconds=10)

        ti_b = dr.get_task_instance(task_id="task_b", session=session)
        ti_b.state = TaskInstanceState.SUCCESS.value
        ti_b.start_date = start
        ti_b.duration = 20.0
        ti_b.end_date = start + timedelta(seconds=20)
        session.flush()

        results = get_historical_runtimes(DAG_ID, "task_a", session=session)

        assert len(results) == 1
        assert results[0].duration == 10.0

    def test_null_duration(self, dag_maker, session):
        """Handles task instances with null duration gracefully."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            run_id="run_null", state=TaskInstanceState.SUCCESS.value,
            start=start, duration=None,
        )

        results = get_historical_runtimes(DAG_ID, TASK_ID, session=session)

        assert len(results) == 1
        assert results[0].duration is None
        assert results[0].end_date is None

    def test_returns_historical_runtime_dataclass(self, dag_maker, session):
        """Results are HistoricalRuntime dataclass instances."""
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        _create_ti(
            dag_maker, session,
            run_id="run1", state=TaskInstanceState.SUCCESS.value,
            start=start, duration=10.0,
        )

        results = get_historical_runtimes(DAG_ID, TASK_ID, session=session)

        assert isinstance(results[0], HistoricalRuntime)
