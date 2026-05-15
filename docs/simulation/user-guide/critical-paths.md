# Critical Paths & Bottlenecks

## What Is the Critical Path?

The critical path is the longest sequence of dependent tasks through the DAG —
the sequence that determines the **Total Estimated Runtime**. Parallel branches
contribute only their maximum duration, not their sum.

## Enabling Overlays

With a simulation active, navigate to the **Graph view** and open **Display Options**
in the Detail Side Panel.

| Overlay | What It Shows |
|---|---|
| Critical Path | Longest dependent task sequence, highlighted in red |
| Bottleneck | The task on the critical path with the highest individual estimated runtime, visually flagged |

## Interpreting Results

Click the flagged bottleneck task to open its **Task Instance side panel**, which shows:
- Estimated runtime
- Confidence score
- Predictor source
- Operator type

## Common Follow-Up Actions

- Split a long-running task into smaller parallel tasks
- Replace a slow operator with a more efficient alternative
- Investigate why a task's historical runtime is high relative to similar tasks
- Review upstream dependencies or input data for inefficiencies

## Overlay State and Sharing

Overlay configuration is controlled via URL search parameters managed by `simulationDisplay.ts`.
Copying the page URL preserves both the active simulation and overlay state for sharing
or bookmarking.
