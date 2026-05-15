# Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| Simulation fails to trigger / returns server error | API server cannot reach the metadata database, or simulation schema migration has not been applied | Verify PostgreSQL is running and reachable. Confirm `is_simulation`, `estimated_runtime`, and `predicted_outcome` columns exist on `task_instance` by running `airflow db migrate` |
| DAG not appearing in Simulation Mode | DAG file has not been parsed by the scheduler, or DAG is paused | Confirm the DAG appears in Normal Mode first. Check the DAG file is in the configured DAGs folder and the scheduler has parsed it. Unpause if necessary |
| Simulation results disappear after a server restart | Results are held in an in-memory dictionary and not persisted across API server restarts | Re-trigger the simulation. The `airflow.latestSimulation.{dagId}` entry in `localStorage` retains the most recent `simulation_id`, but the underlying report must be regenerated |
| All task estimates show Low confidence | Fewer than the minimum historical runs required; system falls back to deterministic heuristic | Run the DAG normally at least three times to build historical data |
| Critical Path or Bottleneck overlay does not appear | Overlay toggles are off, or URL search parameters have been cleared | Open Display Options and re-enable the overlays |
| Simulation Mode toggle does not appear in the UI | Browser cache is stale | Hard-refresh (`Ctrl+Shift+R` / `Cmd+Shift+R`) |
| `/api/v2/dags/{dagId}/simulate` returns 404 | Simulation route not registered with the FastAPI router | Confirm API server logs show simulation routes registered on startup. Verify the simulation module is included in FastAPI route registration |
| Predicted runtime differs significantly from actual | Small historical sample or DAG behavior has fundamentally changed since historical runs were recorded | Review confidence scores. If most tasks are Low/Medium, accumulate more runs. For significantly changed DAGs, consider excluding old runs from the historical data window |
