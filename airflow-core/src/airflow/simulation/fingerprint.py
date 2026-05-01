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
Cross-DAG task identity ("fingerprint").

Two task instances in different DAGs are considered "the same task" — and
therefore valid donors of historical runtime data — when their operator class
and operator-specific work signal hash to the same value.

Fingerprints intentionally exclude ``dag_id``, ``task_id``, and DAG-positional
metadata: those identify a task's *location*, not its *behavior*. Matching by
operator-class alone would already be the existing Level 3 fallback in
``HistoricalPredictor``; the fingerprint adds finer-grained signals — the
Python callable, the bash command, the SQL query — that distinguish two
tasks that share an operator type but do completely different work.

A fingerprint of ``None`` means the task offered no signal beyond its operator
class. Callers should skip the fingerprint level in that case so the predictor
falls through to the operator-type fallback.
"""

from __future__ import annotations

import hashlib
from typing import Any


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _python_callable_signal(task: Any) -> str | None:
    callable_obj = getattr(task, "python_callable", None)
    if callable_obj is None:
        return None
    module = getattr(callable_obj, "__module__", None)
    qualname = getattr(callable_obj, "__qualname__", getattr(callable_obj, "__name__", None))
    if module is None and qualname is None:
        return None
    return f"py:{module or '?'}.{qualname or '?'}"


def _bash_command_signal(task: Any) -> str | None:
    command = getattr(task, "bash_command", None)
    if not command or not isinstance(command, str):
        return None
    return f"bash:{_hash(command)}"


def _sql_signal(task: Any) -> str | None:
    sql = getattr(task, "sql", None)
    if not sql:
        return None
    text = sql if isinstance(sql, str) else str(sql)
    return f"sql:{_hash(text)}"


def _image_signal(task: Any) -> str | None:
    image = getattr(task, "image", None)
    if not image or not isinstance(image, str):
        return None
    return f"img:{image}"


# The signal extractors are tried in turn; any that return a non-None value
# contribute to the fingerprint. Order is stable so the resulting hash is
# deterministic across processes and across Airflow restarts.
_SIGNAL_EXTRACTORS = (
    _python_callable_signal,
    _bash_command_signal,
    _sql_signal,
    _image_signal,
)


def compute_task_fingerprint(task: Any) -> str | None:
    """
    Return a stable identity for a task across DAGs, or ``None`` if no signal exists.

    A fingerprint of ``None`` signals to the predictor that the operator class
    is the only available signal — equivalent to falling back to the operator
    fallback level rather than running an expensive cross-DAG search that
    would yield the same result.
    """
    operator_class = type(task).__name__
    parts: list[str] = [operator_class]

    for extract in _SIGNAL_EXTRACTORS:
        signal = extract(task)
        if signal is not None:
            parts.append(signal)

    # If the only part is the operator class name, the fingerprint adds no
    # information beyond what the operator-type fallback already provides.
    if len(parts) == 1:
        return None

    return _hash("|".join(parts))
