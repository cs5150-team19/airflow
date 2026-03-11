import { Box, Button, VStack, Text } from "@chakra-ui/react";
import { useState } from "react";
import { MdScience, MdExpandLess, MdExpandMore } from "react-icons/md";

// Use the Chakra v3 Checkbox namespace directly
import { Checkbox as ChakraCheckbox } from "@chakra-ui/react";

export const SimulationMenu = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [options, setOptions] = useState({
    setCriticalPath: false,
    setDuration: false,
    setResource: false,
    setWaitTime: false
  });

  const toggle = (key: keyof typeof options) =>
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }));

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
                checked={options.setCriticalPath}
                onCheckedChange={() => toggle("setCriticalPath")}
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
                checked={options.setDuration}
                onCheckedChange={() => toggle("setDuration")}
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
                checked={options.setResource}
                onCheckedChange={() => toggle("setResource")}
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
                checked={options.setWaitTime}
                onCheckedChange={() => toggle("setWaitTime")}
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