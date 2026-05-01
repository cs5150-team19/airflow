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

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select

from airflow.api_fastapi.auth.managers.models.resource_details import DagAccessEntity
from airflow.api_fastapi.common.db.common import SessionDep
from airflow.api_fastapi.common.router import AirflowRouter
from airflow.api_fastapi.core_api.datamodels.simulation import (
    SimulationResponse,
    TaskSimulationResponse,
)
from airflow.api_fastapi.core_api.openapi.exceptions import create_openapi_http_exception_doc
from airflow.api_fastapi.core_api.security import requires_access_dag
from airflow.exceptions import AirflowException
from airflow.models.dagrun import DagRun
from airflow.models.serialized_dag import SerializedDagModel
from airflow.models.taskinstance import TaskInstance as TI
from airflow.simulation.critical_path import get_critical_path
from airflow.simulation.predictor_interface import DeterministicPredictor
from airflow.simulation.predictors.historical_predictor import HistoricalPredictor
from airflow.utils.state import DagRunState
from airflow.utils.types import DagRunTriggeredByType, DagRunType
from airflow._shared.timezones import timezone

simulation_router = AirflowRouter(tags=["Simulation"], prefix="/dags/{dag_id}")

# In-memory store for simulation results (keyed by simulation_id)
_simulation_results: dict[str, SimulationResponse] = {}


def _get_serialized_dag(dag_id: str, session: SessionDep):
    dag = SerializedDagModel.get_dag(dag_id, session=session)
    if dag is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No serialized DAG found for dag_id: `{dag_id}`",
        )
    return dag


def _get_dag_for_dag_run(dag_run: DagRun, dag_id: str, session: SessionDep):
    if dag_run.dag is not None:
        return dag_run.dag

    try:
        dag = dag_run.get_dag()
    except AirflowException:
        dag = None

    if dag is None:
        dag = _get_serialized_dag(dag_id, session)

    dag_run.dag = dag
    return dag


@simulation_router.post(
    "/simulate",
    responses=create_openapi_http_exception_doc([status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT]),
    dependencies=[Depends(requires_access_dag(method="GET", access_entity=DagAccessEntity.TASK_INSTANCE))],
)
def run_simulation(
    dag_id: str,
    session: SessionDep,
) -> SimulationResponse:
    """Run a simulation for all tasks in the most recent DAG run."""
    dag_run = session.scalar(
        select(DagRun)
        .where(DagRun.dag_id == dag_id)
        .order_by(DagRun.start_date.desc())
        .limit(1)
    )

    if dag_run is not None:
        task_instances = session.scalars(
            select(TI).where(TI.dag_id == dag_id, TI.run_id == dag_run.run_id)
        ).all()
    else:
        task_instances = []

    if task_instances:
        tasks = [
            {"task_id": ti.task_id, "operator_type": ti.operator or "Unknown"}
            for ti in task_instances
        ]
        dag = _get_dag_for_dag_run(dag_run, dag_id, session)
    else:
        dag = _get_serialized_dag(dag_id, session)
        tasks = [
            {
                "task_id": task.task_id,
                "operator_type": getattr(task, "operator", None)
                or getattr(task, "task_type", None)
                or "Unknown",
            }
            for task in dag.tasks
        ]
        if not tasks:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"No tasks found for dag_id: `{dag_id}`",
            )

    historical_predictor = HistoricalPredictor()
    estimates = []
    total_runtime = 0
    for t in tasks:
        task_runtime_estimate = historical_predictor.estimate_task(
            t["task_id"],
            t["operator_type"],
        )
        estimates.append(task_runtime_estimate)
        total_runtime += task_runtime_estimate.estimated_seconds

    simulation_id = str(uuid.uuid4())
    task_responses = [
        TaskSimulationResponse(
            task_id=te.task_id,
            operator_type=te.operator_type,
            estimated_seconds=te.estimated_seconds,
            confidence=te.confidence,
        )
        for te in estimates
    ]

    critical_path_response = get_critical_path(dag, task_responses)

    response = SimulationResponse(
        simulation_id=simulation_id,
        dag_id=dag_id,
        task_estimates=task_responses,
        total_estimated_seconds=total_runtime,
        critical_path=critical_path_response,  # bottle neck is returned in this function
        predicted_outcome="success",  # TODO: replace with actual model prediction in the future implementation
    )

    simulation_run_id = DagRunType.SIMULATION.generate_run_id(suffix=simulation_id)
    simulation_dag_run = dag.create_dagrun(
        run_id=simulation_run_id,
        logical_date=None,
        data_interval=None,
        run_after=timezone.utcnow(),
        conf=None,
        run_type=DagRunType.SIMULATION,
        triggered_by=DagRunTriggeredByType.UI,
        triggering_user_name=None,
        note="Simulation run",
        state=DagRunState.SUCCESS,
        session=session,
    )
    simulation_dag_run.is_simulation = True

    _simulation_results[simulation_id] = response
    return response


@simulation_router.get(
    "/simulate/{simulation_id}",
    responses=create_openapi_http_exception_doc([status.HTTP_404_NOT_FOUND]),
    dependencies=[Depends(requires_access_dag(method="GET", access_entity=DagAccessEntity.TASK_INSTANCE))],
)
def get_simulation(
    dag_id: str,
    simulation_id: str,
) -> SimulationResponse:
    """Get the results of a previously run simulation."""
    result = _simulation_results.get(simulation_id)
    if result is None or result.dag_id != dag_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Simulation with id `{simulation_id}` not found for dag_id: `{dag_id}`",
        )
    return result
