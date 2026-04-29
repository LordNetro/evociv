# Tasks: social-update

> 5 features, 3 fases, 12 tareas. Orden de implementación estricto por dependencias.

---

## Resumen

| Fase | Features | Tareas | Depende de | Estimación total |
|------|----------|--------|------------|-----------------|
| F1 — Backend: Pipeline LLM | F1 (`say_to` field), F2 (Snapshot dialogue) | T1–T6 | Ninguna | Alta |
| F2 — Frontend: Burbujas | F3 (Speech), F4 (Thought) | T7–T10 | F1 | Media |
| F3 — Frontend: EventLog Social | F5 (Social filter) | T11–T12 | F1 | Baja |

---

## Fase 1 — Backend: Pipeline LLM (F1 + F2)

### T1 — Añadir `say_to` a `JSON_FORMAT_INSTRUCTION` en prompts.py

**Fase**: 1
**Archivos**: `backend/app/ai/prompts.py`
**Depende de**: Ninguna
**Estimación**: Baja

**Descripción**:
Añadir el campo `say_to` al JSON schema en `JSON_FORMAT_INSTRUCTION` dentro de `prompts.py`. El campo debe ser opcional (nullable) con estructura `{"agent_id": str, "text": str}`. Va junto al campo `think_aloud` existente.

```json
{
  "say_to": {"agent_id": "target_id", "text": "what to say"} | null
}
```

El prompt debe indicar que `say_to` es opcional — el LLM puede omitirlo o poner `null` cuando no se dirige a nadie.

**Criterios de aceptación**:
- [x] `JSON_FORMAT_INSTRUCTION` incluye `"say_to": {"agent_id": "target_id", "text": "what to say"} | null`
- [x] El campo `say_to` aparece documentado como opcional
- [x] `think_aloud` sigue presente sin cambios
- [x] Todos los tests existentes de prompts pasan

---

### T2 — Extraer `say_to` en orchestrator.py (RealLLMOrchestrator + Mock)

**Fase**: 1
**Archivos**: `backend/app/ai/orchestrator.py`, `backend/app/simulation/agent.py`
**Depende de**: T1
**Estimación**: Media

**Descripción**:
1. **RealLLMOrchestrator** (`orchestrator.py`): En `_call_ollama()`, extraer `say_to` del JSON parseado del LLM. Añadirlo al `data` del response:
   ```python
   "say_to": plan.get("say_to", None),
   ```
   Si el LLM devuelve `null` o no incluye el campo, debe quedar como `None`.

2. **MockLLMOrchestrator** (`agent.py`): Añadir `say_to` a la respuesta mock en `call_async()`. Usar un target válido como `"agent_002"` y texto variado para testing:
   ```python
   "say_to": {"agent_id": "agent_002", "text": "Hello Mila!"},
   ```
   Ocasionalmente debe ser `None` (simular que el LLM a veces no habla).

**Criterios de aceptación**:
- [x] `RealLLMOrchestrator._call_ollama()` extrae `say_to` del JSON de respuesta
- [x] Si el JSON no tiene `say_to`, el response tiene `say_to=None`
- [x] `MockLLMOrchestrator.call_async()` incluye `say_to` en datos mock
- [x] Tests: `test_real_orchestrator_extracts_say_to`, `test_mock_includes_say_to`
- [x] Todos los tests existentes de orchestrator pasan

---

### T3 — Añadir `current_dialogue` y `dialogue_type` a Agent + AgentState + Snapshot

**Fase**: 1
**Archivos**: `backend/app/simulation/agent.py`, `backend/app/models/schemas.py`, `backend/app/simulation/snapshot.py`
**Depende de**: Ninguna (son solo campos de datos, no dependen de lógica de engine)
**Estimación**: Baja

**Descripción**:

1. **Agent** (`agent.py`): Añadir al dataclass `Agent`:
   ```python
   current_dialogue: str | None = None
   dialogue_type: str | None = None  # "speech" | "thought" | None
   ```

2. **AgentState** (`schemas.py`): Añadir al modelo Pydantic `AgentState`:
   ```python
   current_dialogue: str | None = None
   dialogue_type: str | None = None
   ```

3. **Snapshot builder** (`snapshot.py`): En `_build_agent_state()`, mapear los nuevos campos del `Agent` al `AgentState`:
   ```python
   current_dialogue=agent.current_dialogue,
   dialogue_type=agent.dialogue_type,
   ```

