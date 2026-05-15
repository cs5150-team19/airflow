/*!
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { describe, it, expect } from "vitest";

import {
  formatProbabilityPercent,
  getSimulationDisplayOptions,
  getSimulationTaskDisplayMetadata,
  type SimulationReportLike,
} from "./simulationDisplay";

const makeReport = (
  overrides: Partial<SimulationReportLike> = {},
): SimulationReportLike => ({
  task_estimates: [
    { task_id: "a", estimated_seconds: 5 },
    { task_id: "b", estimated_seconds: 30 },
    { task_id: "c", estimated_seconds: 10 },
  ],
  critical_path: {
    critical_path: ["a", "b"],
    longest_task: "b",
  },
  ...overrides,
});

describe("getSimulationDisplayOptions", () => {
  it("returns all flags false when no params are set", () => {
    const params = new URLSearchParams();

    expect(getSimulationDisplayOptions(params)).toEqual({
      showCriticalPath: false,
      showDurationBottleneck: false,
      showSuccessProbability: false,
    });
  });

  it("treats sim_cp=1 as enabling critical-path overlay", () => {
    const params = new URLSearchParams("sim_cp=1");

    expect(getSimulationDisplayOptions(params).showCriticalPath).toBe(true);
  });

  it("treats sim_duration=1 as enabling duration-bottleneck overlay", () => {
    const params = new URLSearchParams("sim_duration=1");

    expect(getSimulationDisplayOptions(params).showDurationBottleneck).toBe(true);
  });

  it("treats sim_success=1 as enabling success-probability overlay", () => {
    const params = new URLSearchParams("sim_success=1");

    expect(getSimulationDisplayOptions(params).showSuccessProbability).toBe(true);
  });

  it("does not enable a flag for non-'1' truthy-looking values", () => {
    const params = new URLSearchParams(
      "sim_cp=true&sim_duration=yes&sim_success=on",
    );

    expect(getSimulationDisplayOptions(params)).toEqual({
      showCriticalPath: false,
      showDurationBottleneck: false,
      showSuccessProbability: false,
    });
  });
});

describe("formatProbabilityPercent", () => {
  it("formats whole numbers with one decimal place", () => {
    expect(formatProbabilityPercent(0.75)).toBe("75.0%");
    expect(formatProbabilityPercent(1)).toBe("100.0%");
    expect(formatProbabilityPercent(0)).toBe("0.0%");
  });

  it("rounds to one decimal place", () => {
    expect(formatProbabilityPercent(0.12345)).toBe("12.3%");
    expect(formatProbabilityPercent(0.6789)).toBe("67.9%");
  });
});

describe("getSimulationTaskDisplayMetadata", () => {
  const taskIds = ["a", "b", "c"];

  it("returns no critical-path or bottleneck signals when both flags are off", () => {
    const result = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: false, showDurationBottleneck: false, showSuccessProbability: false },
      undefined,
      makeReport(),
    );

    for (const taskId of taskIds) {
      expect(result[taskId]).toEqual({
        isBottleneck: false,
        isCriticalPath: false,
        metricLabel: undefined,
      });

    }
  });

  it("flags critical-path tasks when showCriticalPath is on", () => {
    const result = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: true, showDurationBottleneck: false, showSuccessProbability: false },
      undefined,
      makeReport(),
    );

    expect(result.a?.isCriticalPath).toBe(true);
    expect(result.b?.isCriticalPath).toBe(true);
    expect(result.c?.isCriticalPath).toBe(false);
  });

  it("filters reported critical-path tasks that are not present in the rendered DAG", () => {
    // Report says ["x", "a"] is the critical path, but "x" isn't in taskIds.
    const result = getSimulationTaskDisplayMetadata(
      ["a", "b"],
      { showCriticalPath: true, showDurationBottleneck: false, showSuccessProbability: false },
      undefined,
      makeReport({
        critical_path: { critical_path: ["x", "a"], longest_task: "x" },
      }),
    );

    expect(result.a?.isCriticalPath).toBe(true);
    expect(result.b?.isCriticalPath).toBe(false);
  });

  it("marks the highest-duration task as the bottleneck when showDurationBottleneck is on", () => {
    const result = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: false, showDurationBottleneck: true, showSuccessProbability: false },
      undefined,
      makeReport(),
    );

    // b is 30s, the largest in the report.
    expect(result.b?.isBottleneck).toBe(true);
    expect(result.a?.isBottleneck).toBe(false);
    expect(result.c?.isBottleneck).toBe(false);
  });

  it("attaches a duration metric label only when bottleneck overlay is on", () => {
    const withFlag = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: false, showDurationBottleneck: true, showSuccessProbability: false },
      undefined,
      makeReport(),
    );
    const withoutFlag = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: false, showDurationBottleneck: false, showSuccessProbability: false },
      undefined,
      makeReport(),
    );

    expect(withFlag.a?.metricLabel).toBe("Dur: 5s");
    expect(withFlag.b?.metricLabel).toBe("Dur: 30s");
    expect(withoutFlag.a?.metricLabel).toBeUndefined();
  });

  it("attaches a success probability label only when success overlay is on", () => {
    const reportWithProbabilities = makeReport({
      task_success_probabilities: { a: 0.9, b: 0.5, c: 0.1 },
    });
    const withFlag = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: false, showDurationBottleneck: false, showSuccessProbability: true },
      undefined,
      reportWithProbabilities,
    );
    const withoutFlag = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: false, showDurationBottleneck: false, showSuccessProbability: false },
      undefined,
      reportWithProbabilities,
    );

    expect(withFlag.a?.metricLabel).toBe("Success: 90.0%");
    expect(withFlag.b?.metricLabel).toBe("Success: 50.0%");
    expect(withFlag.c?.metricLabel).toBe("Success: 10.0%");
    expect(withoutFlag.a?.metricLabel).toBeUndefined();
  });

  it("combines duration and success labels with a separator", () => {
    const reportWithProbabilities = makeReport({
      task_success_probabilities: { a: 0.9, b: 0.5, c: 0.1 },
    });
    const result = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: false, showDurationBottleneck: true, showSuccessProbability: true },
      undefined,
      reportWithProbabilities,
    );

    expect(result.a?.metricLabel).toBe("Dur: 5s | Success: 90.0%");
  });

  it("omits a success label when no probability is available for the task", () => {
    // The report knows about "a" but not "b" or "c"; only "a" should get a label.
    const reportWithProbabilities = makeReport({
      task_success_probabilities: { a: 0.42 },
    });
    const result = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: false, showDurationBottleneck: false, showSuccessProbability: true },
      undefined,
      reportWithProbabilities,
    );

    expect(result.a?.metricLabel).toBe("Success: 42.0%");
    expect(result.b?.metricLabel).toBeUndefined();
    expect(result.c?.metricLabel).toBeUndefined();
  });

  it("returns no bottleneck and no labels when the report is undefined", () => {
    const result = getSimulationTaskDisplayMetadata(
      taskIds,
      { showCriticalPath: true, showDurationBottleneck: true, showSuccessProbability: false },
      undefined,
      undefined,
    );

    for (const taskId of taskIds) {
      expect(result[taskId]).toEqual({
        isBottleneck: false,
        isCriticalPath: false,
        metricLabel: undefined,
      });

    }
  });

  it("ignores tasks present in the report but missing from the rendered DAG", () => {
    // "ghost" is in the report but not in the taskIds list — must not appear in metadata.
    const result = getSimulationTaskDisplayMetadata(
      ["a", "b"],
      { showCriticalPath: false, showDurationBottleneck: true, showSuccessProbability: false },
      undefined,
      {
        task_estimates: [
          { task_id: "a", estimated_seconds: 1 },
          { task_id: "b", estimated_seconds: 2 },
          { task_id: "ghost", estimated_seconds: 999 },
        ],
        critical_path: { critical_path: [], longest_task: "" },
      },
    );

    expect(Object.keys(result).sort()).toEqual(["a", "b"]);
    // Bottleneck must be on-render: b (2s) wins over a (1s); ghost is excluded.
    expect(result.b?.isBottleneck).toBe(true);
    expect(result.a?.isBottleneck).toBe(false);
  });

  it("breaks ties by keeping the first task encountered", () => {
    // a and b tie at 5s. The reduce uses strict ``>``, so the first task to claim
    // the max keeps it — "a" wins because it appears first in the taskIds array.
    const result = getSimulationTaskDisplayMetadata(
      ["a", "b"],
      { showCriticalPath: false, showDurationBottleneck: true, showSuccessProbability: false },
      undefined,
      {
        task_estimates: [
          { task_id: "a", estimated_seconds: 5 },
          { task_id: "b", estimated_seconds: 5 },
        ],
        critical_path: { critical_path: [], longest_task: "" },
      },
    );

    expect(result.a?.isBottleneck).toBe(true);
    expect(result.b?.isBottleneck).toBe(false);
  });
});
