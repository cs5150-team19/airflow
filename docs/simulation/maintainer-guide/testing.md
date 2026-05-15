# Testing

## Strategy

Tests are written alongside each feature in the same pull request — no feature is merged
without corresponding tests. The approach combines unit testing and manual usability
testing to cover both technical correctness and user experience.

### Infrastructure Requirements

- Local Python environment with `apache-airflow`, `pytest`, and `pytest-cov` installed
- No running Airflow instance, Docker, or external database required for unit tests
- Database-dependent tests use Airflow's `dag_maker` fixture with in-memory SQLite
- Algorithm logic tests mock the database layer for speed and isolation

### Test Markers

| Marker | When It Runs |
|---|---|
| _(no marker)_ | All CI runs, including draft PRs |
| `@pytest.mark.db_test` | Full CI suite (merge-ready PRs only) |
| `@pytest.mark.integration` | Separate integration suite |

### Running Tests

```bash
# Unit tests only
pytest tests/unit

# Integration tests
pytest tests/integration -m integration

# Full suite with coverage
pytest --cov=airflow/simulation tests/
```

Coverage target: **>= 90%** across `simulation/`.

---

## Unit Test Coverage

| File | Tests | What It Covers | Status |
|---|---|---|---|
| `test_predictor_interface.py` | — | `DeterministicPredictor`, `TaskRuntimeEstimate`, DAG estimate aggregation, default predicted outcome | Complete |
| `test_simulation_executor.py` | — | `SimulationExecutor`: task success/failure events, predictor metadata, callback handling, outcome parsing | Complete |
| `predictors/test_historical_predictor.py` | 38 | 3-level fallback chain, aggregation methods, confidence scoring, outlier filtering | Complete (Sprint 3) |
| `predictors/test_success_predictor.py` | — | Success probability from task/DagRun history | Complete |
| `data/test_historical_data_extractor.py` | 18 | DB retrieval, state filtering, date range, ordering, pagination, isolation | Complete (Sprint 3) |
| `test_critical_path.py` | 12 | Kahn's algorithm, critical path selection, isolation, edge cases | Complete (Sprint 4) |
| `test_bottleneck.py` | 4 | Bottleneck extraction, tie-breaking, empty edge cases | Complete (Sprint 4) |
| `test_fingerprint.py` | — | Cross-DAG task fingerprint generation | Complete |
| `api_fastapi/.../test_simulation.py` | — | API endpoint for `/dags/{dag_id}/simulate` | Complete |
| `models/test_taskinstance_simulation.py` | — | Simulation-related `TaskInstance` fields and `run_simulation()` | Complete |
| `migrations/test_simulation_migration.py` | — | Alembic migration structure for simulation DB columns | Complete |

---

## Integration & UAT

Integration tests cover the full path: API request -> predictor -> database query -> response.
They use Airflow's pytest test client against a temporary SQLite instance and are
marked `@pytest.mark.integration`.

> **Status:** Planned for Sprint 4 after UI, API, and CLI branches merge.

User acceptance testing is possible once the UI displays simulation results.

> **Status:** Scheduled immediately after integration testing completes.

---

## Manual & Usability Testing

Informal usability testing was conducted with three participants (15-20 min sessions each).

| Participant | Background | Key Finding |
|---|---|---|
| CS Junior | Python, limited Airflow experience | Confused by total runtime vs. sum of task runtimes; understood after seeing critical path |
| CS Senior | Data workflow experience | Wanted clearer labeling of estimate source (historical vs. heuristic), not just confidence tier |
| CS Senior | Business process / workflow tools background | Found visual dependency preview helpful; flagged Airflow terminology as a barrier for new users |

### Issues Identified

| Issue | Severity | Suggested Fix |
|---|---|---|
| UI doesn't explain how total runtime is calculated | Medium | Add tooltip or inline note in Summary section explaining critical path vs. sum |
| Confidence score alone insufficient to understand estimate source | Medium | Show predictor source label alongside confidence score |
| Display Options panel has low visibility | Medium | Move closer to the diagram or expand the panel; auto-open after simulation trigger |
| Interface assumes Airflow knowledge | Low | Add contextual tooltips for key terms (critical path, DAG, operator) |