**Criterios de aceptación**:
- [x] `Agent` tiene `current_dialogue` y `dialogue_type` por defecto `None`
- [x] `AgentState` tiene los mismos campos por defecto `None`
- [x] `_build_agent_state()` mapea ambos campos del Agent al AgentState
- [x] Un agente recién creado tiene ambos campos `None`
- [x] Tests: `test_agent_dialogue_fields_default_to_none`, `test_snapshot_includes_dialogue_fields`
- [x] Todos los tests existentes pasan

---

### T4 — Procesar `say_to` en engine.py — Helper `_process_say_to` + Message enqueue

**Fase**: 1
**Archivos**: `backend/app/simulation/engine.py`
**Depende de**: T2 (orchestrator extrae say_to), T3 (campos existen en Agent)
**Estimación**: Alta

**Descripción**:
Crear el método compartido `_process_say_to(agent, response_data)` en `SimulationEngine` y llamarlo desde **ambos** caminos de respuesta LLM:

1. **`_poll_llm_responses()`** (línea ~1089): después de que un futuro LLM se completa fuera del FSM.
2. **`_fsm_llm_waiting()`** (línea ~1010): después de que un futuro LLM se completa dentro del FSM.

El helper debe:

- Si `response_data` tiene `say_to` con `agent_id` y `text` no vacío:
  - `agent.current_dialogue = say_to["text"]`
  - `agent.dialogue_type = "speech"`
  - Buscar target agent por `agent_id` en `self.agents`
  - Crear un `Message(sender_id=agent.id, content={"type": "dialogue", "text": say_to["text"]}, tick=current_tick)`
  - Encolar en `target.conversation_queue` (usar `ConversationManager._enqueue_message()` o inline si no hay acceso directo — el manager es un helper estático)
  - Loggear a info `"{source.name} → {target.name}: {text}"`

- Si `response_data` tiene `think_aloud` no vacío (y NO hay `say_to`):
  - `agent.current_dialogue = response_data["think_aloud"]`
  - `agent.dialogue_type = "thought"`

- Si no hay `say_to` ni `think_aloud`:
  - `agent.current_dialogue = None`
  - `agent.dialogue_type = None`

Marcar `self.builder.mark_agent_dirty(agent.id)` en todos los casos.

**Criterios de aceptación**:
- [x] `_poll_llm_responses()` llama a `_process_say_to()` después de extraer el plan
- [x] `_fsm_llm_waiting()` llama a `_process_say_to()` después de extraer el plan
- [x] `say_to` con target existente encola `Message` en `target.conversation_queue`
- [x] `say_to` con target inexistente loggea warning pero no crash
- [x] `think_aloud` sin `say_to` setea `current_dialogue` y `dialogue_type="thought"`
- [x] ni `say_to` ni `think_aloud` → limpia ambos campos a `None`
- [x] Tests: `test_process_say_to_creates_message`, `test_process_say_to_think_aloud`, `test_process_say_to_clears_on_none`, `test_process_say_to_called_from_poll`, `test_process_say_to_called_from_fsm`
- [x] Todos los tests existentes de engine pasan

---

### T5 — Generar SimEvent tipo `"dialogue"` en engine.py

**Fase**: 1
**Archivos**: `backend/app/simulation/engine.py`
**Depende de**: T4 (existe `_process_say_to`)
**Estimación**: Baja

**Descripción**:
Dentro del helper `_process_say_to()`, emitir un `SimEvent` con `type="dialogue"` en cada caso:

- Para `say_to`:
  ```python
  SimEvent(
      event_id=f"dialogue_{tick}_{agent.id}_{say_to['agent_id']}",
      type="dialogue",
      severity="info",
      description=f"{agent.name} → {target.name}: {say_to['text']}",
      agent_ids=[agent.id, target.id],
      tick=tick,
      position=agent.position,
  )
  ```
  Pushear al `self.event_queue`.

- Para `think_aloud` (solo cuando se procesa `think_aloud` sin `say_to`):
  ```python
  SimEvent(
      event_id=f"dialogue_{tick}_{agent.id}_thought",
      type="dialogue",
      severity="info",
      description=f"{agent.name} thinks: {think_aloud_text}",
      agent_ids=[agent.id],
      tick=tick,
      position=agent.position,
  )
  ```
  Pushear al `self.event_queue`.

Los eventos se drenarán en el siguiente `self.event_queue.drain()` dentro del tick loop (paso 4/8 en `_tick()`).

