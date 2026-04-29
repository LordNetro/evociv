# Tasks: 3D Rendering Migration

> Total: **12 tasks** | Fase 1: Setup (2) · Fase 2: Grid (1) · Fase 3: Resources (2) · Fase 4: Agents (4) · Fase 5: Integration (2) · Fase 6: Polish (1)

---

## Fase 1 — Setup

### T1 — Install Threlte 8 + Three.js Dependencies

**Fase**: 1
**Archivos**: `frontend/package.json`
**Depende de**: —
**Estimación**: baja

**Descripción**: Agregar `@threlte/core`, `@threlte/extras`, y `three` al `package.json`. Verificar compatibilidad con Svelte 5.55 y Vite 8. Ejecutar `npm install` y confirmar que la resolución de dependencias es correcta sin advertencias de peer dependency.

**Criterios de aceptación**:
- [ ] `package.json` incluye `@threlte/core`, `@threlte/extras`, `three` en `dependencies`
- [ ] `npm install` completa sin errores ni advertencias
- [ ] `npm run check` pasa sin errores de tipos relacionados a Threlte/Three

---

### T2 — Create Scene.svelte with Canvas, Lights, and OrbitControls

**Fase**: 1
**Archivos**: `frontend/src/lib/canvas3d/Scene.svelte`
**Depende de**: T1
**Estimación**: media

**Descripción**: Crear el componente raíz de la escena 3D. Debe montar `<T.Canvas>` de Threlte con:
- `<T.PerspectiveCamera>` con posición inicial `makeDefault` (ángulo superior mirando al centro del grid)
- `<AmbientLight>` intensidad ~0.5 para iluminación base
- `<DirectionalLight>` intensidad ~0.8, posición `(50, 100, 50)` para sombras suaves
- `<OrbitControls>` con soporte para pan, rotate y zoom (límites de zoom: min 5, max 200)

El componente acepta `$props()` con `gridWidth`, `gridHeight`, `tileSize` (defaults: `{ gridWidth: 50, gridHeight: 50, tileSize: 32 }`).

La cámara debe inicializarse centrada sobre el grid: posición `(gridWidth * tileSize / 2, 100, gridHeight * tileSize / 2 + 80)` mirando hacia `(gridWidth * tileSize / 2, 0, gridHeight * tileSize / 2)`.

El `<T.Canvas>` debe ocupar el 100% del contenedor padre. Usar `let { config } = $props()` para recibir la configuración desde `SimCanvas.svelte`.

**Criterios de aceptación**:
- [ ] `<T.Canvas>` se monta sin errores y ocupa el contenedor padre
- [ ] `AmbientLight` + `DirectionalLight` iluminan la escena
- [ ] `OrbitControls` permite pan, rotate y zoom con límites de zoom
- [ ] `PerspectiveCamera` se posiciona en el centro superior del grid
- [ ] Acepta `config` via `$props()` con defaults
- [ ] `npm run check` pasa sin errores

---

## Fase 2 — Grid

### T3 — Create Grid3D.svelte with InstancedMesh Tiles

**Fase**: 2
**Archivos**: `frontend/src/lib/canvas3d/Grid3D.svelte`
**Depende de**: T2
**Estimación**: alta

**Descripción**: Crear el componente de grid usando `THREE.InstancedMesh` para renderizar todos los tiles del grid (50×50 = 2500 tiles) en una sola draw call.

- Usar `PlaneGeometry(tileSize, tileSize)` rotada 90° en X para quedar horizontal
- `InstancedMesh` con `count = gridWidth * gridHeight`
- Por cada tile `(tx, ty)`:
  - Posición: `(tx * tileSize + tileSize/2, 0, ty * tileSize + tileSize/2)` — centro del tile
  - Color: según `resource_type` — `#3d2b1f` si tiene recurso, `#2d1b0e` si está vacío
- Leer tiles de `$simulationStore` via `$derived($simulationStore.tiles)` (auto-subscribe)
- Actualizar colores reactivamente cuando cambien los tiles (escribir al instanceColor buffer)
- Construir key del tile como `"${tx},${ty}"` para búsqueda O(1)

**Criterios de aceptación**:
- [ ] 2500 tiles renderizados en una sola `InstancedMesh` draw call
- [ ] Tiles con recurso muestran color `#3d2b1f`, vacíos `#2d1b0e`
- [ ] Tile en `(5,5)` se posiciona en `(5 * tileSize + tileSize/2, 0, 5 * tileSize + tileSize/2)`
- [ ] Reactivo: cuando `simulationStore` cambia, los colores se actualizan
- [ ] Sin errores de Three.js en consola
- [ ] Frustum culling activo (default de Three.js)

