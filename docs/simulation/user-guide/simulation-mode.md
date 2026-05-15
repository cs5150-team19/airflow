# Simulation Mode

## Switching Modes

The **Normal / Simulation toggle** in the top navigation bar controls which mode is active.

| Mode | Behavior |
|---|---|
| Normal | Standard Airflow — triggering a DAG runs real tasks |
| Simulation | Dry-run only — no tasks execute, no external calls are made |

When Simulation Mode is active:
- The URL prefix updates to `/simulation`
- A **Simulation Trigger** button appears to the right of the toggle
- All navigation links (DAG runs, tasks, overview) stay in simulation context

## Triggering a Simulation

Click **Simulation Trigger** on any DAG page. The `SimulationExecutor` walks the DAG,
mocks all task results, and returns a structured report without creating a real DAG run.

A `dag_run` row is written to the database with `run_type=simulation` and `is_simulation=True`,
but this row does **not** appear in Normal Mode run history.

## Sharing a Simulation View

Simulation state is preserved in the URL:

```
/simulation/dags/<dag_id>/graph?simulation_id=<id>&criticalPath=true&bottleneck=true
```

Copying the URL shares both the active simulation and the current overlay configuration
with a teammate.

## Use Cases

- [Running a simulation](getting-started.md)
- [Viewing runtime estimates](runtime-estimates.md)
- [Identifying bottlenecks](critical-paths.md)