**Criterios de aceptación**:
- [x] `say_to` emite SimEvent con `type="dialogue"` y descripción `"{source} → {target}: {text}"`
- [x] `think_aloud` emite SimEvent con `type="dialogue"` y descripción `"{name} thinks: {text}"`
- [x] Evento llega al EventQueue del engine
- [x] No se emite evento si `say_to` y `think_aloud` son ambos `None`
- [x] Tests: `test_dialogue_event_for_say_to`, `test_dialogue_event_for_think_aloud`, `test_no_dialogue_event_when_both_none`
- [x] Todos los tests existentes pasan

---

### T6 — Tests completos del pipeline LLM dialogue

**Fase**: 1
**Archivos**: `backend/tests/test_social.py` (o nuevo `backend/tests/test_dialogue.py`)
**Depende de**: T1, T2, T3, T4, T5
**Estimación**: Alta

**Descripción**:
Escribir tests unitarios y de integración para todo el pipeline dialogue:

**Tests unitarios** (posiblemente en test_social.py):

1. `test_current_dialogue_in_snapshot` — Build snapshot de agente con current_dialogue="Hello" y verificar que AgentState lo incluye.
2. `test_say_to_enqueues_message` — Mock LLM response con say_to; verificar que target.conversation_queue contiene un Message con `content={"type": "dialogue", "text": ...}`.
3. `test_say_to_sets_dialogue_fields` — Verificar que agent.current_dialogue y dialogue_type se setean correctamente.
4. `test_think_aloud_sets_thought_dialogue` — think_aloud sin say_to produce dialogue_type="thought".
5. `test_clear_dialogue_on_empty_response` — Respuesta sin say_to ni think_aloud limpia current_dialogue a None.
6. `test_dialogue_sim_event_emitted` — Verificar que el SimEvent type="dialogue" se emite para ambos casos.
7. `test_say_to_invalid_target` — say_to con agent_id que no existe → warning log, no crash.

**Tests de integración**:

8. `test_full_tick_cycle_with_dialogue` — Usar MockLLMOrchestrator para simular un tick completo con say_to, luego verificar snapshot y event_queue.
9. `test_poll_llm_responses_triggers_dialogue` — Llamar _poll_llm_responses con mock, verificar dialogue en target.
10. `test_fsm_llm_waiting_triggers_dialogue` — Simular futuro completado en FSM, verificar dialogue.

**Criterios de aceptación**:
- [x] Todos los tests unitarios del pipeline dialogue pasan
- [x] Todos los tests de integración tick-cycle pasan
- [x] Cobertura: say_to, think_aloud, ambos None, target inválido
- [x] Ningún test existente se rompe
- [x] `make test` o `pytest backend/tests/` pasa limpio

---

## Fase 2 — Frontend: Burbujas (F3 + F4)

### T7 — Modificar canvas3dStore para trackear diálogos activos con timers

**Fase**: 2
**Archivos**: `frontend/src/lib/canvas3d/canvas3dStore.svelte.ts`
**Depende de**: T3 (snapshot incluye campos dialogue)
**Estimación**: Media

**Descripción**:
Añadir gestión de burbujas de diálogo en `canvas3dStore`:

```typescript
type DialogueBubble = {
  text: string;
  type: 'speech' | 'thought';
  visibleUntil: number;  // Date.now() + duration_ms
};
```

1. **Nuevo estado reactivo**:
   ```typescript
   dialogueBubbles = $state<Record<string, DialogueBubble | null>>({});
   ```

2. **En `updateTargets(snapshot)`**: Después de actualizar `targetPositions`:
   - Iterar `snapshot.agents`
   - Si `agent.current_dialogue` es truthy:
     - `duration = agent.dialogue_type === 'thought' ? 5000 : 3000`
     - Setear `dialogueBubbles[id] = { text, type, visibleUntil: Date.now() + duration }`
   - Si `agent.current_dialogue` es null/empty:
     - Limpiar `dialogueBubbles[id] = null` (se borra en este snapshot)

3. **En `tick(delta)`**: Después de interpolar posiciones, expirar burbujas cuyo timer haya pasado:
   ```typescript
   const now = Date.now();
   for (const [id, bubble] of Object.entries(this.dialogueBubbles)) {
     if (bubble && now > bubble.visibleUntil) {
       this.dialogueBubbles[id] = null;
     }
   }
   ```

