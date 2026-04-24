export type SimulationDisplayOptions = {
  showCriticalPath: boolean;
  showDurationBottleneck: boolean;
  showResourceBottleneck: boolean;
  showWaitTimeBottleneck: boolean;
};

export type SimulationTaskDisplayMetadata = {
  isBottleneck: boolean;
  isCriticalPath: boolean;
  metricLabel?: string;
};

type SimulationEdge = {
  source: string;
  target: string;
};

type SimulationTaskMetrics = {
  duration: number;
  resource: number;
  waitTime: number;
};

const hashString = (value: string): number =>
  value.split("").reduce((accumulator, character) => accumulator + character.charCodeAt(0), 0);

const getTaskMetrics = (taskId: string): SimulationTaskMetrics => {
  const hash = hashString(taskId);

  return {
    duration: (hash % 90) + 10,
    resource: Number((((hash % 40) + 10) / 10).toFixed(1)),
    waitTime: (hash % 45) + 5,
  };
};

export const getSimulationDisplayOptions = (searchParams: URLSearchParams): SimulationDisplayOptions => ({
  showCriticalPath: searchParams.get("sim_cp") === "1",
  showDurationBottleneck: searchParams.get("sim_duration") === "1",
  showResourceBottleneck: searchParams.get("sim_resource") === "1",
  showWaitTimeBottleneck: searchParams.get("sim_wait") === "1",
});

const getCriticalPathTaskIds = (taskIds: Array<string>, edges?: Array<SimulationEdge>): Set<string> => {
  if (taskIds.length === 0) {
    return new Set();
  }

  if (!edges || edges.length === 0) {
    const sorted = [...taskIds].sort(
      (first, second) => getTaskMetrics(second).duration - getTaskMetrics(first).duration,
    );
    const takeCount = Math.max(1, Math.ceil(sorted.length * 0.3));

    return new Set(sorted.slice(0, takeCount));
  }

  const taskIdSet = new Set(taskIds);
  const incomingCount = new Map<string, number>(taskIds.map((taskId) => [taskId, 0]));
  const adjacency = new Map<string, Array<string>>(taskIds.map((taskId) => [taskId, []]));

  for (const edge of edges) {
    if (!taskIdSet.has(edge.source) || !taskIdSet.has(edge.target) || edge.source === edge.target) {
      continue;
    }

    adjacency.get(edge.source)?.push(edge.target);
    incomingCount.set(edge.target, (incomingCount.get(edge.target) ?? 0) + 1);
  }

  const originalIncomingCount = new Map(incomingCount);
  const queue: Array<string> = [];
  for (const [taskId, count] of incomingCount.entries()) {
    if (count === 0) {
      queue.push(taskId);
    }
  }

  const topologicalOrder: Array<string> = [];
  while (queue.length > 0) {
    const current = queue.shift();

    if (!current) {
      continue;
    }

    topologicalOrder.push(current);
    for (const next of adjacency.get(current) ?? []) {
      const nextCount = (incomingCount.get(next) ?? 0) - 1;
      incomingCount.set(next, nextCount);
      if (nextCount === 0) {
        queue.push(next);
      }
    }
  }

  if (topologicalOrder.length !== taskIds.length) {
    const sorted = [...taskIds].sort(
      (first, second) => getTaskMetrics(second).duration - getTaskMetrics(first).duration,
    );
    const takeCount = Math.max(1, Math.ceil(sorted.length * 0.3));

    return new Set(sorted.slice(0, takeCount));
  }

  const distance = new Map<string, number>(
    taskIds.map((taskId) => [taskId, Number.NEGATIVE_INFINITY]),
  );
  const predecessor = new Map<string, string | undefined>();

  for (const taskId of topologicalOrder) {
    if ((originalIncomingCount.get(taskId) ?? 0) === 0) {
      distance.set(taskId, getTaskMetrics(taskId).duration);
      predecessor.set(taskId, undefined);
    }
  }

  for (const taskId of topologicalOrder) {
    const currentDistance = distance.get(taskId) ?? Number.NEGATIVE_INFINITY;
    if (currentDistance === Number.NEGATIVE_INFINITY) {
      continue;
    }
    for (const next of adjacency.get(taskId) ?? []) {
      const candidate = currentDistance + getTaskMetrics(next).duration;
      if (candidate > (distance.get(next) ?? Number.NEGATIVE_INFINITY)) {
        distance.set(next, candidate);
        predecessor.set(next, taskId);
      }
    }
  }

  let endNode: string = taskIds[0]!;
  for (const taskId of taskIds) {
    if ((distance.get(taskId) ?? Number.NEGATIVE_INFINITY) > (distance.get(endNode) ?? Number.NEGATIVE_INFINITY)) {
      endNode = taskId;
    }
  }

  const criticalPath = new Set<string>();
  let cursor: string | undefined = endNode;
  while (cursor !== undefined) {
    criticalPath.add(cursor);
    cursor = predecessor.get(cursor);
  }

  return criticalPath;
};

const getMaxTaskIdForMetric = (
  taskIds: Array<string>,
  metric: keyof SimulationTaskMetrics,
): string | undefined =>
  taskIds.reduce<string | undefined>((currentMaxTaskId, taskId) => {
    if (currentMaxTaskId === undefined) {
      return taskId;
    }
    return getTaskMetrics(taskId)[metric] > getTaskMetrics(currentMaxTaskId)[metric] ? taskId : currentMaxTaskId;
  }, undefined);

const getMetricLabel = (taskId: string, options: SimulationDisplayOptions): string | undefined => {
  const metrics = getTaskMetrics(taskId);
  const labels: Array<string> = [];

  if (options.showDurationBottleneck) {
    labels.push(`Dur: ${metrics.duration}s`);
  }
  if (options.showResourceBottleneck) {
    labels.push(`Res: ${metrics.resource} cores`);
  }
  if (options.showWaitTimeBottleneck) {
    labels.push(`Wait: ${metrics.waitTime}s`);
  }

  return labels.length === 0 ? undefined : labels.join(" | ");
};

export const getSimulationTaskDisplayMetadata = (
  taskIds: Array<string>,
  options: SimulationDisplayOptions,
  edges?: Array<SimulationEdge>,
): Record<string, SimulationTaskDisplayMetadata> => {
  const metadata: Record<string, SimulationTaskDisplayMetadata> = {};
  const criticalPathTaskIds = options.showCriticalPath ? getCriticalPathTaskIds(taskIds, edges) : new Set<string>();
  const durationBottleneckTaskId = options.showDurationBottleneck ? getMaxTaskIdForMetric(taskIds, "duration") : undefined;
  const resourceBottleneckTaskId = options.showResourceBottleneck ? getMaxTaskIdForMetric(taskIds, "resource") : undefined;
  const waitTimeBottleneckTaskId = options.showWaitTimeBottleneck ? getMaxTaskIdForMetric(taskIds, "waitTime") : undefined;

  for (const taskId of taskIds) {
    const isBottleneck =
      taskId === durationBottleneckTaskId || taskId === resourceBottleneckTaskId || taskId === waitTimeBottleneckTaskId;

    metadata[taskId] = {
      isBottleneck,
      isCriticalPath: criticalPathTaskIds.has(taskId),
      metricLabel: getMetricLabel(taskId, options),
    };
  }

  return metadata;
};
