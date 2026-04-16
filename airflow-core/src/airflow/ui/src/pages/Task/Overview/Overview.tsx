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
import {
  Box,
  HStack,
  Skeleton,
  SimpleGrid,
  Badge,
  Text,
  VStack,
  Heading,
  Grid,
  GridItem,
  Icon,
} from "@chakra-ui/react";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useLocation, useSearchParams } from "react-router-dom";
import { FiClock, FiCpu, FiDatabase, FiAlertCircle } from "react-icons/fi";

import { useTaskInstanceServiceGetTaskInstances } from "openapi/queries";
import { DurationChart } from "src/components/DurationChart";
import { NeedsReviewButton } from "src/components/NeedsReviewButton";
import TimeRangeSelector from "src/components/TimeRangeSelector";
import { TrendCountButton } from "src/components/TrendCountButton";
import { SearchParamsKeys } from "src/constants/searchParams";
import { isStatePending, useAutoRefresh } from "src/utils";

const defaultHour = "24";

// --- Mock data for simulation mode (single task) ---
interface SimulationTaskInstance {
  task_id: string;
  status: "success" | "failed" | "skipped" | "upstream_failed";
  duration_seconds: number;
  start_time: string;
  end_time: string;
  estimated_resource_usage: {
    time_complexity: string;
    space_complexity: string;
  };
  input_output: {
    input_source: string;
    input_type: string;
    output_source: string;
    output_type: string;
  };
  error?: string;
}

type LatestSimulationRecord = {
  simulationId: string;
  triggeredAt: string;
};

const getLatestSimulationRecord = (dagId: string): LatestSimulationRecord | null => {
  if (!dagId) {
    return null;
  }
  const raw = globalThis.localStorage.getItem(`airflow.latestSimulation.${dagId}`);

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as LatestSimulationRecord;
  } catch {
    return null;
  }
};

const hashString = (value: string): number =>
  value.split("").reduce((accumulator, char) => accumulator + char.charCodeAt(0), 0);

const deriveSimulationResult = (taskId: string, seed: string): SimulationTaskInstance => {
  const hash = hashString(`${taskId}:${seed}`);
  const base = dayjs().subtract(hash % 20, "minute");
  const duration = (hash % 40) + 5;
  const states: Array<SimulationTaskInstance["status"]> = ["success", "failed", "skipped", "upstream_failed"];
  const status = states[hash % states.length] ?? "success";

  return {
    task_id: taskId,
    status,
    duration_seconds: duration,
    end_time: base.add(duration, "second").toISOString(),
    error: status === "failed" ? "Simulation predicts this task may fail due to input constraints." : undefined,
    estimated_resource_usage: {
      space_complexity: hash % 2 === 0 ? "O(1)" : "O(n)",
      time_complexity: hash % 3 === 0 ? "O(n)" : "O(1)",
    },
    input_output: {
      input_source: "upstream task output",
      input_type: "json",
      output_source: status === "failed" ? "none" : "task output",
      output_type: status === "failed" ? "" : "json",
    },
    start_time: base.toISOString(),
  };
};

// Placeholder API call – replace with real endpoint later
const fetchSimulationTaskInstance = async (
  dagId: string,
  taskId: string,
  simulationId?: string | null,
): Promise<SimulationTaskInstance | null> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  const latestSimulation = simulationId ?? getLatestSimulationRecord(dagId)?.simulationId;

  if (!latestSimulation) {
    return null;
  }

  return deriveSimulationResult(taskId, latestSimulation);
};

// Helper functions
const formatDuration = (seconds: number): string => {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) return `${hrs} hr ${mins} min ${secs} sec`;
  if (mins > 0) return `${mins} min ${secs} sec`;
  return `${secs} sec`;
};

const formatTime = (isoString: string): string => {
  if (!isoString) return "—";
  return dayjs(isoString).format("hh:mm:ss A");
};

