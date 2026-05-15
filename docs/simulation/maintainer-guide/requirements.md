# Requirements & Specifications

## Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Users can trigger a DAG simulation from the Web UI without executing real tasks | Complete |
| FR-2 | Users can trigger a DAG simulation from the CLI | Complete |
| FR-3 | The system estimates per-task runtime using historical data with a confidence score | Complete |
| FR-4 | The system identifies the critical path and highlights it on the DAG graph | Complete |
| FR-5 | The system identifies the bottleneck task on the critical path | Complete |
| FR-6 | The system predicts a DAG-level outcome (`SUCCESS` / `FAILURE`) | Complete |
| FR-7 | Simulation runs are excluded from historical data used for future predictions | Complete |
| FR-8 | Simulation runs are recorded in the metadata database with `run_type=simulation` and `is_simulation=True` and are visible in Simulation Mode only | Complete |
| FR-9 | The system provides a runtime comparison between simulated estimates and actual historical runtimes | Complete |
| FR-10 | Simulation state (active simulation, overlay configuration) is preserved in the page URL and shareable | Complete |

---

## Nonfunctional Requirements

| Requirement | Description |
|---|---|
| Performance | Simulation completes in reasonable time without blocking the scheduler or API server |
| Reliability | Simulation failures surface clear error messages and do not affect normal DAG operations |
| Scalability | Historical data queries perform acceptably as the number of DAG runs grows |
| Test Coverage | >= 90% line coverage across the `simulation/` module |

---

## Constraints

- **Time:** Developed across four sprints in a single semester
- **Technical:** PostgreSQL (versions 14–18) required as the metadata database backend; SQLite not supported in production for the historical data layer. Team developed and tested against PostgreSQL 18.
- **Compatibility:** Must integrate with Apache Airflow 3.2X without breaking existing functionality

---

## Out of Scope

- Input size prediction (estimating the output size of each task in bytes)