---

## Fase 3 — Resources

### T4 — Create Resources3D.svelte with Primitives

**Fase**: 3
**Archivos**: `frontend/src/lib/canvas3d/Resources3D.svelte`
**Depende de**: T3
**Estimación**: media

**Descripción**: Crear componente que renderiza primitivas 3D sobre tiles con recursos. Solo instanciar geometrías para tiles que tengan `resource_type !== null` para minimizar draw calls.

Mapeo de recursos:
| resource_type | Geometría | Color | Altura (y) |
|---|---|---|---|
| `tree` | `ConeGeometry(8, 16, 8)` | `#2e7d32` verde | 0 (base del cono sobre tile) |
| `berries` | `SphereGeometry(4, 12, 12)` | `#c62828` rojo | 4 (centro de esfera) |
| `stone` | `BoxGeometry(6, 6, 6)` | `#757575` gris | 3 (centro de cubo) |

- Cada primitiva centrada en `(tx * tileSize + tileSize/2, y, ty * tileSize + tileSize/2)`
- Usar `MeshStandardMaterial` con `roughness: 0.7` para aspecto natural
- Leer `$derived($simulationStore.tiles)` y filtrar solo tiles con recurso
- Crear un grupo por tile con recurso o usar meshes individuales (máximo ~500 instancias para grid de 50×50, aceptable sin instancing)

**Criterios de aceptación**:
- [ ] `tree` → cono verde `#2e7d32` centrado en el tile
- [ ] `berries` → esfera roja `#c62828` centrada en el tile
- [ ] `stone` → cubo gris `#757575` centrado en el tile
- [ ] Solo se crean geometrías para tiles con `resource_type !== null`
- [ ] Reactivo: nueva tile con recurso aparece al actualizar el store

---

### T5 — Create WaterPlane.svelte

**Fase**: 3
**Archivos**: `frontend/src/lib/canvas3d/WaterPlane.svelte`
**Depende de**: T3
**Estimación**: baja

**Descripción**: Crear componente para tiles de agua. Los tiles con `resource_type === "water"` se renderizan como planos semi-transparentes en vez de las primitivas de Resources3D.

- `PlaneGeometry(tileSize, tileSize)` rotada horizontal
- `MeshStandardMaterial` con `color: #1565c0`, `opacity: 0.6`, `transparent: true`
- Posición: `(tx * tileSize + tileSize/2, 0.01, ty * tileSize + tileSize/2)` — ligeramente elevado para evitar z-fighting con el tile base
- Leer `$derived($simulationStore.tiles)` y filtrar solo `water` tiles
- **Futuro**: (out of scope para MVP) animación de onda vía `onBeforeCompile` o shader personalizado

**Criterios de aceptación**:
- [ ] Tile `water` renderizado como plano azul semi-transparente `rgba(21,101,192,0.6)`
- [ ] Sin z-fighting con el tile base (elevado 0.01)
- [ ] Reactivo: cambio de resource_type a water actualiza el render
- [ ] Los demás resource_types (tree, berries, stone) NO son afectados

---

## Fase 4 — Agents

### T6 — Create canvas3dStore.svelte.js for Agent Interpolation

**Fase**: 4
**Archivos**: `frontend/src/lib/canvas3d/canvas3dStore.svelte.js`
**Depende de**: T2
**Estimación**: media

**Descripción**: Crear store de interpolación para movimiento suave de agentes. Como los ticks del servidor llegan discretamente (~cada 200ms), necesitamos interpolar posiciones entre ticks para movimiento fluido.

- Store basado en `writable` con un Map `agentPositions: Map<string, { currentX, currentY, targetX, targetY }>`
- Método `updateTargets(agents)`: recibe snapshot del servidor, actualiza targets
- Bucle interno con `requestAnimationFrame` que lerp `current → target` con factor `speed * dt`
- Exponer `$derived` de posiciones interpoladas para que Agents3D las consuma
- Limpiar agentes muertos del Map
- Velocidad de interpolación: ~200ms (completar ~90% del trayecto en 200ms)
- Re-exportar funciones `lerp`, `clamp` desde este store (migrar desde `canvas/animation.ts`)

**Criterios de aceptación**:
- [ ] `updateTargets(agents)` actualiza targets desde snapshot
- [ ] Agente se mueve suavemente entre posiciones (lerp sobre ~200ms)
- [ ] Agentes muertos se eliminan del Map de interpolación
- [ ] Store expone `$derived` para consumo reactivo

---

### T7 — Create Agents3D.svelte with Role-Colored Spheres

**Fase**: 4
**Archivos**: `frontend/src/lib/canvas3d/Agents3D.svelte`
**Depende de**: T6, T3
**Estimación**: alta

