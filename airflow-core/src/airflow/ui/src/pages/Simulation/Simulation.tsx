import {
  Box,
  Heading,
  Table,
  Text,
  HStack,
  VStack,
  Badge,
  Grid,
  GridItem,
  Icon,
} from "@chakra-ui/react";
import { FiClock } from "react-icons/fi";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useDagServiceGetDagDetails } from "openapi/queries";
import { formatProbabilityPercent } from "src/utils/simulationDisplay";

interface TaskEstimate {
  task_id: string;
  operator_type: string;
  estimated_seconds: number;
  confidence: number;
  // Counts of historical (dag_id, task_id) entries the predictors saw —
  // total, success-state count, failed-state count (failed + upstream_failed).
  // Optional because older simulation reports won't include them.
  historical_total?: number;
  historical_success?: number;
  historical_failed?: number;
}

interface CriticalPathResult {
  critical_path: string[];
  critical_edges: [string, string][];
  longest_task: string;
}

interface SimulationReport {
  simulation_id: string;
  dag_id: string;
  task_estimates: TaskEstimate[];
  total_estimated_seconds: number;
  critical_path: CriticalPathResult;
  predicted_outcome: string;
  // Optional because reports persisted before the SuccessPredictor backend
  // landed will not include them.
  success_probability?: number;
  task_success_probabilities?: Record<string, number>;
}

const getLatestSimulationId = (dagId: string): string | null => {
  if (!dagId) {
    return null;
  }

  const raw = globalThis.localStorage.getItem(`airflow.latestSimulation.${dagId}`);

  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as { simulationId?: string };
    return parsed.simulationId ?? null;
  } catch {
    return null;
  }
};

const fetchSimulationReport = async (dagId: string, simulationId: string): Promise<SimulationReport> => {
  const response = await fetch(
    `/api/v2/dags/${encodeURIComponent(dagId)}/simulate/${encodeURIComponent(simulationId)}`,
  );
  if (!response.ok) {
    throw new Error("Failed to fetch simulation report");
  }
  return response.json();
};

