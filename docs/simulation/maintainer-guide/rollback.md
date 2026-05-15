# Rollback Procedures

The simulation feature does not modify Airflow's Docker setup. The Docker image is
inherited from Apache Airflow upstream and does not need to be reverted as part of
a simulation-specific rollback. The only components that require rollback are the
Alembic database migrations and, if necessary, the database itself.

## Rollback Triggers

Initiate a rollback if any of the following occur:

- Unhandled exception in the simulation API endpoint affecting normal DAG operations
- The `is_simulation` flag or schema migration causing errors in existing non-simulation DAG runs
- UI regressions that break Normal Mode navigation (routing changes affect both modes)

## Rollback Steps

### 1. Revert the Alembic Migration

Run the down-migration to remove the simulation-specific schema columns
(`is_simulation`, `estimated_runtime`, `predicted_outcome`) from `task_instance`
and `dag_run`, and drop the `simulation_result` and `simulation_task_result` tables:

```bash
# List migrations to find the revision that preceded the simulation migration
airflow db show-migrations

# Downgrade to that revision
airflow db downgrade <previous_revision_id>
```

Both the `up` and `down` migration directions are implemented and tested.

### 2. Restore the Database (if needed)

If the migration caused data corruption, restore from the pre-deployment backup taken
before `airflow db migrate` was run using your standard PostgreSQL restore procedure.

### 3. Restart Services

After confirming the database is in a clean state, restart the Airflow API server,
workers, and scheduler in sequence — scheduler last.

### 4. Verify Normal Mode

Confirm that Normal Mode DAG triggering, run history, and task logs are
functioning correctly before closing the incident.
