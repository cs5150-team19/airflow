**Table of contents**

- [Overview](#overview)
- [Documentation Structure](#documentation-structure)
- [Simulation Feature Architecture](#simulation-feature-architecture)
- [Typical Workflows](#typical-workflows)
- [Repository Structure](#repository-structure)

# DAG Simulation Documentation

This directory contains the documentation and handoff materials for the DAG Simulation Feature
developed for Apache Airflow.

The simulation feature introduces side-effect-free DAG execution simulation into Airflow,
allowing users to:

- Simulate DAG execution without triggering real tasks
- Estimate DAG runtime behavior
- Detect workflow bottlenecks
- Visualize critical execution paths
- Predict execution outcomes using historical task data

The feature integrates into Airflow's existing backend, REST API, CLI,
and React frontend.

# Overview

The documentation is separated into multiple sections:

| Directory | Purpose |
|---|---|
| `user-guide/` | Documentation for DAG authors and end users |
| `maintainer-guide/` | Internal architecture and deployment documentation |
| `design/` | UI mockups, diagrams, and design artifacts |
| `demos/` | Demo videos and screenshots |
| `attribution/` | Licensing and ownership agreements |
| `assets/` | Images and diagrams used throughout documentation |

# Documentation Structure

## User Guide

Documentation focused on using the simulation feature.

- [Overview](user-guide/overview.md)
- [Getting Started](user-guide/getting-started.md)
- [Simulation Mode](user-guide/simulation-mode.md)
- [Runtime Estimates](user-guide/runtime-estimates.md)
- [Critical Paths & Bottlenecks](user-guide/critical-paths.md)
- [Troubleshooting](user-guide/troubleshooting.md)
- [FAQ](user-guide/faq.md)

## Maintainer Guide

Documentation focused on development, testing, deployment,
and future maintenance.

- [Architecture](maintainer-guide/architecture.md)
- [Deployment](maintainer-guide/deployment.md)
- [Database](maintainer-guide/database.md)
- [API](maintainer-guide/api.md)
- [Frontend](maintainer-guide/frontend.md)
- [Testing](maintainer-guide/testing.md)
- [Developer Workflow](maintainer-guide/developer-workflow.md)
- [Requirements](maintainer-guide/requirements.md)
- [Rollback Procedures](maintainer-guide/rollback.md)

# Simulation Feature Architecture

The simulation feature consists of several major subsystems:

- Simulation Executor
- Runtime Prediction Engine
- Historical Data Layer
- FastAPI REST API
- React/TypeScript Frontend Extensions
- Critical Path Analyzer
- Bottleneck Detection System

Additional architecture documentation is available in:

- [Architecture Overview](maintainer-guide/architecture.md)
- [Database Design](maintainer-guide/database.md)
- [Frontend Design](maintainer-guide/frontend.md)

# Typical Workflows

Typical workflows supported by the simulation feature include:

- Triggering a DAG simulation from the UI
- Running simulations from the CLI
- Viewing estimated runtimes
- Identifying bottlenecks
- Comparing simulated results against historical runs
- Deploying simulation infrastructure
- Running regression tests

# Repository Structure

```text
docs/simulation/
├── README.md
├── user-guide/
├── maintainer-guide/
├── design/
├── demos/
├── attribution/
└── assets/
```
