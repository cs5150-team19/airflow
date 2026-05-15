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
import { FiAlertCircle } from "react-icons/fi";

import { useTaskInstanceServiceGetTaskInstances } from "openapi/queries";
import { DurationChart } from "src/components/DurationChart";
import { NeedsReviewButton } from "src/components/NeedsReviewButton";
import TimeRangeSelector from "src/components/TimeRangeSelector";
import { TrendCountButton } from "src/components/TrendCountButton";
import { SearchParamsKeys } from "src/constants/searchParams";
import { isStatePending, useAutoRefresh } from "src/utils";
import { formatProbabilityPercent } from "src/utils/simulationDisplay";

const defaultHour = "24";

interface SimulationTaskEstimate {
  task_id: string;
  operator_type: string;
  estimated_seconds: number;
  confidence: number;
  // Per-task success probability in [0.0, 1.0]. Populated by the fetch helper
  // from the report's ``task_success_probabilities`` map. Optional because
  // reports persisted before the SuccessPredictor backend landed will not
  // include it.
  success_probability?: number;
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

interface SimulationReport {
  task_estimates: SimulationTaskEstimate[];
  task_success_probabilities?: Record<string, number>;
}

const fetchSimulationTaskEstimate = async (
  dagId: string,
  taskId: string,
  simulationId?: string | null,
): Promise<SimulationTaskEstimate | null> => {
  const latestSimulation = simulationId ?? getLatestSimulationRecord(dagId)?.simulationId;

  if (!latestSimulation) {
    return null;
  }

  const response = await fetch(
    `/api/v2/dags/${encodeURIComponent(dagId)}/simulate/${encodeURIComponent(latestSimulation)}`,
  );
  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as SimulationReport;
  const estimate = data.task_estimates.find((te) => te.task_id === taskId);
  if (estimate === undefined) {
    return null;
  }

  return {
    ...estimate,
    success_probability: data.task_success_probabilities?.[taskId],
  };
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
  const [simulationTask, setSimulationTask] = useState<SimulationTaskEstimate | null>(null);
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
      fetchSimulationTaskEstimate(dagId, taskIdentifier, simulationIdFromQuery)
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
              <Heading size="md" mb={0}>
                Simulation Estimate
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
                    Operator Type
                  </Text>
                  <Text fontSize="lg" fontWeight="bold">
                    {simulationTask.operator_type}
                  </Text>
                </GridItem>
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    Estimated Duration
                  </Text>
                  <Text fontSize="lg" fontWeight="bold">
                    {simulationTask.estimated_seconds} seconds
                  </Text>
                </GridItem>
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    Confidence
                  </Text>
                  <Text fontSize="lg" fontWeight="bold">
                    {(simulationTask.confidence * 100).toFixed(0)}%
                  </Text>
                </GridItem>
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    Success Probability
                  </Text>
                  <Text fontSize="lg" fontWeight="bold">
                    {simulationTask.success_probability === undefined
                      ? "—"
                      : formatProbabilityPercent(simulationTask.success_probability)}
                  </Text>
                </GridItem>
              </Grid>
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