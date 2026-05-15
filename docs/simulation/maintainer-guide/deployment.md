# Deployment

## Prerequisites

| Component | Version |
|---|---|
| Python | >= 3.10 |
| Apache Airflow | 3.2X |
| PostgreSQL | 14–18 (team tested against 18) |
| Redis | 7.X |

## Setup

```bash
git clone https://github.com/cs5150-team19/airflow
cd airflow
python -m venv venv
source venv/bin/activate
pip install -e ".[devel]"
airflow db migrate
airflow standalone
```

## Enabling the Simulation Feature

The following environment variables are required for a functioning Airflow deployment:

```bash
export AIRFLOW_HOME=~/airflow
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://<user>:<password>@localhost/airflow
export AIRFLOW__CELERY__BROKER_URL=redis://localhost:6379/0
```

---

## Pre-Deployment Checklist

- [ ] All PRs reviewed by >= 2 team members and merged
- [ ] CI/CD pipeline passes fully (ruff, mypy, license headers, full pytest suite)
- [ ] Test coverage >= 90% across `simulation/`
- [ ] Alembic migration scripts tested for both `up` and `down` directions
- [ ] Feature branch rebased against latest upstream Airflow `main`

## Deployment Steps

1. Pull the latest feature branch commit that passed all CI checks
2. Build the custom Docker image: `docker build .`
3. Back up the existing PostgreSQL metadata database
4. Run Alembic up-migrations: `airflow db migrate`
5. Restart Airflow scheduler, API server, and workers in sequence —
   **scheduler last**, after DB migration is confirmed
6. Verify `/api/v2/dags/{dagId}/simulate` responds correctly with a test DAG
7. Confirm the Simulation Mode toggle appears in the UI and Simulation Trigger works
8. Run a smoke test on a simple known DAG and verify predicted outcome
   and runtime estimates appear

See [Rollback Procedures](rollback.md) for rollback triggers and steps.
