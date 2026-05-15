# FAQ

**Q: Does simulation trigger real tasks?**

No. No tasks are executed and no operators consume real resources during a simulation run.

---

**Q: Are external APIs called during simulation?**

No. The simulation feature is fully side-effect-free — no real task execution, no external
service calls, and no triggered integrations occur.

---

**Q: How accurate are the runtime estimates?**

Accuracy depends on the amount of historical data available. With at least three prior runs
of the same `(dag_id, task_id)` pair, estimates are typically close to the median observed
runtime. With sparse data, the system falls back to cross-DAG fingerprint matching,
operator-type averaging, or a deterministic heuristic — each with a progressively lower
confidence score. Always consult the confidence score alongside the runtime estimate.

---

**Q: Do simulation runs appear in the Airflow run history?**

A row is written to `dag_run` with `is_simulation=True` and `run_type=simulation`, so
simulation runs are queryable from the metadata database. In the UI, they are scoped to
Simulation Mode and do not appear in Normal Mode run history. Numeric estimates live
in memory only and are not persisted to the database row itself.

---

**Q: Can I run a simulation from the command line?**

Yes:

```bash
airflow dags simulate --dag-id <dag_id>
```

---

**Q: Are simulation runs included in historical data for future predictions?**

No. The historical data layer explicitly excludes rows where `is_simulation=True`,
preventing the predictor from training on its own estimates and creating a feedback loop.