**Descripción**: Crear componente que renderiza agentes como esferas 3D.

- `SphereGeometry(radius=0.4 * tileSize / 2, 16, 16)` — escalado por tileSize
- Color por rol: `gatherer: #4CAF50`, `builder: #FF9800`, `scout: #2196F3`, `warrior: #F44336`, default `#999999`
- Posición: `(agentX * tileSize + tileSize/2, 0.5, agentY * tileSize + tileSize/2)` — elevado y=0.5
- Agentes child: escala `0.6` (usar `scale` de `Object3D` o radio reducido)
- Faction ring: si `faction_id` presente, dibujar `RingGeometry` o `LineLoop` alrededor del agente con el color de la facción, elevado en y=0.5
- Usar posiciones interpoladas desde `canvas3dStore` en vez de posiciones crudas del snapshot
- Leer agentes de `$derived($simulationStore.agents)` y facciones de `$derived($simulationStore.factions)`

**Criterios de aceptación**:
- [ ] Agente `gatherer` → esfera `#4CAF50`
- [ ] Agente `builder` → esfera `#FF9800`
- [ ] Agente `scout` → esfera `#2196F3`
- [ ] Agente `warrior` → esfera `#F44336`
- [ ] Agente child → 60% del tamaño adulto
- [ ] Agente con facción → anillo del color de la facción
- [ ] Posición interpolada: el agente se mueve suavemente entre ticks
- [ ] Posición Y = 0.5 sobre el tile

---

### T8 — Create AgentLabel.svelte with HTML Sprites

**Fase**: 4
**Archivos**: `frontend/src/lib/canvas3d/AgentLabel.svelte`
**Depende de**: T7
**Estimación**: baja

**Descripción**: Crear etiquetas HTML sobre cada agente mostrando la inicial del nombre. Usar `<T.Html>` de `@threlte/extras` para renderizar HTML que sigue la posición 3D del agente.

- `<T.Html>` posicionado en `(agentX, agentY + 0.8, agentZ)` — sobre el agente
- Mostrar `agent.name.charAt(0)` con estilo: `color: white`, `font-weight: bold`, `font-size: 12px`, `text-shadow` para legibilidad
- `pointer-events: none` para no interferir con raycasting
- Fondo semi-transparente `rgba(0,0,0,0.4)` con `padding: 2px 6px`, `border-radius: 4px`
- `transform: translateY(-100%)` para alinear sobre la cabeza del agente

**Criterios de aceptación**:
- [ ] Etiqueta HTML visible sobre cada agente
- [ ] Muestra la inicial del nombre del agente
- [ ] Sigue la posición 3D del agente (incluyendo interpolación)
- [ ] `pointer-events: none` — no bloquea clicks en el agente
- [ ] Estilo legible sobre cualquier color de fondo

---

### T9 — Create SelectionHighlight.svelte with Ring Geometry

**Fase**: 4
**Archivos**: `frontend/src/lib/canvas3d/SelectionHighlight.svelte`
**Depende de**: T7
**Estimación**: baja

**Descripción**: Crear anillo de selección amarillo que aparece alrededor del agente seleccionado.

- `RingGeometry(inner=0.45, outer=0.55) * tileSize` con `LineLoop` o `MeshBasicMaterial`
- Color: amarillo `#FFD700`
- Posición: se actualiza según la posición interpolada del agente seleccionado
- Leer `$uiStore.selectedAgentId` de `uiStore.svelte.js`
- Mostrar solo cuando `selectedAgentId !== null`
- Rotar para quedar horizontal (paralelo al tile)

**Criterios de aceptación**:
- [ ] Anillo amarillo `#FFD700` visible alrededor del agente seleccionado
- [ ] Sigue al agente cuando se mueve
- [ ] Desaparece cuando `selectedAgentId` es `null`
- [ ] No interfiere con raycasting de otros agentes

---

## Fase 5 — Integration

### T10 — Rewrite SimCanvas.svelte to Mount Threlte Canvas

**Fase**: 5
**Archivos**: `frontend/src/lib/components/SimCanvas.svelte`
**Depende de**: T2, T3, T4, T5, T7, T8, T9
**Estimación**: alta

**Descripción**: Reescribir `SimCanvas.svelte` para que monte el componente `Scene.svelte` en vez de instanciar la clase `Engine`.

- Importar `Scene` de `$lib/canvas3d/Scene.svelte`
- Pasar `config` via props: `<Scene config={config} />`
- **Dynamic import** (code splitting) de Threlte: `const { default: Scene } = await import('$lib/canvas3d/Scene.svelte')` dentro de `$effect` para mantener el bundle inicial pequeño
- Configurar raycaster para clicks en agentes:
  - Threlte `<Canvas>` expone eventos pointer: usar `onclick` o eventos de Three.js
  - Al hacer click en un agente, llamar `uiStore.selectAgent(agentId)`
