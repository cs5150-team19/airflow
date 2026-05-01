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
"""Historical task runtime data extraction from the Airflow metadata database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from airflow.models.dagrun import DagRun
from airflow.models.taskinstance import TaskInstance
from airflow.utils.session import NEW_SESSION, provide_session
from airflow.utils.state import TaskInstanceState

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Default limit for historical query results.
DEFAULT_LIMIT: int = 1000


@dataclass(frozen=True)
class HistoricalRuntime:
    """A single historical task execution record."""

    run_id: str
    duration: float | None
    start_date: datetime | None
    end_date: datetime | None
    state: str | None


@provide_session
def get_historical_runtimes(
    dag_id: str,
    task_id: str,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    states: list[str] | None = None,
    dag_version_id: UUID | None = None,
    exclude_simulations: bool = True,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    session: Session = NEW_SESSION,
) -> list[HistoricalRuntime]:
    """
    Retrieve historical runtimes for a specific task in a DAG.

    Args:
        dag_id: The DAG identifier.
        task_id: The task identifier.
        start_date: Only include runs that started on or after this datetime.
        end_date: Only include runs that started on or before this datetime.
        states: Task states to include. Defaults to ``["success"]`` when *None*.
        dag_version_id: Filter to a specific DAG version when provided.
        exclude_simulations: When *True*, exclude rows where ``is_simulation`` is set.
            Requires the ``is_simulation`` column to be present on :class:`TaskInstance`.
        limit: Maximum number of records to return. Capped at :data:`DEFAULT_LIMIT`.
        offset: Number of records to skip for pagination.
        session: SQLAlchemy session (provided by ``@provide_session``).

    Returns:
        A list of :class:`HistoricalRuntime` records ordered by ``start_date``
        descending (most recent first).  Returns an empty list when no matching
        records exist.
    """
    if states is None:
        states = [TaskInstanceState.SUCCESS.value]

    limit = min(max(limit, 1), DEFAULT_LIMIT)
    offset = max(offset, 0)

    stmt = select(
        TaskInstance.run_id,
        TaskInstance.duration,
        TaskInstance.start_date,
        TaskInstance.end_date,
        TaskInstance.state,
    ).where(
        TaskInstance.dag_id == dag_id,
        TaskInstance.task_id == task_id,
        TaskInstance.state.in_(states),
    )

    if start_date is not None:
        stmt = stmt.where(TaskInstance.start_date >= start_date)

    if end_date is not None:
        stmt = stmt.where(TaskInstance.start_date <= end_date)

    if dag_version_id is not None:
        stmt = stmt.where(TaskInstance.dag_version_id == dag_version_id)

    if exclude_simulations and hasattr(TaskInstance, "is_simulation"):
        stmt = stmt.where(TaskInstance.is_simulation.is_(False))

    stmt = stmt.order_by(TaskInstance.start_date.desc()).limit(limit).offset(offset)

    rows = session.execute(stmt).all()

    return [
        HistoricalRuntime(
            run_id=row.run_id,
            duration=row.duration,
            start_date=row.start_date,
            end_date=row.end_date,
            state=row.state,
        )
        for row in rows
    ]


@provide_session
def get_historical_runtimes_by_operator(
    operator_type: str,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    states: list[str] | None = None,
    exclude_simulations: bool = True,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    session: Session = NEW_SESSION,
) -> list[HistoricalRuntime]:
    """
    Retrieve historical runtimes for all tasks using a given operator type.

    This enables cross-DAG estimates for new tasks that have no history of
    their own but share an operator type with tasks that do.

    Args:
        operator_type: The operator class name (e.g. ``"PythonOperator"``).
        start_date: Only include runs that started on or after this datetime.
        end_date: Only include runs that started on or before this datetime.
        states: Task states to include. Defaults to ``["success"]`` when *None*.
        exclude_simulations: When *True*, exclude rows where ``is_simulation`` is set.
        limit: Maximum number of records to return. Capped at :data:`DEFAULT_LIMIT`.
        offset: Number of records to skip for pagination.
        session: SQLAlchemy session (provided by ``@provide_session``).

    Returns:
        A list of :class:`HistoricalRuntime` records ordered by ``start_date``
        descending (most recent first).  Returns an empty list when no matching
        records exist.
    """
    if states is None:
        states = [TaskInstanceState.SUCCESS.value]

    limit = min(max(limit, 1), DEFAULT_LIMIT)
    offset = max(offset, 0)

    stmt = select(
        TaskInstance.run_id,
        TaskInstance.duration,
        TaskInstance.start_date,
        TaskInstance.end_date,
        TaskInstance.state,
    ).where(
        TaskInstance.operator == operator_type,
        TaskInstance.state.in_(states),
    )

    if start_date is not None:
        stmt = stmt.where(TaskInstance.start_date >= start_date)

    if end_date is not None:
        stmt = stmt.where(TaskInstance.start_date <= end_date)

    if exclude_simulations and hasattr(TaskInstance, "is_simulation"):
        stmt = stmt.where(TaskInstance.is_simulation.is_(False))

    stmt = stmt.order_by(TaskInstance.start_date.desc()).limit(limit).offset(offset)

    rows = session.execute(stmt).all()

    return [
        HistoricalRuntime(
            run_id=row.run_id,
            duration=row.duration,
            start_date=row.start_date,
            end_date=row.end_date,
            state=row.state,
        )
        for row in rows
    ]


@provide_session
def get_task_state_history(
    dag_id: str,
    task_id: str,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    exclude_simulations: bool = True,
    limit: int = DEFAULT_LIMIT,
    session: Session = NEW_SESSION,
) -> list[str]:
    """
    Return task instance states for a task, ordered newest-first.

    Unlike :func:`get_historical_runtimes`, this does not filter by state — every
    recorded outcome (``success``, ``failed``, ``upstream_failed``, ``skipped``,
    etc.) is returned. Used by :class:`SuccessPredictor` to compute success rates.

    Args:
        dag_id: The DAG identifier.
        task_id: The task identifier.
        start_date: Only include runs that started on or after this datetime.
        end_date: Only include runs that started on or before this datetime.
        exclude_simulations: When *True*, exclude rows where ``is_simulation`` is set.
        limit: Maximum number of records to return. Capped at :data:`DEFAULT_LIMIT`.
        session: SQLAlchemy session (provided by ``@provide_session``).

    Returns:
        A list of state strings ordered by ``start_date`` descending (most
        recent first). ``None`` states are filtered out.
    """
    limit = min(max(limit, 1), DEFAULT_LIMIT)

    stmt = select(TaskInstance.state, TaskInstance.start_date).where(
        TaskInstance.dag_id == dag_id,
        TaskInstance.task_id == task_id,
        TaskInstance.state.is_not(None),
    )

    if start_date is not None:
        stmt = stmt.where(TaskInstance.start_date >= start_date)

    if end_date is not None:
        stmt = stmt.where(TaskInstance.start_date <= end_date)

    if exclude_simulations and hasattr(TaskInstance, "is_simulation"):
        stmt = stmt.where(TaskInstance.is_simulation.is_(False))

    stmt = stmt.order_by(TaskInstance.start_date.desc()).limit(limit)

    rows = session.execute(stmt).all()

    return [row.state for row in rows]


@provide_session
def get_dag_run_state_history(
    dag_id: str,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    exclude_simulations: bool = True,
    limit: int = DEFAULT_LIMIT,
    session: Session = NEW_SESSION,
) -> list[str]:
    """
    Return DagRun states for a DAG, ordered newest-first.

    Used by :class:`SuccessPredictor` for DAG-level success prediction. Returns
    every recorded DagRun state (``success``, ``failed``, ...). Unlike per-task
    state queries, only terminal DagRun outcomes are meaningful here, so
    in-flight states (``running``, ``queued``) are filtered out.

    Args:
        dag_id: The DAG identifier.
        start_date: Only include runs that started on or after this datetime.
        end_date: Only include runs that started on or before this datetime.
        exclude_simulations: When *True*, exclude DagRuns flagged as simulations.
        limit: Maximum number of records to return. Capped at :data:`DEFAULT_LIMIT`.
        session: SQLAlchemy session (provided by ``@provide_session``).

    Returns:
        A list of state strings ordered by ``start_date`` descending (most
        recent first).
    """
    limit = min(max(limit, 1), DEFAULT_LIMIT)

    stmt = select(DagRun.state, DagRun.start_date).where(
        DagRun.dag_id == dag_id,
        DagRun.state.in_(("success", "failed")),
    )

    if start_date is not None:
        stmt = stmt.where(DagRun.start_date >= start_date)

    if end_date is not None:
        stmt = stmt.where(DagRun.start_date <= end_date)

    if exclude_simulations and hasattr(DagRun, "is_simulation"):
        stmt = stmt.where(DagRun.is_simulation.is_(False))

    stmt = stmt.order_by(DagRun.start_date.desc()).limit(limit)

    rows = session.execute(stmt).all()

    return [row.state for row in rows]
