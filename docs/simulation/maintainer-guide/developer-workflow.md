# Developer Workflow & Style Guide

## Branching Strategy

- `main` — stable, production-ready code only
- `feature` — integration branch; PRs merge here first before promotion to `main`
- Feature branches — all new features, bug fixes, and experiments; branch off `feature`
- **Merge requirements:** >= 2 approving reviews, all CI checks passing, no unresolved conflicts

## Pull Request Process

1. Implement and test changes locally
2. Push branch and open a pull request targeting the `feature` branch
3. Address all review feedback
4. Obtain 2 approvals and green CI before merge

---

## Coding Standards

### Python

- PEP 8 compliance enforced via `ruff`
- Type annotations required; checked via `mypy`
- Apache license headers required on all new files (checked in CI)
- Use `@pytest.mark.parametrize` for multi-input tests; avoid `unittest.TestCase`
- Test files mirror source structure: `simulation/data/` -> `tests/unit/simulation/data/`

### Frontend (React / TypeScript)

- Component organization follows Airflow's existing conventions
- Styling follows Airflow's existing design system
- No `<form>` elements — use `onClick` / `onChange` event handlers

---

## CI/CD

Every pull request automatically runs:

| Check | Tool |
|---|---|
| Linting | `ruff` |
| License headers | custom CI check |
| Type checking | `mypy` |
| Tests + coverage | `pytest` + `pytest-cov` |

Draft PRs run the unit-only suite. Merge-ready PRs run the full suite including
`@pytest.mark.db_test` and `@pytest.mark.integration`.

---

## Tools

| Tool | Purpose |
|---|---|
| GitHub | Version control and pull request workflow |
| `pytest` / `pytest-cov` | Testing and coverage |
| `ruff` | Python linting |
| `mypy` | Static type checking |
| Docker | Containerization |
| Alembic | Database migrations |
| GitHub Actions | CI/CD automation |