**Criterios de aceptación**:
- [x] `dialogueBubbles` es reactivo (`$state`)
- [x] `updateTargets()` lee `current_dialogue` y `dialogue_type` del snapshot
- [x] Speech: `visibleUntil = Date.now() + 3000ms`
- [x] Thought: `visibleUntil = Date.now() + 5000ms`
- [x] Snapshot sin `current_dialogue` → burbuja se limpia inmediatamente
- [x] `tick()` expira burbujas cuyo timer ha pasado
- [x] Los tests existentes del store siguen funcionando (o verificación visual)

---

### T8 — Modificar AgentLabel.svelte para mostrar speech bubble

**Fase**: 2
**Archivos**: `frontend/src/lib/canvas3d/AgentLabel.svelte`
**Depende de**: T7 (store provee datos de burbuja)
**Estimación**: Media

**Descripción**:
Añadir renderizado de speech bubble (bocadillo de cómic) en `AgentLabel.svelte` cuando el agente tiene un diálogo activo de tipo `speech`.

1. Leer `dialogueBubbles` del store:
   ```typescript
   let bubble = $derived(canvas3dStore.dialogueBubbles[agent.id ?? '']);
   ```

2. Renderizar condicionalmente encima del label existente:
   ```svelte
   {#if bubble && bubble.type === 'speech'}
     <div class="speech-bubble">
       <span class="bubble-text">{bubble.text}</span>
       <div class="bubble-tail"></div>
     </div>
   {/if}
   ```

3. CSS para estilo comic/speech bubble:
   - Fondo blanco o amarillo claro
   - Borde sólido negro/oscuro 2px
   - Border-radius: 12px
   - Padding: 6px 10px
   - Tail/pointer hacia abajo (pseudo-elemento CSS)
   - Font-size: 11px, max-width: 180px
   - Text-wrap: balance, overflow hidden
   - Posicionado sobre el label existente con transform translate

**Criterios de aceptación**:
- [x] Speech bubble aparece cuando `dialogueBubbles[id]` tiene `type='speech'`
- [x] No se renderiza cuando `dialogueBubbles[id]` es null
- [x] Tiene estilo de bocadillo de cómic (fondo claro, borde, tail)
- [x] El texto se muestra truncado si es muy largo (max-width + ellipsis)
- [x] No interfiere con el label existente (name + emoji)
- [x] Verificación visual manual

---

### T9 — Añadir thought bubble (nube) con estilo diferenciado

**Fase**: 2
**Archivos**: `frontend/src/lib/canvas3d/AgentLabel.svelte`
**Depende de**: T7 (store provee datos), T8 (infraestructura de burbuja)
**Estimación**: Media

**Descripción**:
Añadir thought bubble (nube de pensamiento) para cuando el diálogo es de tipo `thought`.

1. En el mismo slot de AgentLabel, renderizar condicionalmente:
   ```svelte
   {#if bubble && bubble.type === 'thought'}
     <div class="thought-bubble">
       <span class="bubble-text">{bubble.text}</span>
       <div class="thought-tail"></div>
     </div>
   {/if}
   ```

2. CSS para estilo nube/pensamiento:
   - Fondo blanco azulado claro o gris claro
   - Borde punteado/dashed 2px (diferenciador visual del speech)
   - Border-radius: 16px (más redondeado que speech)
   - Padding: 6px 10px
   - Tail con puntitos (circulitos decrecientes en vez de triángulo)
   - Font-style: italic (opcional, para denotar pensamiento)
   - Mismo max-width y font-size que speech

**Criterios de aceptación**:
- [x] Thought bubble aparece cuando `dialogueBubbles[id]` tiene `type='thought'`
- [x] Estilo visualmente distinto del speech bubble (borde dashed, tail de puntitos)
- [x] No se renderiza speech y thought simultáneamente
- [x] No interfiere con speech bubble ni con label base
- [x] Verificación visual manual

---

### T10 — Animaciones fade-in / fade-out en burbujas

**Fase**: 2
**Archivos**: `frontend/src/lib/canvas3d/AgentLabel.svelte` (CSS)
**Depende de**: T8, T9 (burbujas existen)
**Estimación**: Baja

**Descripción**:
Añadir animaciones CSS de entrada y salida para ambas burbujas (speech y thought):

1. **Fade-in**: cuando la burbuja aparece (transición de `display: none` a `block`):
   ```css
   @keyframes bubbleIn {
     from { opacity: 0; transform: translateY(8px) scale(0.9); }
     to   { opacity: 1; transform: translateY(0) scale(1); }
   }
   .speech-bubble, .thought-bubble {
     animation: bubbleIn 0.2s ease-out;
   }
   ```