- Eliminar toda la lógica del Engine class, resize listeners, setup de input, game loop
- El `<canvas>` ahora es gestionado internamente por Threlte — eliminar el `<canvas>` manual
- El estilo `cursor: grab/grabbing` ahora lo maneja `OrbitControls`

**Criterios de aceptación**:
- [ ] `SimCanvas.svelte` monta `<Scene config={config} />` en vez del Engine class
- [ ] No importa ningún archivo de `$lib/canvas/`
- [ ] Dynamic import de Threlte funciona (code splitting)
- [ ] Click en agente dispara `uiStore.selectAgent(agentId)` vía raycaster
- [ ] Resize del navegador funciona sin errores (Threlte lo maneja automáticamente)
- [ ] Overlays (HUD, AgentInspector, etc.) se renderizan correctamente sobre el canvas 3D
- [ ] `npm run check` y `npm run build` pasan sin errores

---

### T11 — Remove Legacy Canvas 2D Files

**Fase**: 5
**Archivos**: `frontend/src/lib/canvas/engine.ts`, `grid.ts`, `entities.ts`, `camera.ts`, `animation.ts`
**Depende de**: T10
**Estimación**: baja

**Descripción**: Eliminar los 5 archivos del canvas 2D legacy. Verificar que ningún import en el proyecto referencia estos archivos.

- Eliminar físicamente los 5 archivos
- Si el directorio `canvas/` queda vacío, eliminarlo también
- Buscar con grep en todo el proyecto por imports a `$lib/canvas/` o `./canvas/` para confirmar que no hay referencias residuales
- Verificar que `SimCanvas.svelte` ya no importa de `$lib/canvas/engine`
- Si existe `animation.ts` con utilidades (lerp, clamp), migrarlas a `canvas3dStore` antes de eliminar

**Criterios de aceptación**:
- [ ] `frontend/src/lib/canvas/engine.ts` eliminado
- [ ] `frontend/src/lib/canvas/grid.ts` eliminado
- [ ] `frontend/src/lib/canvas/entities.ts` eliminado
- [ ] `frontend/src/lib/canvas/camera.ts` eliminado
- [ ] `frontend/src/lib/canvas/animation.ts` eliminado (funciones migradas a canvas3dStore)
- [ ] Cero imports rotos a `$lib/canvas/` en todo el proyecto
- [ ] `npm run build` pasa sin errores

---

## Fase 6 — Polish

### T12 — Animations, Performance Tuning, and Tests

**Fase**: 6
**Archivos**: `frontend/src/lib/canvas3d/canvas3dStore.svelte.js`, nuevos tests
**Depende de**: T11
**Estimación**: media

**Descripción**: Pulir la implementación final: asegurar animaciones suaves, rendimiento aceptable y cobertura de tests base.

**Animaciones**:
- Verificar interpolación de agentes: ~200ms de duración con easing (ease-in-out)
- Opcional: fade-in inicial cuando un agente aparece por primera vez (opacity transition)

**Rendimiento**:
- Verificar con grid 50×50 + 20 agentes en GPU integrada
- Monitorear `renderer.info.render.calls` — debe ser bajo (instanced mesh = 1 call para tiles)
- Verificar que no hay fugas de memoria: agentes que mueren deben liberar geometrías
- Sin sombras, sin post-processing (confirmar)
- Frustum culling activo

**Tests** (Vitest + jsdom):
- Test de componente: `Scene.svelte` monta sin errores (sin WebGL, mockear `HTMLCanvasElement.getContext`)
- Test de integración: click simulado en agente → `uiStore.selectedAgentId` se actualiza
- Test de store: `canvas3dStore.updateTargets()` → posiciones se interpolan correctamente
- Test de snapshot: verificar que `Grid3D` produce instancias con colores correctos

**Documentación**:
- Asegurar que `proposal.md` success criteria están todos marcados como completos

**Criterios de aceptación**:
- [ ] Interpolación de agentes fluida (~200ms ease-in-out)
- [ ] 50×50 grid + 20 agentes a ≥30fps (target 60fps) en GPU integrada
- [ ] Sin fugas de memoria: agentes muertos no acumulan geometrías
- [ ] Tests de componente: Scene monta sin errores
- [ ] Test de integración: click → uiStore.selectAgent
- [ ] Test de store: interpolación funciona correctamente
- [ ] `npm run check` pasa sin errores
- [ ] `npm run build` pasa sin errores
