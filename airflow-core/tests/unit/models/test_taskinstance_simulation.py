#
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

from unittest.mock import MagicMock, patch

import pytest

from airflow.models.taskinstance import TaskInstance
from airflow.simulation.predictor_interface import (
    DeterministicPredictor,
    PredictedOutcome,
    _OPERATOR_RUNTIME_SECONDS,
)
from airflow.utils.state import TaskInstanceState


class TestTaskInstanceSimulationFields:
    """Tests for the is_simulation, estimated_runtime, and predicted_outcome columns."""

    def test_simulation_columns_exist(self):
        """The TaskInstance table should have the three simulation columns."""
        col_names = {c.name for c in TaskInstance.__table__.columns}
        assert "is_simulation" in col_names
        assert "estimated_runtime" in col_names
        assert "predicted_outcome" in col_names

    def test_is_simulation_column_not_nullable(self):
        col = TaskInstance.__table__.c.is_simulation
        assert col.nullable is False

    def test_is_simulation_server_default(self):
        col = TaskInstance.__table__.c.is_simulation
        assert col.server_default is not None

    def test_estimated_runtime_column_nullable(self):
        col = TaskInstance.__table__.c.estimated_runtime
        assert col.nullable is True

    def test_predicted_outcome_column_nullable(self):
        col = TaskInstance.__table__.c.predicted_outcome
        assert col.nullable is True


class TestTaskInstanceRunSimulation:
    """Tests for the run_simulation method."""

    def _make_ti(self, operator_name="PythonOperator"):
        """Create a mock TaskInstance with the needed attributes."""
        ti = MagicMock(spec=TaskInstance)
        ti.task_id = "test_task"
        ti.dag_id = "test_dag"
        ti.operator = operator_name
        ti.is_simulation = False
        ti.estimated_runtime = None
        ti.predicted_outcome = None
        ti.state = None
        ti.duration = None
        # Use the real method bound to this mock
        ti.run_simulation = TaskInstance.run_simulation.__get__(ti, TaskInstance)
        return ti

    def test_run_simulation_sets_is_simulation(self):
        ti = self._make_ti()
        ti.run_simulation(session=MagicMock())
        assert ti.is_simulation is True

    def test_run_simulation_sets_estimated_runtime(self):
        ti = self._make_ti("PythonOperator")
        ti.run_simulation(session=MagicMock())
        assert ti.estimated_runtime == 30.0

    def test_run_simulation_sets_predicted_outcome(self):
        ti = self._make_ti()
        ti.run_simulation(session=MagicMock())
        assert ti.predicted_outcome == PredictedOutcome.SUCCESS.value

    def test_run_simulation_sets_state_to_success(self):
        ti = self._make_ti()
        ti.run_simulation(session=MagicMock())
        assert ti.state == TaskInstanceState.SUCCESS.value

    def test_run_simulation_sets_duration(self):
        ti = self._make_ti()
        ti.run_simulation(session=MagicMock())
        assert ti.duration == ti.estimated_runtime

    def test_run_simulation_bash_operator(self):
        ti = self._make_ti("BashOperator")
        ti.run_simulation(session=MagicMock())
        assert ti.estimated_runtime == 10.0

    def test_run_simulation_unknown_operator(self):
        ti = self._make_ti("SomeCustomOperator")
        ti.run_simulation(session=MagicMock())
        # Unknown operators default to 30 seconds
        assert ti.estimated_runtime == 30.0

    @pytest.mark.parametrize(
        "operator_name, expected_seconds",
        [
            ("PythonOperator", 30.0),
            ("BashOperator", 10.0),
            ("MySqlOperator", 60.0),
            ("PostgresOperator", 60.0),
            ("S3KeySensor", 300.0),
            ("Unknown", 30.0),
        ],
    )
    def test_run_simulation_operator_runtimes(self, operator_name, expected_seconds):
        ti = self._make_ti(operator_name)
        ti.run_simulation(session=MagicMock())
        assert ti.estimated_runtime == expected_seconds
