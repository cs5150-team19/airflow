# Getting Started

- [Local Development Setup](#local-development-setup)
- [Required Software](#required-software)
- [Clone and Install](#clone-and-install)
- [Database Setup](#database-setup)
- [Verifying Your Installation](#verifying-your-installation)
- [Running Your First Simulation](#running-your-first-simulation)

---

## Local Development Setup

This guide covers setting up the simulation feature fork of Airflow locally
for development and testing. This is different from a production deployment —
see [Deployment](../maintainer-guide/deployment.md) for production instructions.

> **Note for contributors:** Airflow's upstream repository also has detailed
> contributor setup docs in `contributing-docs/` at the repo root. Read those
> alongside this guide, as the fork inherits all of Airflow's own dev requirements.

---

## Required Software

Before cloning the repo, make sure you have the following installed:

| Requirement | Version | Notes |
|---|---|---|
| Python | >= 3.10 | Use `pyenv` or your OS package manager |
| PostgreSQL | 14–18 | Required — SQLite is not supported for the simulation feature. The team developed and tested against PostgreSQL 18. |
| Redis | 7.X | Required for the Celery executor in development |

---

## Clone and Install

```bash
# 1. Clone the fork
git clone https://github.com/cs5150-team19/airflow
cd airflow

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install -e ".[devel]"

# 4. Set required environment variables
export AIRFLOW_HOME=~/airflow  # or your preferred location
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://<user>:<password>@localhost/airflow
```

---

## Database Setup

The simulation feature requires PostgreSQL. SQLite will not work.

Database setup is handled via Apache Airflow Breeze, which provides a reproducible
containerized environment with PostgreSQL preconfigured. See `contributing-docs/` in
the repo root for full Breeze setup instructions.

Once your database is running, apply the Airflow schema and simulation migrations:

```bash
airflow db migrate
```

---

## Running Airflow Locally

For quick local development, use:

```bash
airflow standalone
```

This starts the scheduler, API server, and web server in a single process and is the
standard startup path for the simulation fork.

For end-to-end testing against a full PostgreSQL + scheduler + API server stack,
use Apache Airflow Breeze:

```bash
# From the repo root — see contributing-docs/ for full Breeze setup instructions
./scripts/ci/pre_commit/run_breeze.sh
```

---

## Verifying Your Installation

Once Airflow is running, verify the simulation feature is active:

1. Open the Airflow UI (default: `http://localhost:8080`)
2. Check that the **Normal / Simulation toggle** appears in the top navigation bar
3. Confirm the `/api/v2/dags/{dagId}/simulate` endpoint responds:

```bash
curl -X POST http://localhost:8080/api/v2/dags/<your_dag_id>/simulate
```

If the toggle is missing, see [Troubleshooting](troubleshooting.md) — the most common
cause is a stale browser cache.

If the endpoint returns 404, the simulation routes have not been registered —
check the API server startup logs.

---

## Running Your First Simulation

Once your local installation is verified:

1. Locate the **Normal / Simulation toggle** in the top-right corner of the navigation bar
   and switch it to **Simulation Mode**.

   The URL prefix updates to include `/simulation`.

2. Select a DAG from the DAGs list.

3. Click the **Simulation Trigger** button.

4. Open the **Detail Side Panel** on the right to view results.

### Via CLI

```bash
airflow dags simulate --dag-id <your_dag_id>
```

Results print to standard output. Useful for scripting and CI integration.

---

## Next Steps

- [Simulation Mode](simulation-mode.md) — understand how Normal and Simulation modes differ
- [Runtime Estimates](runtime-estimates.md) — interpret confidence scores and per-task estimates
- [Critical Paths & Bottlenecks](critical-paths.md) — use graph overlays to identify bottlenecks
- [Troubleshooting](troubleshooting.md) — fix common setup and runtime issues
