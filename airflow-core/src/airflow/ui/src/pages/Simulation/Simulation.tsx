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
  Button,
  Icon,
} from "@chakra-ui/react";
import {
  FiClock,
  FiCpu,
  FiCheckCircle,
  FiXCircle,
  FiSkipForward,
  FiAlertCircle,
  FiSettings,
  FiBarChart2,
  FiGitBranch,
} from "react-icons/fi";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useDagServiceGetDagDetails } from "openapi/queries";

// --- Types ---
interface ValidationError {
  type: string;
  message: string;
  tasks?: string[];
}

interface ResourceLimitWarning {
  resource: string;
  estimated: number;
  limit: number;
  unit: string;
}

interface SLAMiss {
  task_id: string;
  expected_duration: number;
  sla_threshold: number;
  severity: "warning" | "critical";
}

interface SimulationReport {
  dag_id: string;
  predicted_outcome: string;
  total_duration_seconds: number;
  total_resource_consumption_cpu: number;
  total_wait_time_seconds: number;
  success_tasks: string[];
  failed_tasks: string[];
  skipped_tasks: string[];
  validation_errors: ValidationError[];
  dag_structure_issues: string[];
  config_errors: string[];
  resource_limit_warnings: ResourceLimitWarning[];
  sla_misses: SLAMiss[];
}

// --- Placeholder fetch for a specific simulation ---
const fetchSimulationReport = async (dagId: string, simulationId: string): Promise<SimulationReport> => {
  await new Promise((resolve) => setTimeout(resolve, 500));
  // Return mock data (same as before)
  return {
    dag_id: dagId,
    predicted_outcome: "success",
    total_duration_seconds: 125,
    total_resource_consumption_cpu: 3.5,
    total_wait_time_seconds: 42,
    success_tasks: ["task_a", "task_b", "task_c", "task_d", "task_e", "task_f", "task_g", "task_h"],
    failed_tasks: ["task_i"],
    skipped_tasks: ["task_j", "task_k"],
    validation_errors: [
      {
        type: "Missing Dependency",
        message: "Task 'send_email' depends on non-existent task 'generate_report'.",
        tasks: ["send_email"],
      },
    ],
    dag_structure_issues: ["Orphaned task: 'cleanup' has no dependencies."],
    config_errors: ["Connection 'postgres_default' not found."],
    resource_limit_warnings: [
      {
        resource: "CPU",
        estimated: 3.5,
        limit: 2.0,
        unit: "cores",
      },
    ],
    sla_misses: [
      {
        task_id: "data_processing",
        expected_duration: 180,
        sla_threshold: 120,
        severity: "critical",
      },
    ],
  };
};

