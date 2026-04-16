import { Box, Button, VStack, Text } from "@chakra-ui/react";
import { useState } from "react";
import { MdScience, MdExpandLess, MdExpandMore } from "react-icons/md";
import { useSearchParams } from "react-router-dom";

// Use the Chakra v3 Checkbox namespace directly
import { Checkbox as ChakraCheckbox } from "@chakra-ui/react";
import { getSimulationDisplayOptions } from "src/utils/simulationDisplay";

export const SimulationMenu = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const options = getSimulationDisplayOptions(searchParams);

  const toggle = (key: "sim_cp" | "sim_duration" | "sim_resource" | "sim_wait") => {
    const nextSearchParams = new URLSearchParams(searchParams);
    const isEnabled = nextSearchParams.get(key) === "1";

    if (isEnabled) {
      nextSearchParams.delete(key);
    } else {
      nextSearchParams.set(key, "1");
    }

    setSearchParams(nextSearchParams, { replace: true });
  };

  return (
    <Box bottom={4} left={14} position="absolute" zIndex={10}>
      <VStack align="stretch" gap={0}>
        {isOpen && (
          <Box
            bg="bg.panel"
            borderRadius="md"
            borderWidth={1}
            boxShadow="lg"
            mb={2}
            p={3}
            w="220px"
          >
            <VStack align="stretch" gap={3}>
              <Text fontSize="sm" fontWeight="semibold">
                Display Options
              </Text>

              <ChakraCheckbox.Root
                checked={options.showCriticalPath}
                onCheckedChange={() => toggle("sim_cp")}
              >
                <ChakraCheckbox.HiddenInput />
                <ChakraCheckbox.Control />
                <VStack align="start" gap={0}>
                    <ChakraCheckbox.Label>Critical Path</ChakraCheckbox.Label>
                    <Text fontSize="xs" color="gray.600" fontWeight="normal">
                        Display Longest Path with Individual Task Durations
                    </Text>
                </VStack>
              </ChakraCheckbox.Root>

              <ChakraCheckbox.Root
                checked={options.showDurationBottleneck}
                onCheckedChange={() => toggle("sim_duration")}
              >
                <ChakraCheckbox.HiddenInput />
                <ChakraCheckbox.Control />
                <VStack align="start" gap={0}>
                  <ChakraCheckbox.Label>Bottlenecks - Duration</ChakraCheckbox.Label>
                  <Text fontSize="xs" color="gray.600" fontWeight="normal">
                    Display Tasks with the Highest Expected Durations
                  </Text>
                </VStack>
              </ChakraCheckbox.Root>

              <ChakraCheckbox.Root
                checked={options.showResourceBottleneck}
                onCheckedChange={() => toggle("sim_resource")}
              >
                <ChakraCheckbox.HiddenInput />
                <ChakraCheckbox.Control />
                <VStack align="start" gap={0}>
                    <ChakraCheckbox.Label>Bottlenecks - Resource</ChakraCheckbox.Label>
                    <Text fontSize="xs" color="gray.600" fontWeight="normal">
                        Dislay Tasks with the Highest Expected Resource Usage
                    </Text>
                </VStack>
              </ChakraCheckbox.Root>

              <ChakraCheckbox.Root
                checked={options.showWaitTimeBottleneck}
                onCheckedChange={() => toggle("sim_wait")}
              >
                <ChakraCheckbox.HiddenInput />
                <ChakraCheckbox.Control />
                <VStack align="start" gap={0}>
                    <ChakraCheckbox.Label>Bottlenecks - Wait Time</ChakraCheckbox.Label>
                    <Text fontSize="xs" color="gray.600" fontWeight="normal">
                        Dislay Tasks with the Highest Expected Wait Time
                    </Text>
                </VStack>
              </ChakraCheckbox.Root>

            </VStack>
          </Box>
        )}

        <Button
          colorPalette="gray.600"
          onClick={() => setIsOpen((prev) => !prev)}
          size="sm"
          variant="solid"
        >
          <MdScience />
          Simulation Displays
          {isOpen ? <MdExpandMore /> : <MdExpandLess />}
        </Button>
      </VStack>
    </Box>
  );
};