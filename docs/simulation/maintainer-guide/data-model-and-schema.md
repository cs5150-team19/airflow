# Data Model & Schema

## Schema Changes

The simulation feature adds columns to existing Airflow tables via an Alembic migration.

### Modified: `task_instance`

| Column | Type | Purpose |
|---|---|---|
| `is_simulation` | `Boolean` | Flags whether this task instance belongs to a simulation run |
| `estimated_runtime` | `Float` | Predicted runtime in seconds |
| `predicted_outcome` | `String` | Predicted outcome (`SUCCESS` or `FAILURE`) |

### Modified: `dag_run`

| Column | Type | Purpose |
|---|---|---|
| `is_simulation` | `Boolean` | Flags whether this DAG run is a simulation run |

### New Tables

#### `simulation_result`

Stores per-simulation metadata for each simulation triggered against a DAG.

| Column | Type | Purpose |
|---|---|---|
| `simulation_id` | `UUID` (PK) | Unique identifier for the simulation run |
| `dag_id` | `String` | The DAG that was simulated |
| `total_estimated_runtime` | `Float` | Estimated runtime of the critical path in seconds |
| `critical_path_runtime` | `Float` | Runtime of the critical path sequence specifically |
| `predictor_type` | `String` | Which predictor was primarily used (`Historical`, `InputSize`, or `Constant`) |
| `triggered_at` | `DateTime` | Timestamp when the simulation was triggered |
| `result_json` | `Text` | Full structured JSON report returned to the client |

#### `simulation_task_result`

Stores per-task predictions for each simulation. References `simulation_result` via foreign key.

| Column | Type | Purpose |
|---|---|---|
| `simulation_id` | `UUID` (FK → `simulation_result`) | Links this row to its parent simulation |
| `task_id` | `String` | The task within the simulated DAG |
| `estimated_runtime` | `Float` | Predicted runtime for this task in seconds |
| `predicted_outcome` | `String` | Predicted task outcome (`SUCCESS` or `FAILURE`) |
| `confidence_score` | `String` | Confidence tier for this estimate (`high`, `medium_high`, `medium`, `low`) |
| `is_bottleneck` | `Boolean` | Whether this task is the identified bottleneck on the critical path |
| `is_on_critical_path` | `Boolean` | Whether this task lies on the critical path |

---

## Migrations

Managed via Alembic. Both `up` and `down` directions are implemented and tested.

```bash
airflow db migrate
```

---

## Important Notes

- PostgreSQL (versions 14–18) is **required**. The team developed and tested against
  PostgreSQL 18. SQLite is not supported in production for the simulation feature.
- Simulation run rows (`run_type=simulation`, `is_simulation=True`) appear in `dag_run`
  but numeric estimates live in memory only — not persisted to the database row.
- The historical data layer **excludes** `is_simulation=True` rows to prevent
  feedback loops in future predictions.
