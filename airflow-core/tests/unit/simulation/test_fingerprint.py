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
"""Tests for ``compute_task_fingerprint``."""

from __future__ import annotations

from types import SimpleNamespace

from airflow.simulation.fingerprint import compute_task_fingerprint

# Stand-in operator types: SimpleNamespace mimics duck-typed access to
# attributes the fingerprint helper inspects, while ``type().__name__`` is the
# operator class name used as the first signal.


class FakePythonOperator(SimpleNamespace):
    pass


class FakeBashOperator(SimpleNamespace):
    pass


class FakeSqlOperator(SimpleNamespace):
    pass


class FakeKubernetesPodOperator(SimpleNamespace):
    pass


class FakeBareOperator(SimpleNamespace):
    """Operator with no work-signal attributes — matches the 'no signal' case."""


def _func_a():
    return 1


def _func_b():
    return 2


class TestNoSignalReturnsNone:
    def test_operator_with_no_attributes_returns_none(self):
        # No callable, no bash_command, no sql, no image — fingerprint adds
        # no information beyond the operator class.
        task = FakeBareOperator()

        assert compute_task_fingerprint(task) is None

    def test_python_operator_with_none_callable_returns_none(self):
        task = FakePythonOperator(python_callable=None)

        assert compute_task_fingerprint(task) is None

    def test_bash_operator_with_empty_command_returns_none(self):
        task = FakeBashOperator(bash_command="")

        assert compute_task_fingerprint(task) is None


class TestStability:
    def test_same_callable_yields_same_fingerprint(self):
        a = FakePythonOperator(python_callable=_func_a)
        b = FakePythonOperator(python_callable=_func_a)

        assert compute_task_fingerprint(a) == compute_task_fingerprint(b)

    def test_different_callables_yield_different_fingerprints(self):
        a = FakePythonOperator(python_callable=_func_a)
        b = FakePythonOperator(python_callable=_func_b)

        assert compute_task_fingerprint(a) != compute_task_fingerprint(b)

    def test_same_bash_command_yields_same_fingerprint(self):
        a = FakeBashOperator(bash_command="echo hello")
        b = FakeBashOperator(bash_command="echo hello")

        assert compute_task_fingerprint(a) == compute_task_fingerprint(b)

    def test_different_bash_commands_yield_different_fingerprints(self):
        a = FakeBashOperator(bash_command="echo hello")
        b = FakeBashOperator(bash_command="echo goodbye")

        assert compute_task_fingerprint(a) != compute_task_fingerprint(b)

    def test_same_sql_yields_same_fingerprint(self):
        a = FakeSqlOperator(sql="SELECT 1")
        b = FakeSqlOperator(sql="SELECT 1")

        assert compute_task_fingerprint(a) == compute_task_fingerprint(b)


class TestOperatorClassNameMatters:
    def test_same_attributes_different_class_yield_different_fingerprints(self):
        # Two operator classes that happen to expose the same attribute name
        # ("script") with the same value should not collide if their class
        # names differ — the operator class is part of the fingerprint.
        bash = FakeBashOperator(bash_command="echo hi")
        sql = FakeSqlOperator(sql="echo hi")

        assert compute_task_fingerprint(bash) != compute_task_fingerprint(sql)

    def test_python_qualname_differentiates_methods(self):
        class HelperA:
            @staticmethod
            def run():
                return None

        class HelperB:
            @staticmethod
            def run():
                return None

        a = FakePythonOperator(python_callable=HelperA.run)
        b = FakePythonOperator(python_callable=HelperB.run)

        assert compute_task_fingerprint(a) != compute_task_fingerprint(b)


class TestImageSignal:
    def test_same_image_yields_same_fingerprint(self):
        a = FakeKubernetesPodOperator(image="ghcr.io/team/app:1.0")
        b = FakeKubernetesPodOperator(image="ghcr.io/team/app:1.0")

        assert compute_task_fingerprint(a) == compute_task_fingerprint(b)

    def test_different_image_tags_yield_different_fingerprints(self):
        a = FakeKubernetesPodOperator(image="ghcr.io/team/app:1.0")
        b = FakeKubernetesPodOperator(image="ghcr.io/team/app:2.0")

        assert compute_task_fingerprint(a) != compute_task_fingerprint(b)


class TestFingerprintShape:
    def test_fingerprint_is_a_short_hex_string(self):
        task = FakeBashOperator(bash_command="echo hi")
        fingerprint = compute_task_fingerprint(task)

        assert fingerprint is not None
        assert isinstance(fingerprint, str)
        assert len(fingerprint) == 16
        assert all(char in "0123456789abcdef" for char in fingerprint)
