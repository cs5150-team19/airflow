# Overview

The DAG Simulation Feature allows Airflow users to model DAG execution behavior
without triggering real task runs, external API calls, or any production side effects.

## What You Can Do

- Simulate any DAG directly from the Airflow Web UI or CLI
- View per-task estimated runtimes with confidence scores
- Identify the critical path and bottleneck task on the DAG graph
- Predict DAG-level outcomes (`SUCCESS` / `FAILURE`) using historical data

## User Roles

### DAG Author

The primary user of the simulation feature. Represents developers and data engineers
who write, maintain, and iterate on Airflow DAGs.

**Capabilities:**
- Switch between Normal Mode and Simulation Mode via the toggle in the top navigation bar
- Trigger simulations from the UI or via `airflow dags simulate`
- View per-task estimates and confidence scores in the Detail Side Panel
- Toggle critical path and bottleneck overlays on the DAG graph
- Compare simulation results against historical actual runtimes

### Administrator

Responsible for the operational health of the Airflow deployment.
Typically a platform engineer or DevOps team member.

**Capabilities:**
- Configure simulation settings and environment variables
- Manage RBAC permissions for simulation endpoints
- Apply Alembic database migrations for simulation schema changes
- Monitor scheduler, API server, and worker logs for simulation errors
- Execute deployment and rollback procedures
