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
"""Structural tests for the ``add_simulation_fields`` migration.

A real upgrade/downgrade roundtrip is exercised by Airflow's existing
migration test infrastructure (which runs the full chain against sqlite
and postgres). These tests pin the small things that don't need a live
DB: the revision identifiers, the airflow_version stamp, and that both
``upgrade``/``downgrade`` modules are importable and callable.
"""

from __future__ import annotations

import importlib

import pytest

MIGRATION_MODULE = (
    "airflow.migrations.versions.0112_3_3_0_add_simulation_fields"
)


@pytest.fixture
def migration():
    return importlib.import_module(MIGRATION_MODULE)


class TestMigrationMetadata:
    def test_revision_id(self, migration):
        assert migration.revision == "49ed3350068d"

    def test_down_revision_chains_off_previous_head(self, migration):
        # Hard-pin so a future migration insertion doesn't silently re-parent
        # this one (which would corrupt the migration graph for existing DBs).
        # Re-parented from "9fabad868fdb" to "fde9ed84d07b" after main brought
        # in 0112_3_3_0_add_task_state_and_asset_state_tables, which would
        # otherwise share our parent and cause "multiple heads" errors.
        assert migration.down_revision == "fde9ed84d07b"

    def test_no_branch_labels(self, migration):
        assert migration.branch_labels is None
        assert migration.depends_on is None

    def test_airflow_version_stamp(self, migration):
        assert migration.airflow_version == "3.3.0"


class TestMigrationCallables:
    def test_upgrade_is_callable(self, migration):
        assert callable(migration.upgrade)

    def test_downgrade_is_callable(self, migration):
        assert callable(migration.downgrade)
