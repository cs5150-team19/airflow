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
from airflow.models.dagrun import DagRun
from airflow.models.taskinstance import TaskInstance as TI
from airflow.simulation.predictor_interface import DeterministicPredictor

simulation_router = AirflowRouter(tags=["Simulation"], prefix="/dags/{dag_id}")

# In-memory store for simulation results (keyed by simulation_id)
_simulation_results: dict[str, SimulationResponse] = {}


@simulation_router.post(
    "/simulate",
    responses=create_openapi_http_exception_doc(
        [status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT]
    ),
    dependencies=[
        Depends(requires_access_dag(method="GET", access_entity=DagAccessEntity.TASK_INSTANCE))
    ],
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
    if dag_run is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No DAG runs found for dag_id: `{dag_id}`",
        )

    task_instances = session.scalars(
        select(TI).where(TI.dag_id == dag_id, TI.run_id == dag_run.run_id)
    ).all()

    if not task_instances:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No task instances found for dag_id: `{dag_id}`, run_id: `{dag_run.run_id}`",
        )

    predictor = DeterministicPredictor()
    tasks = [
        {"task_id": ti.task_id, "operator_type": ti.operator or "Unknown"}
        for ti in task_instances
    ]
    estimate = predictor.estimate_dag(dag_id=dag_id, tasks=tasks)

    simulation_id = str(uuid.uuid4())
    task_responses = [
        TaskSimulationResponse(
            task_id=te.task_id,
            operator_type=te.operator_type,
            estimated_seconds=te.estimated_seconds,
            confidence=te.confidence,
        )
        for te in estimate.task_estimates
    ]

    response = SimulationResponse(
        simulation_id=simulation_id,
        dag_id=dag_id,
        task_estimates=task_responses,
        total_estimated_seconds=estimate.total_task_seconds,
        predicted_outcome=estimate.predicted_outcome.value,
    )

    _simulation_results[simulation_id] = response
    return response


@simulation_router.get(
    "/simulate/{simulation_id}",
    responses=create_openapi_http_exception_doc([status.HTTP_404_NOT_FOUND]),
    dependencies=[
        Depends(requires_access_dag(method="GET", access_entity=DagAccessEntity.TASK_INSTANCE))
    ],
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
