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
"""Structural similarity-based runtime predictor (skeleton).

This predictor estimates runtimes for new DAGs by finding existing DAGs
with similar structure and using their historical execution data.

The fallback chain with this predictor would become:
    Level 1: Exact match (same dag_id + task_id)
    Level 2: Similar DAG match (structurally similar DAG, matched task)
    Level 3: Operator-type match (same operator across all DAGs)
    Level 4: Hardcoded heuristic (DeterministicPredictor)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DagFeatureVector:
    """Structural features extracted from a DAG for similarity comparison.

    TODO: Extract these features from SerializedDagModel. The serialized
    DAG JSON contains the full task graph — operator types, dependency
    edges, and task parameters.
    """

    dag_id: str
    task_count: int = 0
    # Operator composition: count of each operator type in the DAG.
    # e.g. {"PythonOperator": 3, "BashOperator": 1}
    operator_counts: dict[str, int] = field(default_factory=dict)
    # Maximum depth of the dependency graph (longest path from root to leaf).
    max_depth: int = 0
    # Maximum parallelism (widest level of the dependency graph).
    max_parallelism: int = 0
    # Number of leaf tasks (tasks with no downstream dependencies).
    leaf_count: int = 0
    # Number of root tasks (tasks with no upstream dependencies).
    root_count: int = 0


def extract_dag_features(dag_id: str) -> DagFeatureVector | None:
    """Extract structural features from a serialized DAG.

    TODO: Implement by querying SerializedDagModel for the given dag_id,
    deserializing the task graph, and computing:
    - task_count: len(dag.tasks)
    - operator_counts: Counter(task.operator for task in dag.tasks)
    - max_depth: longest path via BFS/DFS on the dependency edges
    - max_parallelism: max tasks at any single depth level
    - leaf_count: tasks with no downstream
    - root_count: tasks with no upstream

    Returns None if the DAG is not found in the database.
    """
    raise NotImplementedError


def extract_all_dag_features() -> list[DagFeatureVector]:
    """Extract features for all DAGs in the metadata database.

    TODO: Implement by querying all rows from SerializedDagModel and
    calling extract_dag_features() for each. Consider caching the
    results since DAG structures change infrequently.

    Performance note: This is O(N) over all DAGs. For large deployments
    (1000+ DAGs), consider building an index or caching the feature
    vectors and invalidating when a DAG is re-serialized.
    """
    raise NotImplementedError


def compute_similarity(a: DagFeatureVector, b: DagFeatureVector) -> float:
    """Compute similarity score between two DAG feature vectors.

    Returns a value between 0.0 (completely different) and 1.0 (identical).

    TODO: Implement using cosine similarity on a combined feature vector.
    Suggested approach:
    1. Build a numeric vector for each DAG from its features:
       - Normalize task_count, max_depth, max_parallelism to [0, 1]
       - Convert operator_counts to a sparse vector over all known
         operator types, normalized by task_count
    2. Compute cosine similarity: dot(a, b) / (||a|| * ||b||)

    Alternative approaches to consider:
    - Weighted features (operator composition may matter more than depth)
    - Jaccard similarity on the set of operator types used
    - Graph edit distance on the dependency structure (expensive but precise)
    """
    raise NotImplementedError


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two numeric vectors.

    TODO: Use this as the core of compute_similarity() once the feature
    vectors are built.
    """
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_similar_dags(
    target: DagFeatureVector,
    candidates: list[DagFeatureVector],
    top_k: int = 5,
    min_similarity: float = 0.6,
) -> list[tuple[DagFeatureVector, float]]:
    """Find the top-K most similar DAGs to the target.

    TODO: Implement by:
    1. Calling compute_similarity(target, candidate) for each candidate
    2. Filtering out candidates below min_similarity
    3. Sorting by similarity descending
    4. Returning the top_k results as (feature_vector, score) tuples

    Args:
        target: The feature vector of the new DAG.
        candidates: Feature vectors of all existing DAGs.
        top_k: Maximum number of similar DAGs to return.
        min_similarity: Minimum similarity score to include a candidate.

    Returns:
        List of (DagFeatureVector, similarity_score) tuples, sorted by
        score descending.
    """
    raise NotImplementedError


def match_task_in_similar_dag(
    task_id: str,
    operator_type: str,
    similar_dag_id: str,
) -> str | None:
    """Find the best matching task in a similar DAG for a given task.

    TODO: Implement task matching strategy. Options (in order of priority):
    1. Same operator_type + similar task_id name (string similarity)
    2. Same operator_type + same position in the dependency graph
    3. Same operator_type (any task)

    Args:
        task_id: The task_id in the new DAG we want to estimate.
        operator_type: The operator type of the task.
        similar_dag_id: The dag_id of the similar DAG to search in.

    Returns:
        The task_id of the best matching task in the similar DAG,
        or None if no reasonable match is found.
    """
    raise NotImplementedError


# TODO: Integrate into HistoricalPredictor as a new fallback level.
#
# The integration point is HistoricalPredictor.estimate_task(). The new
# fallback level would be inserted between Level 1 (exact match) and
# Level 2 (operator-type match):
#
#   Level 1: Exact match (existing)
#   Level 1.5 (NEW): Similar DAG match
#       1. Call extract_dag_features() for the target DAG
#       2. Call find_similar_dags() to get candidates
#       3. For each similar DAG, call match_task_in_similar_dag()
#       4. Use get_historical_runtimes() with the matched dag_id + task_id
#       5. Aggregate durations and return with confidence scaled by
#          similarity score (e.g., 0.6 * similarity_score + 0.05)
#   Level 2: Operator-type match (existing)
#   Level 3: Hardcoded heuristic (existing)
#
# Confidence for similar-DAG estimates should be:
# - Higher than operator-type (more specific signal)
# - Lower than exact match (it's still an approximation)
# - Scaled by the similarity score (0.85 similar → higher confidence
#   than 0.65 similar)
#
# Suggested confidence range: 0.6–0.85 (between exact match 0.7–0.95
# and operator-type 0.55–0.75)
