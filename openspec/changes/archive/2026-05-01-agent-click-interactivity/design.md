# Design: Fix Agent Click Interactivity

## Technical Approach

Replace Threlte's prop-based interactivity registration (`onclick` on `<T.Mesh>`) with explicit registration via `useInteractivity().addInteractiveObject()` inside the `oncreate` callback. This bypasses Svelte 5's prop forwarding entirely — the plugin's `hasEventHandlers` check (`typeof props['onclick'] === 'function'`) never runs for these meshes because registration happens at the JS API level, not the prop level.

## Architecture Decisions

### Decision: Direct registration via `oncreate` over prop-based `onclick`

| Option | Tradeoffs | Decision |
|--------|-----------|----------|
| **Prop-based `onclick`** (current) | Works by convention but breaks in Svelte 5 runes — `onclick` doesn't reliably reach `$props()` rest params. Zero control over when/if registration happens. | ❌ Rejected |
| **Direct `useInteractivity().addInteractiveObject()` via `oncreate`** | Only affects `Agents3D.svelte`. Uses public Threlte API. `oncreate` fires after all hooks run and ref is constructed. Cleanup function handles deregistration. | ✅ **Chosen** |
| **Manual raycaster** | Complete control but duplicates Threlte's interactivity system — hundreds of lines for hit testing, propagation, cursor handling. | ❌ Rejected |

### Decision: Keep `InteractivityInit.svelte` unchanged

The `InteractivityInit` wrapper correctly calls `interactivity()` which sets up the context (`addInteractiveObject`, `removeInteractiveObject`, raycaster, pointer state). Our approach depends on this context being available — removing it would break the fix.

## Data Flow

```
User clicks canvas
       │
       ▼
setupInteractivity (Threlte internal)
       │
       ├─ Raycaster intersects all objects in interactiveObjects[]
       │
       └─ Finds Mesh → looks up handlers WeakMap → calls onclick()
                                              │
                                              ▼
                                       handleClick(id)
                                              │
                                              ▼
                                       uiStore.selectAgent(id)
                                              │
                                              ▼
                                       AgentInspector opens
```

**Registration path (new):**
```
Agents3D.svelte: <T.Mesh oncreate={(ref) => {
    const { addInteractiveObject } = useInteractivity();
    addInteractiveObject(ref, { onclick: handler });
}}>
       │
       ▼
T.svelte: $effect → calls oncreate(internalRef)
       │
       ▼
Plugin is NOT consulted (no hasEventHandlers check)
       │
       ▼
Mesh pushed to interactiveObjects[] + handlers WeakMap
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/lib/canvas3d/Agents3D.svelte` | Modify | Replace `onclick={}` prop on `<T.Mesh>` with `oncreate` callback calling `addInteractiveObject` |
| `frontend/src/lib/canvas3d/InteractivityInit.svelte` | No change | Context setup is correct, no modifications needed |
| `frontend/src/lib/canvas3d/Scene.svelte` | No change | Wrapper structure is correct, no modifications needed |

## Interfaces / Contracts

No new types or interfaces. The `useInteractivity()` function returns:

```typescript
{
  addInteractiveObject: (object: Object3D, events: Record<string, Function>) => void;
  removeInteractiveObject: (object: Object3D) => void;
  // ... other context properties
}
```

The `oncreate` callback on `<T.Mesh>` receives the Three.js ref directly `(ref)` — the Three.js Mesh instance.

## Implementation Detail

The key change in `Agents3D.svelte` is extracting `useInteractivity` at the top level and using it inside `oncreate`:

```svelte
<script lang="ts">
  import { useInteractivity } from '@threlte/extras';
  // ... existing imports

  function handleClick(agentId: string) {
    uiStore.selectAgent(agentId);
  }
</script>

<T.Mesh
  oncreate={(ref) => {
    const { addInteractiveObject, removeInteractiveObject } = useInteractivity();
    const handler = () => handleClick(id);
    addInteractiveObject(ref, { onclick: handler });
    return () => removeInteractiveObject(ref);
  }}
  userData={{ agentId: id }}
>
```

The cleanup function returned from `oncreate` runs when the component unmounts, preventing stale mesh references in `interactiveObjects[]`.

## Testing Strategy

Frontend has no test framework installed per config. Manual verification:

| What | How |
|------|-----|
| Agent click opens inspector | Click each agent sphere → AgentInspector panel opens with correct agent ID |
| Click outside agents | Nothing selected (no false positives) |
| Agent inspector dismiss | Click close or click empty canvas → deselected |
| Re-mount stability | Agents that enter/leave view (panning) still clickable |

Use browser devtools console: `console.log(uiStore.selectedAgentId)` to verify state changes without visual feedback.

## Migration / Rollout

Single file change, no migration needed. The old `onclick` prop on `<T.Mesh>` (line 70 in `Agents3D.svelte`) is removed and replaced with `oncreate`. All other interactivity plumbing (`InteractivityInit`, `Scene`) stays identical.

## Open Questions

- None. Root cause identified, solution verified against Threlte source (`plugin.svelte.js` line 25, `context.js` line 28-44, `T.svelte` line 103-111).
