import { Box, Heading, Table, Text, HStack } from "@chakra-ui/react";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { useDagServiceGetDagDetails } from "openapi/queries";
import { TriggerDAGButton } from "src/components/TriggerDag/TriggerDAGButton";

export const Simulation = () => {
  const { dagId = "" } = useParams();
  const { data: dag } = useDagServiceGetDagDetails({ dagId });
  const [searchParams] = useSearchParams();

  type TaskSimulation = {
    readonly task_id: string;
    readonly operator_type: string;
    readonly estimated_seconds: number;
    readonly confidence: number;
  };

  type SimulationResult = {
    readonly simulation_id: string;
    readonly dag_id: string;
    readonly task_estimates: TaskSimulation[];
    readonly total_estimated_seconds: number;
    readonly predicted_outcome: string;
  };

  const [simulationResult, setSimulationResult] = useState<SimulationResult | undefined>(undefined);
  const [isLoadingSimulation, setIsLoadingSimulation] = useState(false);

  useEffect(() => {
    const simulationId = searchParams.get("simulation_id");
    if (!dagId || !simulationId) {
      setSimulationResult(undefined);
      return;
    }

    let cancelled = false;
    const fetchSimulation = async () => {
      setIsLoadingSimulation(true);
      try {
        const response = await fetch(`/api/v2/dags/${dagId}/simulate/${simulationId}`);
        if (!response.ok) {
          return;
        }
        const data = (await response.json()) as SimulationResult;
        if (!cancelled) {
          setSimulationResult(data);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingSimulation(false);
        }
      }
    };

    void fetchSimulation();

    return () => {
      cancelled = true;
    };
  }, [dagId, searchParams]);

  return (
    <Box p={2}>
      {dag === undefined ? (
        <div />
      ) : (
        <>
          <Heading mb={4} size="md">
            Simulation
          </Heading>
          <Text color="fg.muted" mb={4}>
            Configure and run a simulation for <strong>{dag.dag_display_name}</strong>.
          </Text>
          <HStack justifyContent="flex-end" mb={4}>
            <TriggerDAGButton
              allowedRunTypes={dag.allowed_run_types}
              dagDisplayName={dag.dag_display_name}
              dagId={dag.dag_id}
              isPaused={dag.is_paused}
              label="Simulation Trigger"
              variant="outline"
              withText
            />
          </HStack>

          <Table.Root striped>
            <Table.Body>
              <Table.Row>
                <Table.Cell>DAG ID</Table.Cell>
                <Table.Cell>{dag.dag_id}</Table.Cell>
              </Table.Row>
              <Table.Row>
                <Table.Cell>Schedule</Table.Cell>
                <Table.Cell>{dag.timetable_description}</Table.Cell>
              </Table.Row>
            </Table.Body>
          </Table.Root>

          <Box mt={6}>
            <Heading mb={2} size="sm">
              Simulation Summary
            </Heading>
            {isLoadingSimulation ? (
              <Text color="fg.muted">Loading simulation results...</Text>
            ) : simulationResult === undefined ? (
              <Text color="fg.muted">
                Run a simulation to see the predicted outcome and estimated runtime.
              </Text>
            ) : (
              <Table.Root striped>
                <Table.Body>
                  <Table.Row>
                    <Table.Cell>Predicted Outcome</Table.Cell>
                    <Table.Cell>{simulationResult.predicted_outcome}</Table.Cell>
                  </Table.Row>
                  <Table.Row>
                    <Table.Cell>Total Estimated Runtime</Table.Cell>
                    <Table.Cell>{simulationResult.total_estimated_seconds} seconds</Table.Cell>
                  </Table.Row>
                </Table.Body>
              </Table.Root>
            )}
          </Box>
        </>
      )}
    </Box>
  );
};