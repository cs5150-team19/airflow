export type SimulationDisplayOptions = {
  showCriticalPath: boolean;
  showDurationBottleneck: boolean;
  showSuccessProbability: boolean;
};

export type SimulationTaskDisplayMetadata = {
  isBottleneck: boolean;
  isCriticalPath: boolean;
  metricLabel?: string;
};

export type SimulationTaskEstimate = {
  task_id: string;
  estimated_seconds: number;
};

export type SimulationCriticalPath = {
  critical_path: Array<string>;
  longest_task: string;
};

export type SimulationReportLike = {
  task_estimates: Array<SimulationTaskEstimate>;
  critical_path: SimulationCriticalPath;
  // Per-task success probability in [0.0, 1.0], keyed by task_id. Optional
  // because reports produced before the SuccessPredictor backend landed will
  // not include it.
  task_success_probabilities?: Record<string, number>;
  // DAG-level success probability in [0.0, 1.0]. Optional for the same reason.
  success_probability?: number;
};

// Format a probability in [0.0, 1.0] as a one-decimal percentage string.
export const formatProbabilityPercent = (probability: number): string =>
  `${(probability * 100).toFixed(1)}%`;

type SimulationEdge = {
  source: string;
  target: string;
};

const getEstimatedSecondsByTaskId = (
  simulationReport?: SimulationReportLike,
): Map<string, number> =>
  new Map(
    (simulationReport?.task_estimates ?? []).map((taskEstimate) => [
      taskEstimate.task_id,
      taskEstimate.estimated_seconds,
    ]),
  );

export const getSimulationDisplayOptions = (searchParams: URLSearchParams): SimulationDisplayOptions => ({
  showCriticalPath: searchParams.get("sim_cp") === "1",
  showDurationBottleneck: searchParams.get("sim_duration") === "1",
  showSuccessProbability: searchParams.get("sim_success") === "1",
});

const getCriticalPathTaskIds = (
  taskIds: Array<string>,
  _edges?: Array<SimulationEdge>,
  simulationReport?: SimulationReportLike,
): Set<string> => {
  const taskIdSet = new Set(taskIds);
  const reportedCriticalPath = simulationReport?.critical_path.critical_path.filter((taskId) =>
    taskIdSet.has(taskId),
  );

  return new Set(reportedCriticalPath ?? []);
};

const getMaxTaskIdForMetric = (
  taskIds: Array<string>,
  metric: "duration",
  simulationReport?: SimulationReportLike,
): string | undefined => {
  const estimatedSecondsByTaskId = getEstimatedSecondsByTaskId(simulationReport);

  return taskIds.reduce<string | undefined>((currentMaxTaskId, taskId) => {
    if (metric === "duration") {
      if (simulationReport === undefined) {
        return undefined;
      }
      const currentEstimate = estimatedSecondsByTaskId.get(taskId);
      if (currentEstimate === undefined) {
        return currentMaxTaskId;
      }
      if (currentMaxTaskId === undefined) {
        return taskId;
      }
      const maxEstimate = estimatedSecondsByTaskId.get(currentMaxTaskId);
      if (maxEstimate === undefined) {
        return taskId;
      }
      return currentEstimate > maxEstimate ? taskId : currentMaxTaskId;
    }
    return currentMaxTaskId;
  }, undefined);
};

const getMetricLabel = (
  taskId: string,
  options: SimulationDisplayOptions,
  simulationReport?: SimulationReportLike,
): string | undefined => {
  const estimatedSecondsByTaskId = getEstimatedSecondsByTaskId(simulationReport);
  const labels: Array<string> = [];

  if (options.showDurationBottleneck) {
    const estimatedSeconds = estimatedSecondsByTaskId.get(taskId);
    if (estimatedSeconds !== undefined) {
      labels.push(`Dur: ${estimatedSeconds}s`);
    }
  }

  if (options.showSuccessProbability) {
    const probability = simulationReport?.task_success_probabilities?.[taskId];
    if (probability !== undefined) {
      labels.push(`Success: ${formatProbabilityPercent(probability)}`);
    }
  }

  return labels.length === 0 ? undefined : labels.join(" | ");
};

export const getSimulationTaskDisplayMetadata = (
  taskIds: Array<string>,
  options: SimulationDisplayOptions,
  edges?: Array<SimulationEdge>,
  simulationReport?: SimulationReportLike,
): Record<string, SimulationTaskDisplayMetadata> => {
  const metadata: Record<string, SimulationTaskDisplayMetadata> = {};
  const criticalPathTaskIds = options.showCriticalPath
    ? getCriticalPathTaskIds(taskIds, edges, simulationReport)
    : new Set<string>();
  const durationBottleneckTaskId = options.showDurationBottleneck
    ? getMaxTaskIdForMetric(taskIds, "duration", simulationReport)
    : undefined;

  for (const taskId of taskIds) {
    const isBottleneck =
      taskId === durationBottleneckTaskId;

    metadata[taskId] = {
      isBottleneck,
      isCriticalPath: criticalPathTaskIds.has(taskId),
      metricLabel: getMetricLabel(taskId, options, simulationReport),
    };
  }

  return metadata;
};
