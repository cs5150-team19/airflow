<!--
 Licensed to the Apache Software Foundation (ASF) under one
 or more contributor license agreements.  See the NOTICE file
 distributed with this work for additional information
 regarding copyright ownership.  The ASF licenses this file
 to you under the Apache License, Version 2.0 (the
 "License"); you may not use this file except in compliance
 with the License.  You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing,
 software distributed under the License is distributed on an
 "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 KIND, either express or implied.  See the License for the
 specific language governing permissions and limitations
 under the License.
 -->

# DAG Simulation Feature - Project Overview

## Team

- Aiden Lee
- Connie Chen
- Cristina Lee
- Evan Li
- Jason Zhou

## Feature Description

A side-effect-free simulation environment for previewing DAG executions
in Apache Airflow. Users can view estimated runtimes, identify bottlenecks,
check data types, and validate workflow changes before committing to
actual execution.

## Core Capabilities (MVP)

- DAG execution preview without triggering actual task execution
- Runtime estimation based on historical data
- Dependency visualization and bottleneck identification

## Sprint 1 Goals

- Get Airflow and Docker running locally for all team members
- Set up CI/CD pipelines and testing frameworks
- Familiarize with existing Airflow codebase

## Key Files for Integration

- airflow-core/src/airflow/models/taskinstance.py
- airflow-core/src/airflow/models/dagrun.py
- airflow-core/src/airflow/executors/base_executor.py
- airflow-core/src/airflow/jobs/scheduler_job_runner.py
