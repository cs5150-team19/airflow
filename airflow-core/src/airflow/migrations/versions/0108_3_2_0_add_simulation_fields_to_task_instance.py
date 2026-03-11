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

"""
Add simulation fields to TaskInstance.

Revision ID: a1b2c3d4e5f6
Revises: 6222ce48e289
Create Date: 2026-03-09 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "6222ce48e289"
branch_labels = None
depends_on = None
airflow_version = "3.2.0"


def upgrade():
    """Add is_simulation, estimated_runtime, and predicted_outcome to task_instance."""
    with op.batch_alter_table("task_instance", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_simulation", sa.Boolean, nullable=False, server_default="0"),
        )
        batch_op.add_column(
            sa.Column("estimated_runtime", sa.Float, nullable=True),
        )
        batch_op.add_column(
            sa.Column("predicted_outcome", sa.String(20), nullable=True),
        )


def downgrade():
    """Remove simulation fields from task_instance."""
    with op.batch_alter_table("task_instance", schema=None) as batch_op:
        batch_op.drop_column("predicted_outcome")
        batch_op.drop_column("estimated_runtime")
        batch_op.drop_column("is_simulation")
