import { Box, Heading, Table, Text } from "@chakra-ui/react";
import { useParams } from "react-router-dom";

import { useDagServiceGetDagDetails } from "openapi/queries";

export const Simulation = () => {
  const { dagId = "" } = useParams();
  const { data: dag } = useDagServiceGetDagDetails({ dagId });

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
        </>
      )}
    </Box>
  );
};