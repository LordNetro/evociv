# Spec: dialogue-system

## Purpose

Define the frontend visual dialogue layer: 3D speech/thought bubbles above agents and a Social filter in the EventLog panel.

## Requirements

### Requirement: Speech Bubble 3D Rendering

When an agent's snapshot payload includes `dialogue_type="speech"` and a non-null `current_dialogue`, the 3D canvas SHALL render a comic-style speech bubble above that agent using Threlte's `<HTML>` component. The bubble SHALL auto-dismiss after approximately 3 seconds or when `current_dialogue` becomes `null`.

#### Scenario: Speech bubble appears and fades out

- GIVEN an agent with `dialogue_type="speech"` and `current_dialogue="Hello!"` in the snapshot
- WHEN the frontend processes the snapshot
- THEN a comic-style bubble with text "Hello!" is rendered above the agent
- AND the bubble fades out after ~3 seconds

### Requirement: Thought Bubble 3D Rendering

When `dialogue_type="thought"` and `current_dialogue` is non-null, the canvas SHALL render a thought cloud (dotted outline, italic text) above the agent. Same auto-dismiss behavior as speech bubbles.

#### Scenario: Thought bubble appears

- GIVEN an agent with `dialogue_type="thought"` and `current_dialogue="I need water"`
- WHEN the frontend processes the snapshot
- THEN a thought cloud with italic text "I need water" and dotted outline is rendered above the agent

#### Scenario: Dialogue type defaults to no bubble

- GIVEN an agent with `current_dialogue=None`
- WHEN the snapshot is rendered
- THEN no bubble is shown above the agent

### Requirement: Visual Distinction Between Speech and Thought

Speech bubbles and thought bubbles SHALL use visually distinct styles: speech uses a solid border and regular font weight; thought uses a dashed border, italic text, and a cloud-like shape.

#### Scenario: Both bubble types coexist

- GIVEN two agents with `dialogue_type="speech"` and `dialogue_type="thought"` respectively
- WHEN rendered simultaneously
- THEN each bubble follows its distinct style

### Requirement: Social EventLog Filter

The EventLog panel SHALL provide a "Social" filter option that displays only events of type `"dialogue"`, formatted as `"SenderName → ReceiverName: message text"`.

#### Scenario: Social filter active

- GIVEN the EventLog panel with mixed event types including `"dialogue"`
- WHEN the user selects the "Social" filter
- THEN only `type === "dialogue"` events are shown

#### Scenario: Dialogue event formatting

- GIVEN a dialogue event with sender "Zog", target "Mila", text "Hello!"
- WHEN displayed in the EventLog
- THEN the line reads "Zog → Mila: Hello!"