// --- Component ---
export const Simulation = () => {
  const { dagId = "" } = useParams();
  const { data: dag } = useDagServiceGetDagDetails({ dagId });
  const [searchParams] = useSearchParams();
  const simulationId = searchParams.get("simulation_id");

  const [report, setReport] = useState<SimulationReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasPreviousSimulation, setHasPreviousSimulation] = useState<boolean | null>(null);

  useEffect(() => {
    if (!dagId) return;

    let cancelled = false;
    const loadReport = async () => {
      setIsLoading(true);
      setError(null);
      try {
        let data: SimulationReport | null = null;

        if (simulationId) {
          data = await fetchSimulationReport(dagId, simulationId);
          setHasPreviousSimulation(true);
        } else {
          const latestSimulationId = getLatestSimulationId(dagId);
          if (latestSimulationId) {
            data = await fetchSimulationReport(dagId, latestSimulationId);
            setHasPreviousSimulation(true);
          } else {
            data = null;
            setHasPreviousSimulation(false);
          }
        }

        if (!cancelled) {
          setReport(data);
        }
      } catch {
        if (!cancelled) {
          setError("Failed to load simulation report.");
          setReport(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    loadReport();
    return () => {
      cancelled = true;
    };
  }, [dagId, simulationId]);

  if (!dag) return null;

  const showNoSimulationPlaceholder =
    !isLoading && !error && hasPreviousSimulation === false && !report;

  return (
    <Box p={2}>
      <Heading mb={4} size="lg">
        Simulation Results
      </Heading>

      <VStack align="stretch" gap={6}>
        {isLoading && <Text color="fg.muted">Loading simulation report...</Text>}
        {error && <Text color="red.500">{error}</Text>}

        {showNoSimulationPlaceholder && (
          <Box textAlign="center" py={8}>
            <Text fontSize="lg" color="fg.muted">
              No simulation results yet.
            </Text>
            <Text fontSize="sm" color="fg.muted" mt={2}>
              Run a simulation to see predictions for this DAG.
            </Text>
          </Box>
        )}

        {report && !isLoading && (
          <>
            <Heading size="md" mb={0}>
              Summary
            </Heading>
            <Grid templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }} gap={5}>
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                  Predicted Outcome
                </Text>
                <Badge
                  colorScheme={report.predicted_outcome === "success" ? "green" : "red"}
                  fontSize="md"
                  px={2}
                  py={1}
                  mt={1}
                >
                  {report.predicted_outcome.toUpperCase()}
                </Badge>
              </GridItem>
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                  Total Estimated Runtime
                </Text>
                <HStack mt={1}>
                  <Icon as={FiClock} color="fg.muted" />
                  <Text fontSize="lg" fontWeight="bold">
                    {report.total_estimated_seconds} seconds
                  </Text>
                </HStack>
              </GridItem>
              {report.success_probability !== undefined ? (
                <GridItem>
                  <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                    DAG Success Probability
                  </Text>
                  <Text fontSize="lg" fontWeight="bold" mt={1}>
                    {formatProbabilityPercent(report.success_probability)}
                  </Text>
                </GridItem>
              ) : null}
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                  Task Count
                </Text>
                <Text fontSize="lg" fontWeight="bold" mt={1}>
                  {report.task_estimates.length}
                </Text>
              </GridItem>
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                  Longest Critical Task
                </Text>
                <Text fontSize="lg" fontWeight="bold" mt={1}>
                  {report.critical_path.longest_task}
                </Text>
              </GridItem>
            </Grid>

            <Box borderTopWidth={1} borderColor="border.emphasized" my={1} />

            <Box>
              <Heading size="md" mb={3}>
                Task Estimates
              </Heading>
              <Table.Root striped size="sm">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Task</Table.ColumnHeader>
                    <Table.ColumnHeader>Operator</Table.ColumnHeader>
                    <Table.ColumnHeader>Estimated Seconds</Table.ColumnHeader>
                    <Table.ColumnHeader>Confidence</Table.ColumnHeader>
                    <Table.ColumnHeader>Success Probability</Table.ColumnHeader>
                    <Table.ColumnHeader>History (Total)</Table.ColumnHeader>
                    <Table.ColumnHeader>Succeeded</Table.ColumnHeader>
                    <Table.ColumnHeader>Failed</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {report.task_estimates.map((taskEstimate) => {
                    const probability = report.task_success_probabilities?.[taskEstimate.task_id];
                    // History columns render "—" when there is zero same-(dag_id,
                    // task_id) data — the predictor fell back to operator-type
                    // history or the deterministic heuristic.
                    const total = taskEstimate.historical_total ?? 0;
                    const hasHistory = total > 0;

                    return (
                      <Table.Row key={taskEstimate.task_id}>
                        <Table.Cell>{taskEstimate.task_id}</Table.Cell>
                        <Table.Cell>{taskEstimate.operator_type}</Table.Cell>
                        <Table.Cell>{taskEstimate.estimated_seconds}</Table.Cell>
                        <Table.Cell>{(taskEstimate.confidence * 100).toFixed(0)}%</Table.Cell>
                        <Table.Cell>
                          {probability === undefined ? "—" : formatProbabilityPercent(probability)}
                        </Table.Cell>
                        <Table.Cell>{hasHistory ? total : "—"}</Table.Cell>
                        <Table.Cell>
                          {hasHistory ? (taskEstimate.historical_success ?? 0) : "—"}
                        </Table.Cell>
                        <Table.Cell>
                          {hasHistory ? (taskEstimate.historical_failed ?? 0) : "—"}
                        </Table.Cell>
                      </Table.Row>
                    );
                  })}
                </Table.Body>
              </Table.Root>
            </Box>

            <Box borderTopWidth={1} borderColor="border.emphasized" my={1} />

            <Box>
              <Heading size="md" mb={3}>
                Critical Path
              </Heading>
              <Text color="fg.muted" mb={2}>
                Longest task: <strong>{report.critical_path.longest_task}</strong>
              </Text>
              <Text color="fg.muted" mb={2}>
                Path: {report.critical_path.critical_path.join(" → ")}
              </Text>
              <Text color="fg.muted">
                Critical edges: {report.critical_path.critical_edges.length}
              </Text>
            </Box>
          </>
        )}
      </VStack>
    </Box>
  );
};