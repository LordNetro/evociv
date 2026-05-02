# Tasks: Fix Agent Click Interactivity

## Phase 1: Implementation

- [x] 1.1 Add `import { useInteractivity } from '@threlte/extras'` at the top of `<script>` block in `frontend/src/lib/canvas3d/Agents3D.svelte`
- [x] 1.2 Replace `<T.Mesh onclick={...}>` prop with `oncreate` callback that calls `useInteractivity().addInteractiveObject(ref, { onclick: handler })` and returns cleanup calling `removeInteractiveObject(ref)`

## Phase 2: Verification (manual — no frontend test framework)

- [ ] 2.1 Verify agent click opens AgentInspector with correct agent ID via DevTools `console.log(uiStore.selectedAgentId)`
- [ ] 2.2 Verify clicking empty canvas space does NOT trigger selection (no false positives)
- [ ] 2.3 Verify AgentInspector dismiss/close works after selection
- [ ] 2.4 Verify agents that leave and re-enter viewport (camera pan) remain clickable after re-mount
