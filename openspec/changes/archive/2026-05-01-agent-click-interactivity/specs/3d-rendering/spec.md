# Delta for 3d-rendering

## MODIFIED Requirements

### Requirement: 3D-R5 — Agent Click via Interactivity Plugin

The system MUST use `oncreate` on `<T.Mesh>` to call `useInteractivity().addInteractiveObject(ref)` and attach a native `onclick` handler that calls `uiStore.selectAgent(agentId)`. The selected agent MUST display a gold highlight ring and open the AgentInspector.
(Previously: Clicking used the `onclick` prop on `<T.Mesh>`, which failed in Svelte 5 runes mode because Threlte does not forward `onclick` to `$props()`.)

#### Scenario: Agent click selects via oncreate

- GIVEN a `<T.Mesh>` with `userData={{ agentId }}` and `oncreate` callback
- WHEN the callback fires with `{ ref }`
- THEN the ref is registered via `addInteractiveObject(ref)`
- AND `ref.onclick` is set to call `uiStore.selectAgent(agentId)`

#### Scenario: Highlight ring on selection

- GIVEN an interactive agent mesh
- WHEN the user clicks the agent sphere
- THEN `uiStore.selectedAgentId` is set and SelectionHighlight shows the gold ring at the agent's position

#### Scenario: Inspector opens on selection

- GIVEN an interactive agent mesh
- WHEN the user clicks the agent sphere
- THEN `uiStore.selectAgent` sets `showInspector: true` and AgentInspector renders with the agent's data

## ADDED Requirements

### Requirement: 3D-R11 — Interactive Object Cleanup

The system MUST deregister interactive objects on component unmount via the cleanup function returned by `useInteractivity().addInteractiveObject()`.

#### Scenario: Unmount removes interactivity

- GIVEN a `<T.Mesh>` registered as interactive via `oncreate`
- WHEN the enclosing component unmounts
- THEN `removeInteractiveObject(ref)` is called
- AND the mesh no longer receives click events
