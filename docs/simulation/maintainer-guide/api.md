# API Reference

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v2/dags/{dagId}/simulate` | `POST` | Triggers a simulation run |
| `/api/v2/dags/{dagId}/simulation/results` | `GET` | Retrieves a past simulation result by `simulation_id` |

## Response Structure (`POST /simulate`)

```json
{
  "simulation_id": "string",
  "predicted_outcome": "SUCCESS | FAILURE",
  "total_estimated_runtime_seconds": 39,
  "task_count": 3,
  "longest_critical_task": "templated",
  "task_estimates": [
    {
      "task_id": "print_date",
      "estimated_runtime_seconds": 10,
      "confidence": "high | medium_high | medium | low",
      "predictor_source": "exact | fingerprint | operator | heuristic"
    }
  ],
  "critical_path": ["print_date", "templated"],
  "bottleneck_task": "templated"
}
```

## Authentication & Authorization

Simulation endpoints respect Airflow's existing RBAC system. Users must have
appropriate permissions to view and trigger DAGs in order to trigger simulations.

## Pydantic Schemas

Full schema definitions are available via the auto-generated OpenAPI spec at
`/api/v2/openapi.json` on any running Airflow instance with the simulation feature enabled.
