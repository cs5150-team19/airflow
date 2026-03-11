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
    estimated_seconds: int
    confidence: float


class SimulationResponse(BaseModel):
    """Response for a DAG simulation."""

    simulation_id: str
    dag_id: str
    task_estimates: list[TaskSimulationResponse]
    total_estimated_seconds: int
    predicted_outcome: str
