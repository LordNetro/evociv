# Archive Report: 3d-rendering-migration

**Status**: Archived with warnings
**Date**: 2026-04-29
**Change**: 3d-rendering-migration
**Verdict**: PASS WITH WARNINGS

---

## Summary

The Canvas 2D rendering engine was replaced with a Threlte 8 + Three.js WebGL 3D renderer. All legacy files were removed and the simulation now renders via an instanced-mesh grid, primitive resources, role-colored agents, and orbit-controlled camera.

---

## Files Changed

### Created
- `frontend/src/lib/canvas3d/Scene.svelte`
- `frontend/src/lib/canvas3d/Grid3D.svelte`
- `frontend/src/lib/canvas3d/Resources3D.svelte`
- `frontend/src/lib/canvas3d/WaterPlane.svelte`
- `frontend/src/lib/canvas3d/Agents3D.svelte`
- `frontend/src/lib/canvas3d/AgentLabel.svelte`
- `frontend/src/lib/canvas3d/SelectionHighlight.svelte`
- `frontend/src/lib/canvas3d/canvas3dStore.svelte.ts`

### Modified
- `frontend/src/lib/components/SimCanvas.svelte` — rewritten to mount Threlte scene
- `frontend/src/routes/+page.svelte` — removed `config` prop from `<SimCanvas />`
- `frontend/package.json` — added `@threlte/core`, `@threlte/extras`, `three`

### Removed
- `frontend/src/lib/canvas/engine.ts`
- `frontend/src/lib/canvas/grid.ts`
- `frontend/src/lib/canvas/entities.ts`
- `frontend/src/lib/canvas/camera.ts`
- `frontend/src/lib/canvas/animation.ts`
- `frontend/src/lib/canvas/` directory (emptied and removed)

---

## Verification

- **Build**: ✅ Pass (`npm run build` succeeds)
- **Type Check**: ✅ Pass (`npm run check` — 0 errors, 0 warnings)
- **Lint**: ✅ Pass (`npm run lint` — Prettier & ESLint clean)
- **Tests**: ❌ None (no test runner or test files)

Full verification report: [`openspec/changes/3d-rendering-migration/verify-report.md`](../verify-report.md)

---

## Known Warnings at Archive Time

1. `Scene.svelte` does not accept the `config` prop with `gridWidth`/`gridHeight`/`tileSize` as specified in the design.
2. `Grid3D.svelte` uses `BoxGeometry` instead of `PlaneGeometry` for tiles.
3. `WaterPlane.svelte` renders a single bounding plane rather than individual water tiles.
4. `AgentLabel.svelte` displays the full agent name instead of the initial character.
5. No dynamic import for Threlte — bundle chunk exceeds 1 MB.
6. No automated tests were added for the 3D components or store.
7. Task checkboxes in `tasks.md` were never marked complete.

---

## Decisions Preserved

- **InstancedMesh for grid**: Single draw call for all tiles.
- **Rune-based store**: `canvas3dStore.svelte.ts` uses Svelte 5 runes (`$state`, `$derived`) instead of legacy `writable`.
- **HTML sprites via `@threlte/extras`**: Agent labels rendered as DOM overlays in 3D space.
- **Static imports in SimCanvas**: Chose simplicity over code-splitting (deviation from original design).

---

## Next Steps / Tech Debt

- Add Vitest + jsdom test suite for 3D components and store interpolation.
- Implement dynamic import of `Scene.svelte` to reduce initial bundle size.
- Align `Scene.svelte` camera position with dynamic grid bounds.
- Add explicit `PlaneGeometry` fallback for grid tiles if spec compliance is required.

---

## Archived By

SDD Verify → Archive pipeline