export const Overview = () => {
  const { dagId = "", groupId, taskId } = useParams();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const isSimulating = location.pathname.includes("/simulation");
  const { t: translate } = useTranslation("dag");

  const now = dayjs();
  const [startDate, setStartDate] = useState(now.subtract(Number(defaultHour), "hour").toISOString());
  const [endDate, setEndDate] = useState(now.toISOString());

  const refetchInterval = useAutoRefresh({});

  // Normal mode data (unchanged)
  const { data: failedTaskInstances, isLoading: isFailedTaskInstancesLoading } =
    useTaskInstanceServiceGetTaskInstances({
      dagId,
      dagRunId: "~",
      limit: 14,
      runAfterGte: startDate,
      runAfterLte: endDate,
      state: ["failed"],
      taskGroupId: groupId ?? undefined,
      taskId: Boolean(groupId) ? undefined : taskId,
    });

  const { data: tiData, isLoading: isLoadingTaskInstances } = useTaskInstanceServiceGetTaskInstances(
    {
      dagId,
      dagRunId: "~",
      limit: 14,
      orderBy: ["-run_after"],
      taskGroupId: groupId ?? undefined,
      taskId: Boolean(groupId) ? undefined : taskId,
    },
    undefined,
    {
      refetchInterval: (query) =>
        query.state.data?.task_instances.some((ti) => isStatePending(ti.state)) ? refetchInterval : false,
    },
  );

  // Simulation mode state
  const [simulationTask, setSimulationTask] = useState<SimulationTaskInstance | null>(null);
  const [isLoadingSimulation, setIsLoadingSimulation] = useState(false);
  const taskIdentifier = taskId || groupId;
  const simulationIdFromQuery = searchParams.get("simulation_id");
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    const onSimulationTriggered = (event: Event) => {
      const simulationEvent = event as CustomEvent<{ dagId: string }>;

      if (simulationEvent.detail?.dagId === dagId) {
        setRefreshToken((value) => value + 1);
      }
    };

    globalThis.addEventListener("airflow:simulation-triggered", onSimulationTriggered);

    return () => {
      globalThis.removeEventListener("airflow:simulation-triggered", onSimulationTriggered);
    };
  }, [dagId]);

  useEffect(() => {
    if (isSimulating && dagId && taskIdentifier) {
      setIsLoadingSimulation(true);
      fetchSimulationTaskInstance(dagId, taskIdentifier, simulationIdFromQuery)
        .then(data => setSimulationTask(data))
        .finally(() => setIsLoadingSimulation(false));
    } else if (isSimulating && !taskIdentifier) {
      setSimulationTask(null);
    }
  }, [isSimulating, dagId, taskIdentifier, simulationIdFromQuery, refreshToken]);

  // ========== Simulation View ==========
  if (isSimulating) {
    return (
      <Box p={2}>
        <Heading mb={4} size="lg">
          Simulation Results
        </Heading>

        <VStack align="stretch" gap={6}>
          {isLoadingSimulation && <Text color="fg.muted">Loading simulation data...</Text>}
          {!isLoadingSimulation && !simulationTask && (
            <Box textAlign="center" py={8}>
              <Icon as={FiAlertCircle} boxSize={8} color="fg.muted" mb={2} />
              <Text color="fg.muted">
                No simulation results available for this task yet.
                <br />
                Run a simulation to see estimated outcomes.
              </Text>
            </Box>
          )}

          {simulationTask && !isLoadingSimulation && (
            <>
              {/* Summary */}
              <Heading size="md" mb={0}>
                Summary
              </Heading>
              <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }} gap={5}>
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    Task ID
                  </Text>
                  <Text fontSize="lg" fontWeight="bold">
                    {simulationTask.task_id}
                  </Text>
                </GridItem>
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    Status
                  </Text>
                  <Badge
                    colorScheme={
                      simulationTask.status === "success"
                        ? "green"
                        : simulationTask.status === "failed"
                          ? "red"
                          : simulationTask.status === "skipped"
                            ? "gray"
                            : "orange"
                    }
                    fontSize="md"
                    px={2}
                    py={1}
                    mt={1}
                  >
                    {simulationTask.status.toUpperCase().replace("_", " ")}
                  </Badge>
                </GridItem>
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    Duration
                  </Text>
                  <HStack mt={1}>
                    <Icon as={FiClock} color="fg.muted" />
                    <Text fontSize="lg" fontWeight="bold">
                      {formatDuration(simulationTask.duration_seconds)}
                    </Text>
                  </HStack>
                </GridItem>
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    Start Time
                  </Text>
                  <Text fontSize="lg" fontWeight="bold">
                    {formatTime(simulationTask.start_time)}
                  </Text>
                </GridItem>
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    End Time
                  </Text>
                  <Text fontSize="lg" fontWeight="bold">
                    {formatTime(simulationTask.end_time)}
                  </Text>
                </GridItem>
              </Grid>

              <Box borderTopWidth={1} borderColor="border.emphasized" my={1} />

              {/* Estimated Resource Usage */}
              <Box>
                <Heading size="md" mb={3}>
                  <HStack>
                    <Icon as={FiCpu} color="blue.500" />
                    <Text>Estimated Resource Usage</Text>
                  </HStack>
                </Heading>
                <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }} gap={5}>
                  <GridItem>
                    <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                      Time Complexity
                    </Text>
                    <Text fontSize="lg" fontWeight="bold">
                      {simulationTask.estimated_resource_usage.time_complexity}
                    </Text>
                  </GridItem>
                  <GridItem>
                    <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                      Space Complexity
                    </Text>
                    <Text fontSize="lg" fontWeight="bold">
                      {simulationTask.estimated_resource_usage.space_complexity}
                    </Text>
                  </GridItem>
                </Grid>
              </Box>

              <Box borderTopWidth={1} borderColor="border.emphasized" my={1} />

              {/* Input/Output */}
              <Box>
                <Heading size="md" mb={3}>
                  <HStack>
                    <Icon as={FiDatabase} color="green.500" />
                    <Text>Input / Output</Text>
                  </HStack>
                </Heading>
                <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }} gap={5}>
                  <GridItem>
                    <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                      Input Source
                    </Text>
                    <Text fontWeight="bold">{simulationTask.input_output.input_source}</Text>
                    {simulationTask.input_output.input_type && (
                      <Text fontSize="sm" color="fg.muted">
                        Type: {simulationTask.input_output.input_type}
                      </Text>
                    )}
                  </GridItem>
                  <GridItem>
                    <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                      Output Source
                    </Text>
                    <Text fontWeight="bold">{simulationTask.input_output.output_source}</Text>
                    {simulationTask.input_output.output_type && (
                      <Text fontSize="sm" color="fg.muted">
                        Type: {simulationTask.input_output.output_type}
                      </Text>
                    )}
                  </GridItem>
                </Grid>
              </Box>

              {/* Errors (if any) */}
              {simulationTask.status === "failed" && simulationTask.error && (
                <Box>
                  <Heading size="md" mb={3}>
                    <HStack>
                      <Icon as={FiAlertCircle} color="red.500" />
                      <Text>Error</Text>
                    </HStack>
                  </Heading>
                  <Box p={0} borderRadius="sm">
                    <Text fontWeight="bold">
                      {simulationTask.error}
                    </Text>
                  </Box>
                </Box>
              )}
            </>
          )}
        </VStack>
      </Box>
    );
  }

  // ========== Normal View (unchanged) ==========
  return (
    <Box m={4} spaceY={4}>
      <NeedsReviewButton taskId={taskId} />
      <Box my={2}>
        <TimeRangeSelector
          defaultValue={defaultHour}
          endDate={endDate}
          setEndDate={setEndDate}
          setStartDate={setStartDate}
          startDate={startDate}
        />
      </Box>
      <HStack flexWrap="wrap">
        <TrendCountButton
          colorPalette={(failedTaskInstances?.total_entries ?? 0) === 0 ? "green" : "red"}
          count={failedTaskInstances?.total_entries ?? 0}
          endDate={endDate}
          events={(failedTaskInstances?.task_instances ?? []).map((ti) => ({
            timestamp: ti.start_date ?? ti.logical_date,
          }))}
          isLoading={isFailedTaskInstancesLoading}
          label={translate("overview.buttons.failedTaskInstance", {
            count: failedTaskInstances?.total_entries ?? 0,
          })}
          route={{
            pathname: "task_instances",
            search: `${SearchParamsKeys.TASK_STATE}=failed`,
          }}
          startDate={startDate}
        />
      </HStack>
      <SimpleGrid columns={3} gap={5} my={5}>
        <Box borderRadius={4} borderStyle="solid" borderWidth={1} p={2} width="350px">
          {isLoadingTaskInstances ? (
            <Skeleton height="200px" w="full" />
          ) : (
            <DurationChart entries={tiData?.task_instances.slice().reverse()} kind="Task Instance" />
          )}
        </Box>
      </SimpleGrid>
    </Box>
  );
};