2. **Fade-out**: cuando la burbuja desaparece (antes del remove del DOM):
   - Usar transición CSS nativa si es posible, o animación con `animation-fill-mode: forwards`:
   ```css
   .bubble-exit {
     animation: bubbleOut 0.15s ease-in forwards;
   }
   @keyframes bubbleOut {
     from { opacity: 1; transform: scale(1); }
     to   { opacity: 0; transform: scale(0.9); }
   }
   ```
   - Estrategia: como Svelte 5 maneja el DOM basado en reactividad, podemos usar `transition: opacity 0.15s, transform 0.15s` en lugar de keyframes para simplicidad:
   ```css
   .speech-bubble, .thought-bubble {
     transition: opacity 0.15s ease-in, transform 0.15s ease-in;
   }
   ```

3. Pequeño retardo en thought (opcional): la thought bubble puede tener `animation-delay: 0.1s` para escalonar respecto a speech.

**Criterios de aceptación**:
- [x] Speech bubble aparece con fade-in + slide-up en 200ms
- [x] Thought bubble aparece con misma animación (o ligeramente diferente)
- [x] Ambas burbujas desaparecen con fade-out suave (~150ms)
- [x] Animaciones no son bruscas ni bloquean interacción
- [x] Verificación visual manual

---

## Fase 3 — Frontend: EventLog Social (F5)

### T11 — Añadir filtro "Social" en EventLog

**Fase**: 3
**Archivos**: `frontend/src/lib/components/EventLog.svelte`
**Depende de**: T5 (existen eventos dialogue en el snapshot)
**Estimación**: Baja

**Descripción**:
Extender el filtro del EventLog para incluir una opción "Social" que filtre eventos por `type === "dialogue"`.

1. Actualizar el tipo del filtro:
   ```typescript
   let filter = $state<'all' | 'info' | 'warning' | 'critical' | 'social'>('all');
   ```

2. Añadir opción al `<select>`:
   ```svelte
   <option value="social">Social</option>
   ```

3. Actualizar el `$derived` de events:
   ```typescript
   let events = $derived<EventData[]>(
     filter === 'all'
       ? ($simulationStore.events as EventData[])
       : filter === 'social'
         ? ($simulationStore.events as EventData[]).filter((e) => e.type === 'dialogue')
         : ($simulationStore.events as EventData[]).filter((e) => e.severity === filter)
   );
   ```

**Criterios de aceptación**:
- [x] El `<select>` tiene opción "Social"
- [x] "Social" filtra eventos con `type === "dialogue"`
- [x] Los otros filtros (All, Info, Warning, Critical) siguen funcionando
- [x] No hay eventos rotos cuando se selecciona Social sin datos
- [x] Verificación visual manual

---

### T12 — Formato chat para eventos dialogue en EventLog

**Fase**: 3
**Archivos**: `frontend/src/lib/components/EventLog.svelte`
**Depende de**: T11 (filtro social existe)
**Estimación**: Baja

**Descripción**:
Cuando el filtro "Social" está activo, los eventos dialogue se muestran en formato chat (sin el prefijo `[dialogue]`). Para otros filtros, los eventos dialogue se muestran con su formato normal.

1. Modificar la renderización de cada evento: si `event.type === "dialogue"` Y el filtro es `"social"`, mostrar con estilo chat:
   ```svelte
   {#if filter === 'social' && event.type === 'dialogue'}
     <div class="chat-event">
       <span class="chat-line">{event.description}</span>
     </div>
   {:else}
     <!-- existing format -->
     <span class="type">[{event.type}]</span>
     <span class="desc">{event.description}</span>
   {/if}
   ```

2. CSS para chat:
   ```css
   .chat-event {
     padding: 2px 0;
   }
   .chat-line {
     color: #b0e0ff; /* azul claro — diferenciado */
     font-style: italic;
   }
   ```

3. Opcional: no mostrar `[dialogue]` tag en el filtro social (es obvio), pero mostrarlo en otros filtros.

**Criterios de aceptación**:
- [x] Con filtro "Social": eventos dialogue se ven como líneas de chat (sin tag type, color azulado)
- [x] Con filtro "All": eventos dialogue se ven con formato normal `[dialogue] desc`
- [x] Eventos no-dialogue no se ven afectados por el estilo chat
- [x] Verificación visual manual

---
