# Runtime Estimates

After triggering a simulation, the **Detail Side Panel** displays a structured report.

## Summary Section

| Field | Description |
|---|---|
| Predicted Outcome | `SUCCESS` or `FAILURE`, derived from success probability across all tasks |
| Total Estimated Runtime | Runtime of the critical path only — parallel tasks do not add together |
| Task Count | Total number of tasks in the DAG |
| Longest Critical Task | The single task on the critical path with the highest individual estimated runtime |

## Task Estimates Section

Each task is listed with:
- **Estimated runtime** (in seconds)
- **Confidence score** indicating which prediction tier produced the estimate

## Confidence Scores

The prediction engine uses a four-level fallback chain. The confidence score reflects
which level was used:

| Level | Source | Confidence |
|---|---|---|
| 1 | Exact `(dag_id, task_id)` historical match | High |
| 2 | Cross-DAG fingerprint match (same operator type + task content hash) | Medium-High |
| 3 | Operator-type average across all DAGs | Medium |
| 4 | Deterministic heuristic (hardcoded constant per operator type) | Low |

When most tasks show **Low** confidence, the DAG has fewer than the minimum historical
runs needed by the Historical Predictor. Run the DAG normally a few times to improve
future estimates.

## Comparing Against Actual Runtimes

Use the Airflow UI's existing run history to compare the **Total Estimated Runtime**
against prior actual DAG run durations. Large discrepancies are most likely when the
majority of task estimates carry low confidence scores.
