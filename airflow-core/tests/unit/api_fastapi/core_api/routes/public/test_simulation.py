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

import pytest

from airflow.models import DagRun, TaskInstance
from airflow.models.dag_version import DagVersion
from airflow.utils.state import DagRunState, TaskInstanceState
from airflow.utils.types import DagRunType

from airflow._shared.timezones.timezone import datetime

from tests_common.test_utils.db import clear_db_runs

pytestmark = pytest.mark.db_test

DEFAULT_TIME = datetime(2020, 1, 1)
DAG_ID = "example_python_operator"


class TestSimulationEndpoint:
    @staticmethod
    def clear_db():
        clear_db_runs()

    def setup_method(self):
        self.clear_db()

    def teardown_method(self):
        self.clear_db()

    @pytest.fixture(autouse=True)
    def setup_attrs(self, dagbag) -> None:
        self.dagbag = dagbag

    def create_dag_run_with_tasks(self, session, dag_id=DAG_ID):
        dag = self.dagbag.get_latest_version_of_dag(dag_id, session=session)
        dag_version = DagVersion.get_latest_version(dag.dag_id, session=session)
        dr = DagRun(
            run_id="TEST_SIMULATION_RUN",
            dag_id=dag_id,
            logical_date=DEFAULT_TIME,
            run_type=DagRunType.MANUAL,
            state=DagRunState.RUNNING,
        )
        session.add(dr)
        session.flush()

        for task in dag.tasks:
            ti = TaskInstance(
                task=task,
                state=TaskInstanceState.SUCCESS,
                map_index=-1,
                dag_version_id=dag_version.id,
            )
            ti.dag_run = dr
            session.add(ti)

        session.commit()
        return dr


class TestRunSimulation(TestSimulationEndpoint):
    def test_should_respond_200(self, test_client, session):
        self.create_dag_run_with_tasks(session)

        response = test_client.post(f"/dags/{DAG_ID}/simulate")

        assert response.status_code == 200
        data = response.json()
        assert data["dag_id"] == DAG_ID
        assert "simulation_id" in data
        assert "task_estimates" in data
        assert isinstance(data["task_estimates"], list)
        assert len(data["task_estimates"]) > 0
        assert "total_estimated_seconds" in data
        assert data["predicted_outcome"] == "success"

    def test_task_estimates_have_required_fields(self, test_client, session):
        self.create_dag_run_with_tasks(session)

        response = test_client.post(f"/dags/{DAG_ID}/simulate")

        assert response.status_code == 200
        for task_est in response.json()["task_estimates"]:
            assert "task_id" in task_est
            assert "operator_type" in task_est
            assert "estimated_seconds" in task_est
            assert "confidence" in task_est
            assert 0.0 <= task_est["confidence"] <= 1.0

    def test_should_respond_404_for_missing_dag(self, test_client, session):
        response = test_client.post("/dags/nonexistent_dag/simulate")

        assert response.status_code == 404

    def test_total_equals_sum_of_task_estimates(self, test_client, session):
        self.create_dag_run_with_tasks(session)

        response = test_client.post(f"/dags/{DAG_ID}/simulate")

        data = response.json()
        total = sum(te["estimated_seconds"] for te in data["task_estimates"])
        assert data["total_estimated_seconds"] == total


class TestGetSimulation(TestSimulationEndpoint):
    def test_should_respond_200(self, test_client, session):
        self.create_dag_run_with_tasks(session)

        # First run a simulation to get a simulation_id
        post_response = test_client.post(f"/dags/{DAG_ID}/simulate")
        assert post_response.status_code == 200
        simulation_id = post_response.json()["simulation_id"]

        # Then retrieve it
        get_response = test_client.get(f"/dags/{DAG_ID}/simulate/{simulation_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["simulation_id"] == simulation_id
        assert data["dag_id"] == DAG_ID

    def test_should_respond_404_for_missing_simulation(self, test_client, session):
        response = test_client.get(f"/dags/{DAG_ID}/simulate/nonexistent-id")

        assert response.status_code == 404

    def test_get_returns_same_data_as_post(self, test_client, session):
        self.create_dag_run_with_tasks(session)

        post_response = test_client.post(f"/dags/{DAG_ID}/simulate")
        post_data = post_response.json()

        get_response = test_client.get(f"/dags/{DAG_ID}/simulate/{post_data['simulation_id']}")
        get_data = get_response.json()

        assert post_data == get_data