// --- Placeholder fetch for the latest simulation (or null if none) ---
const fetchLatestSimulationReport = async (dagId: string): Promise<SimulationReport | null> => {
  await new Promise((resolve) => setTimeout(resolve, 500));
  // Simulate that there is a previous simulation for this DAG.
  // Return null if no simulation ever run.
  // For demo, we'll return a mock report (or null to test placeholder).
  // Adjust as needed: if you want to test the "no simulation" state, change to `null`.
  return {
    dag_id: dagId,
    predicted_outcome: "success",
    total_duration_seconds: 98,
    total_resource_consumption_cpu: 2.8,
    total_wait_time_seconds: 35,
    success_tasks: ["task_a", "task_b", "task_c", "task_d", "task_e", "task_f"],
    failed_tasks: [],
    skipped_tasks: ["task_g"],
    validation_errors: [],
    dag_structure_issues: [],
    config_errors: [],
    resource_limit_warnings: [],
    sla_misses: [],
  };
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

  // Expand/collapse states for each status
  const [showAllSuccess, setShowAllSuccess] = useState(false);
  const [showAllFailed, setShowAllFailed] = useState(false);
  const [showAllSkipped, setShowAllSkipped] = useState(false);

  useEffect(() => {
    if (!dagId) return;

    let cancelled = false;
    const loadReport = async () => {
      setIsLoading(true);
      setError(null);
      try {
        let data: SimulationReport | null = null;

        if (simulationId) {
          // Fetch a specific simulation by ID
          data = await fetchSimulationReport(dagId, simulationId);
          setHasPreviousSimulation(true);
        } else {
          // Fetch the latest simulation for this DAG
          data = await fetchLatestSimulationReport(dagId);
          setHasPreviousSimulation(!!data);
        }

        if (!cancelled) {
          setReport(data);
        }
      } catch (err) {
        if (!cancelled) setError("Failed to load simulation report.");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    loadReport();
    return () => {
      cancelled = true;
    };
  }, [dagId, simulationId]);

  if (!dag) return null;

  const renderTaskTable = (
    title: string,
    tasks: string[],
    color: string,
    state: boolean,
    setState: React.Dispatch<React.SetStateAction<boolean>>,
    icon?: React.ElementType
  ) => {
    const taskCount = tasks.length;
    const visibleTasks = state ? tasks : tasks.slice(0, 3);
    const hasMore = taskCount > 3;

    return (
      <Box>
        <HStack mb={2}>
          {icon && <Icon as={icon} color={color} />}
          <Text fontWeight="bold" color={color}>
            {title}
          </Text>
          <Badge
            colorScheme={color === "green.500" ? "green" : color === "red.500" ? "red" : "gray"}
            ml={2}
          >
            {taskCount}
          </Badge>
        </HStack>
        {taskCount === 0 ? (
          <Text color="fg.muted" fontSize="sm">
            None
          </Text>
        ) : (
          <>
            <Table.Root striped size="sm">
              <Table.Body>
                {visibleTasks.map((task, idx) => (
                  <Table.Row key={idx}>
                    <Table.Cell>{task}</Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
            {hasMore && (
              <Button variant="ghost" size="xs" mt={1} onClick={() => setState(!state)}>
                {state ? "Show less" : `Show all ${taskCount}`}
              </Button>
            )}
          </>
        )}
      </Box>
    );
  };

  // If no simulation has ever been run and we are not currently loading,
  // show a placeholder message.
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
            {/* Summary */}
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
                  Total Duration
                </Text>
                <HStack mt={1}>
                  <Icon as={FiClock} color="fg.muted" />
                  <Text fontSize="lg" fontWeight="bold">
                    {report.total_duration_seconds} seconds
                  </Text>
                </HStack>
              </GridItem>
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                  Total Resource Consumption (CPU)
                </Text>
                <HStack mt={1}>
                  <Icon as={FiCpu} color="blue.500" />
                  <Text fontSize="lg" fontWeight="bold">
                    {report.total_resource_consumption_cpu} cores
                  </Text>
                </HStack>
              </GridItem>
              <GridItem>
                <Text fontSize="sm" fontWeight="medium" color="fg.muted">
                  Total Wait Time
                </Text>
                <HStack mt={1}>
                  <Icon as={FiClock} color="fg.muted" />
                  <Text fontSize="lg" fontWeight="bold">
                    {report.total_wait_time_seconds} seconds
                  </Text>
                </HStack>
              </GridItem>
            </Grid>

            <Box borderTopWidth={1} borderColor="border.emphasized" my={1} />

            {/* Task Status Details */}
            <Box>
              <Heading size="sm" mb={2}>
                Task Status Details
              </Heading>
              <Grid templateColumns="repeat(3, 1fr)" gap={3}>
                <GridItem>
                  {renderTaskTable(
                    "Success Tasks",
                    report.success_tasks,
                    "green.500",
                    showAllSuccess,
                    setShowAllSuccess,
                    FiCheckCircle
                  )}
                </GridItem>
                <GridItem>
                  {renderTaskTable(
                    "Failed Tasks",
                    report.failed_tasks,
                    "red.500",
                    showAllFailed,
                    setShowAllFailed,
                    FiXCircle
                  )}
                </GridItem>
                <GridItem>
                  {renderTaskTable(
                    "Skipped Tasks",
                    report.skipped_tasks,
                    "gray.500",
                    showAllSkipped,
                    setShowAllSkipped,
                    FiSkipForward
                  )}
                </GridItem>
              </Grid>
            </Box>

            <Box borderTopWidth={1} borderColor="border.emphasized" my={1} />

            {/* DAG Structure Issues */}
            {report.dag_structure_issues.length > 0 && (
              <Box>
                <Heading size="md" mb={3}>
                  <HStack>
                    <Icon as={FiGitBranch} color="orange.500" />
                    <Text>DAG Structure Issues</Text>
                    <Badge colorScheme="orange" ml={2}>
                      {report.dag_structure_issues.length}
                    </Badge>
                  </HStack>
                </Heading>
                <Table.Root striped>
                  <Table.Body>
                    {report.dag_structure_issues.map((issue, idx) => (
                      <Table.Row key={idx}>
                        <Table.Cell>{issue}</Table.Cell>
                      </Table.Row>
                    ))}
                  </Table.Body>
                </Table.Root>
              </Box>
            )}

            {/* Validation Errors */}
            {report.validation_errors.length > 0 && (
              <Box>
                <Heading size="md" mb={3}>
                  <HStack>
                    <Icon as={FiAlertCircle} color="red.500" />
                    <Text>Validation Errors</Text>
                    <Badge colorScheme="red" ml={2}>
                      {report.validation_errors.length}
                    </Badge>
                  </HStack>
                </Heading>
                <Table.Root striped>
                  <Table.Body>
                    {report.validation_errors.map((err, idx) => (
                      <Table.Row key={idx}>
                        <Table.Cell>
                          <Text fontWeight="bold">{err.type}</Text>
                          <Text>{err.message}</Text>
                          {err.tasks && (
                            <Text fontSize="sm" color="fg.muted">
                              Tasks: {err.tasks.join(", ")}
                            </Text>
                          )}
                        </Table.Cell>
                      </Table.Row>
                    ))}
                  </Table.Body>
                </Table.Root>
              </Box>
            )}

            {/* Configuration Errors */}
            {report.config_errors.length > 0 && (
              <Box>
                <Heading size="md" mb={3}>
                  <HStack>
                    <Icon as={FiSettings} color="red.500" />
                    <Text>Configuration Errors</Text>
                    <Badge colorScheme="red" ml={2}>
                      {report.config_errors.length}
                    </Badge>
                  </HStack>
                </Heading>
                <Table.Root striped>
                  <Table.Body>
                    {report.config_errors.map((err, idx) => (
                      <Table.Row key={idx}>
                        <Table.Cell>{err}</Table.Cell>
                      </Table.Row>
                    ))}
                  </Table.Body>
                </Table.Root>
              </Box>
            )}

            {/* Resource Limit Warnings */}
            {report.resource_limit_warnings.length > 0 && (
              <Box>
                <Heading size="md" mb={3}>
                  <HStack>
                    <Icon as={FiBarChart2} color="orange.500" />
                    <Text>Resource Limit Warnings</Text>
                    <Badge colorScheme="orange" ml={2}>
                      {report.resource_limit_warnings.length}
                    </Badge>
                  </HStack>
                </Heading>
                <Table.Root striped>
                  <Table.Body>
                    {report.resource_limit_warnings.map((warn, idx) => (
                      <Table.Row key={idx}>
                        <Table.Cell>
                          <Text fontWeight="bold" color="orange.500">
                            {warn.resource}
                          </Text>
                          <Text>
                            Estimated: {warn.estimated} {warn.unit}
                          </Text>
                          <Text>
                            Limit: {warn.limit} {warn.unit}
                          </Text>
                        </Table.Cell>
                      </Table.Row>
                    ))}
                  </Table.Body>
                </Table.Root>
              </Box>
            )}

            {/* SLA Misses */}
            {report.sla_misses.length > 0 && (
              <Box>
                <Heading size="md" mb={3}>
                  <HStack>
                    <Icon as={FiClock} color="red.500" />
                    <Text>SLA Misses</Text>
                    <Badge colorScheme="red" ml={2}>
                      {report.sla_misses.length}
                    </Badge>
                  </HStack>
                </Heading>
                <Table.Root striped>
                  <Table.Body>
                    {report.sla_misses.map((sla, idx) => (
                      <Table.Row key={idx}>
                        <Table.Cell>
                          <Text fontWeight="bold">{sla.task_id}</Text>
                          <Text>Expected duration: {sla.expected_duration}s</Text>
                          <Text>SLA threshold: {sla.sla_threshold}s</Text>
                          <Badge
                            colorScheme={sla.severity === "critical" ? "red" : "orange"}
                            mt={1}
                          >
                            {sla.severity}
                          </Badge>
                        </Table.Cell>
                      </Table.Row>
                    ))}
                  </Table.Body>
                </Table.Root>
              </Box>
            )}
          </>
        )}
      </VStack>
    </Box>
  );
};