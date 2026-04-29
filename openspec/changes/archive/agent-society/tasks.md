# Tasks: agent-society

> 8 features, 5 fases, 28 tareas. Orden de implementación estricto por dependencias.

---

## Resumen

| Fase | Features | Tareas | Depende de | Estimación total |
|------|----------|--------|------------|-----------------|
| F1 — Foundation | F1 (LLM feedback), F8 (Relationships) | T1–T6 | Ninguna | Alta |
| F2 — Social Core | F6 (Conversations) | T7–T10 | F1 | Alta |
| F3 — Society | F2 (Knowledge), F5 (Trading) | T11–T17 | F2 | Alta |
| F4 — Lifecycle & Groups | F3 (Childhood), F4 (Factions) | T18–T23 | F3 | Alta |
| F5 — Colony UI | F7 (Colony panel) + frontend | T24–T28 | F4 | Media |

---

## Fase 1 — Foundation (F1: Action Feedback + F8: Relationships)

### T1 — Añadir `action_type` y `action_summary` a `ActionResult`
**Feature**: F1
**Fase**: 1
**Archivos**: `backend/app/simulation/actions.py`
**Depende de**: Ninguna
**Estimación**: Baja

**Descripción**:
Añadir dos nuevos campos al dataclass `ActionResult` en `actions.py`:
- `action_type: ActionType | None = None`
- `action_summary: str = ""` — string con resumen de deltas, ej. `"hunger:-30, wood:+5, berries:-1"`

Actualizar **todos los handlers existentes** (`handle_move`, `handle_chop`, `handle_drink`, `handle_eat`, `handle_gather`, `handle_rest`, `handle_reproduce`) para que poblén ambos campos. El `action_summary` debe incluir los cambios de estado y de inventario que el handler produce. Ejemplo para `handle_eat`: `action_summary="hunger:-20, berries:-1"`.

Actualizar la constante `ACTION_EMOJIS` no requiere cambio.

**Criterios de aceptación**:
- [x] `ActionResult` tiene campos `action_type` y `action_summary` con valores por defecto `None` / `""`
- [x] `handle_eat()` produce `ActionResult(action_type=ActionType.EAT, action_summary="hunger:-20, berries:-1")`
- [x] `handle_chop()` produce `action_summary` con `wood:+1`
- [x] `handle_move()` produce `action_summary` con cambios de posición si aplica
- [x] `handle_drink()` produce `action_summary` con `thirst:0`
- [x] `handle_gather()` produce `action_summary` con el recurso recolectado
- [x] `handle_rest()` produce `action_summary` con `energy:+10`
- [x] `handle_reproduce()` produce `action_summary` informativo
- [x] Todos los tests existentes de `TestActions` siguen pasando

---

### T2 — Añadir `last_action_result` al `Agent` y propagarlo al prompt LLM
**Feature**: F1
**Fase**: 1
**Archivos**: `backend/app/simulation/agent.py`, `backend/app/simulation/engine.py`, `backend/app/ai/orchestrator.py`, `backend/app/ai/prompts.py`
**Depende de**: T1
**Estimación**: Media

**Descripción**:
1. **Agent** (`agent.py`): Añadir `last_action_result: Optional[ActionResult] = None` al dataclass `Agent`.
2. **Engine** (`engine.py`):
   - En `_fsm_executing()`: después de ejecutar un handler y obtener el `ActionResult`, asignarlo a `agent.last_action_result = result`.
   - En `_fsm_llm_trigger()`: antes de construir el prompt, leer `agent.last_action_result`. Si existe, pasarlo como nuevo parámetro a `build_prompt()`. Después del prompt, resetear `agent.last_action_result = None` (evitar acumulación de contexto stale).
   - En fallback de instinto (LLM timeout en `_fsm_llm_waiting`): si el agente cae a instinto, el `last_action_result` pendiente debe descartarse (no acumularse).
3. **MockLLMOrchestrator** (`agent.py`): Actualizar `build_prompt()` para aceptar y formatear `last_action_result`.
4. **RealLLMOrchestrator** (`orchestrator.py`): Actualizar `build_prompt()` para pasar `last_action_result` al template de prompt.
5. **Prompts** (`prompts.py`): Añadir una nueva sección `LAST ACTION RESULT:` en el prompt template, con el formato:
   ```
   LAST ACTION RESULT:
   - Action: {action_type}
   - Success: {true/false}
   - Effects: {action_summary}
   ```
   Si `last_action_result` es `None`, la sección debe decir `LAST ACTION RESULT: None (first tick)`.

**Criterios de aceptación**:
- [x] Nuevo agente (primer tick) tiene `last_action_result=None` y el prompt muestra "None (first tick)"
- [x] Después de una acción, `ActionResult` queda asignado en `agent.last_action_result`
- [x] `build_prompt()` incluye la sección `LAST ACTION RESULT` con action_type, success y summary
- [x] Después de construir el prompt, `agent.last_action_result` es `None` (consumido)
- [x] En fallback de instinto por timeout, el `last_action_result` se descarta sin acumular
- [x] Tests `test_action_result_captured`, `test_action_result_null_on_first_tick`, `test_action_result_cleared_after_read` pasan

---

### T3 — Añadir `RelationshipData` y campo `relationships` al `Agent`
**Feature**: F8
**Fase**: 1
**Archivos**: `backend/app/simulation/agent.py`, `backend/app/models/schemas.py`, `backend/app/simulation/snapshot.py`
**Depende de**: Ninguna
**Estimación**: Baja

**Descripción**:
1. **Agent** (`agent.py`): Añadir nuevo dataclass `RelationshipData` con campos:
   - `interaction_count: int = 0`
   - `last_interaction_tick: int = 0`
   - `score: float = 0.0` (rango -1.0 a 1.0)

   Añadir campo `relationships: dict[str, RelationshipData] = field(default_factory=dict)` al dataclass `Agent`.

2. **AgentState schema** (`schemas.py`): Añadir campo `relationships: dict[str, dict] = {}` al modelo Pydantic `AgentState`. Convertir `RelationshipData` a dict plano para serialización.

3. **Snapshot builder** (`snapshot.py`): Actualizar `_build_agent_state()` para incluir `agent.relationships` serializado como dict de dicts.

4. **AgentFactory** (`agent.py`): No requiere cambios — `relationships` tiene default factory.

**Criterios de aceptación**:
- [x] `RelationshipData` existe con los 3 campos requeridos
- [x] `Agent.relationships` es un dict vacío por defecto
- [x] `AgentState.relationships` se serializa correctamente en el snapshot
- [x] Snapshot incluye `relationships` para cada agente (aunque vacío)
- [x] Agentes existentes sin relaciones funcionan con valor por defecto (backward compat)

---

### T4 — Implementar tracking de relaciones por interacciones
**Feature**: F8
**Fase**: 1
**Archivos**: `backend/app/simulation/engine.py`, `backend/app/simulation/actions.py`
**Depende de**: T3
**Estimación**: Media

**Descripción**:
1. **Engine** (`engine.py`):
   - Añadir constantes:
     - `INTERACTION_THRESHOLD = 5` (en `REPRODUCE_COOLDOWN` y similares)
     - `DECAY_INTERVAL = 100`
   - Crear método `_update_relationship(agent_a: Agent, agent_b: Agent, tick: int, score_delta: float = 0.1)` que:
     - Incrementa `interaction_count` para ambos
     - Actualiza `last_interaction_tick` para ambos
     - Aplica `score_delta` al `score` de ambos (clamped a [-1.0, 1.0])
   - En `_process_needs()`: añadir lógica de decaimiento de relaciones:
     - Por cada agente, por cada relación: si `tick - last_interaction_tick > DECAY_INTERVAL`, decrementar `interaction_count` en 1 (mínimo 0).
   - En `handle_reproduce` (cuando se completa exitosamente): llamar a `_update_relationship` con `score_delta=0.2`.

2. **Actions** (`actions.py`):
   - `handle_reproduce()`: tras reproducción exitosa (llamada desde engine), actualizar relaciones de ambos padres.

**Criterios de aceptación**:
- [x] `_update_relationship()` actualiza ambos agentes con interaction_count +1
- [x] `score` no excede el rango [-1.0, 1.0]
- [x] Después de `DECAY_INTERVAL` ticks sin interacción, `interaction_count` decrementa
- [x] `interaction_count` nunca es menor que 0
- [x] Tests `test_relationship_data`, `test_relationship_decay` pasan

---

### T5 — Gatear `REPRODUCE` por threshold de interacciones
**Feature**: F8
**Fase**: 1
**Archivos**: `backend/app/simulation/engine.py`
**Depende de**: T4
**Estimación**: Media

**Descripción**:
Modificar `_find_reproduction_partner()` en `engine.py` para que:
1. Solo considere agentes que tengan `agent.relationships[other.id].interaction_count >= INTERACTION_THRESHOLD` (5).
2. Si un agente no tiene entradas en `relationships` para el candidato, se considera 0 interacciones → no apto.
3. Mantener las demás comprobaciones existentes (sexo opuesto, energía > 20, hambre/sed < 80, edad mínima, distancia).
4. Añadir logging warning cuando un agente intenta reproducir pero no hay pareja válida por falta de interacciones.

Modificar `_fsm_evaluate()`: la sección de reproducción (punto 6) debe verificar que exista un partner viable antes de transicionar a `executing` con acción reproduce. Si no hay partner (por threshold), pasar a LLM directamente.

Eliminar la lógica actual que permite reproducción sin restricción de interacciones.

**Criterios de aceptación**:
- [x] `_find_reproduction_partner()` retorna `None` si `interaction_count < INTERACTION_THRESHOLD` para todos los candidatos
- [x] Si `interaction_count >= 5`, el agente es candidato válido (si cumple demás condiciones)
- [x] Agentes con 0 interacciones nunca son considerados para reproducción
- [x] Tests `test_reproduce_gated_by_interactions` pasa
- [x] Se reemplaza la lógica de reproducción incondicional actual

---

### T6 — Tests de Fase 1 (F1 + F8)
**Feature**: F1, F8
**Fase**: 1
**Archivos**: `backend/tests/test_engine.py` (o nuevo `backend/tests/test_social.py`)
**Depende de**: T1, T2, T3, T4, T5
**Estimación**: Baja

**Descripción**:
Implementar todos los tests unitarios para F1 y F8 según el plan de testing del design:

**F1 Tests:**
- `test_action_result_captured` — Crear ActionResult, asignar a agente, verificar que `build_prompt()` lo incluye
- `test_action_result_null_on_first_tick` — Agente nuevo → `last_action_result` es None
- `test_action_result_cleared_after_read` — Después de construir prompt, verificar field es None
- `test_action_result_llm_timeout_discard` — Timeout de LLM → last_action_result se descarta

**F8 Tests:**
- `test_relationship_data` — Interacción entre agentes → relación creada con campos correctos
- `test_reproduce_gated_by_interactions` — interaction_count < threshold → no partner
- `test_relationship_decay` — Después de decay interval, interaction_count decrementa

**Estrategia de mocks:**
- Usar `MockLLMOrchestrator(success_rate=1.0, delay_range=(0.01, 0.05))` para tests deterministas
- Crear agentes directamente con `Agent(...)` para tests unitarios
- Usar engine real para tests de integración con tick loop

---

## Fase 2 — Social Core (F6: Socialización y Conversaciones)

### T7 — Crear `Message` dataclass y `ConversationManager`
**Feature**: F6
**Fase**: 2
**Archivos**: `backend/app/simulation/conversation.py` (NUEVO)
**Depende de**: Fase 1 (T4)
**Estimación**: Media

**Descripción**:
Crear nuevo módulo `backend/app/simulation/conversation.py` con:

1. **`Message` dataclass:**
   ```python
   @dataclass
   class Message:
       sender_id: str
       content: dict  # structured: {"type": "greeting"|"share_knowledge"|"trade_proposal"|...}
       tick: int
   ```

2. **`ConversationManager` class:**
   - `max_pairs_per_tick: int = 5`
   - `max_queue_size: int = 50`
   - `_pending_pairs: list[tuple[str, str]]` — pares de agentes pendientes para procesar
   - `detect_encounters(agents: list[Agent], radius: float, tick: int) -> None`:
     - Reutiliza lógica O(n²) de `check_proximity_encounters()`
     - Para cada par dentro de radio, enqueuea un `Message` de tipo `"greeting"` en ambos agentes
     - Si hay más de `max_pairs_per_tick`, difiere el resto a `_pending_pairs`
     - Cada `Message.content` incluye: `{"type": "greeting", "agent_name": "..."}`
   - `process_next_pair(agent_a, agent_b, world) -> tuple[Message, Message] | None`:
     - Toma el siguiente par pendiente
     - Enqueuea los mensajes de encuentro en cada agente
     - Retorna los mensajes creados o None si no hay pares
   - Método interno `_enqueue_message(agent, message)` que respeta `max_queue_size` (FIFO, si excede, descarta el más antiguo)

Registrar el módulo en `backend/app/simulation/__init__.py`.

**Criterios de aceptación**:
- [x] `Message` dataclass con sender_id, content (dict), tick
- [x] `detect_encounters()` encuentra pares dentro de radio y enqueuea greeting messages
- [x] Se respeta `max_pairs_per_tick=5`; pares excedentes se difieren
- [x] Cada agente tiene max 50 mensajes en cola (FIFO discard)
- [x] Tests `test_conversation_enqueue`, `test_max_queue_size`, `test_max_pairs_per_tick` pasan

---

### T8 — Integrar `conversation_queue` en el Agent y el tick del engine
**Feature**: F6
**Fase**: 2
**Archivos**: `backend/app/simulation/agent.py`, `backend/app/simulation/engine.py`, `backend/app/simulation/conversation.py`
**Depende de**: T7
**Estimación**: Alta

**Descripción**:

1. **Agent** (`agent.py`): Añadir `conversation_queue: list[Message] = field(default_factory=list)` al dataclass `Agent`. Necesita importar `Message` desde `conversation.py` — usar `TYPE_CHECKING` para evitar circular imports.

2. **Engine** (`engine.py`):
   - En `__init__()`: instanciar `self.conversation_manager = ConversationManager()`.
   - Crear nuevo método `async _process_social_interactions(tick: int)`:
     1. Llamar a `self.conversation_manager.detect_encounters(self.agents, INTERACTION_RADIUS, tick)`.
     2. Procesar pares pendientes hasta `max_pairs_per_tick`.
     3. Para cada agente con `conversation_queue` no vacía en estado IDLE, marcar para que el FSM lo procese.
     4. Enqueuear SimEvents de tipo `"socialize"` para cada conversación.
   - Reordenar el tick loop (`_tick()`) a:
     ```
     1. _process_needs(tick)
     2. _run_agent_fsm() para cada agente
     3. _process_social_interactions(tick)       # NUEVO
     4. event_queue.drain()
     5. _poll_llm_responses(tick)
     6. world.regenerate_resources()
     7. check_proximity_encounters() (existente)
     8. check_resource_discoveries() (existente)
     9. Build + broadcast snapshot
     ```
   - En `_process_social_interactions()`: para cada agente cuyo FSM esté en `evaluate` y tenga `conversation_queue` no vacía, incluir los mensajes como contexto adicional.

3. **Faction deaths**: NO mover `_process_faction_agent_death` aún (se hará en F4, fase 4).

4. **SimEvent types**: Añadir `"socialize"` a la lista válida de tipos de eventos.

**Criterios de aceptación**:
- [x] Agent tiene campo `conversation_queue: list[Message]` con default factory
- [x] Engine instancia `ConversationManager`
- [x] `_process_social_interactions()` se llama cada tick y enqueuea mensajes
- [x] Se respeta límite de 5 pares por tick
- [x] Evento `"socialize"` se logea correctamente
- [x] Tests de integración F6 pasan (conversación fluye a través del tick)

---

### T9 — Actualizar prompt LLM con contexto social y procesar acciones sociales
**Feature**: F6
**Fase**: 2
**Archivos**: `backend/app/ai/prompts.py`, `backend/app/ai/orchestrator.py`, `backend/app/simulation/engine.py`
**Depende de**: T8
**Estimación**: Media

**Descripción**:

1. **Prompt template** (`prompts.py`):
   - Añadir nueva sección `SOCIAL CONTEXT:` después de `NEARBY AGENTS`:
   ```
   SOCIAL CONTEXT:
   - Unread messages: {count}
   - Latest: {snippet}
   ```
   - Añadir `"socialize"` y `"trade"` como acciones válidas en `JSON_FORMAT_INSTRUCTION`.
   - Añadir `"feed_child"` como acción válida (prepara para F3).

2. **Orchestrator** (`orchestrator.py`):
   - En `RealLLMOrchestrator.build_prompt()`: leer `agent.conversation_queue` (primeros 3 mensajes como snippet), formatearlos, pasarlos al prompt builder.
   - En `MockLLMOrchestrator.build_prompt()`: mismo cambio (para testing).

3. **Engine FSM** (`engine.py`):
   - En `_fsm_evaluate()`: antes de evaluar necesidades, si el agente tiene `conversation_queue` no vacía y está en `evaluate`, procesar el mensaje más antiguo:
     - Si es `greeting`: continuar a LLM con contexto social (no requiere acción especial).
     - Si es `share_knowledge`: actualizar `agent.knowledge` (prepara para F2).
     - Si es `trade_proposal`: marcar para que el LLM lo evalúe (prepara para F5).
   - Añadir transición: en `evaluate`, si hay mensajes en cola Y no hay necesidad crítica, ir a `llm_trigger` para que el LLM decida cómo responder.

4. **Añadir estado FSM** `"social_interaction"`: (opcional, si se justifica). El design sugiere un estado dedicado, pero por simplicidad podemos procesar en `evaluate`. Decisión del implementador.

**Criterios de aceptación**:
- [x] Prompt incluye sección SOCIAL CONTEXT con count de mensajes no leídos
- [x] JSON format instructions incluyen "socialize", "trade", "feed_child"
- [x] Agent con conversación pendiente recibe contexto social en el prompt
- [x] Messages de tipo greeting se procesan y generan SimEvent
- [x] Tests F6 (LLM procesa mensajes de conversación) pasan

---

### T10 — Tests de Fase 2 (F6)
**Feature**: F6
**Fase**: 2
**Archivos**: `backend/tests/test_social.py` (NUEVO)
**Depende de**: T7, T8, T9
**Estimación**: Baja

**Descripción**:
Implementar todos los tests unitarios y de integración para F6:

**Unit tests:**
- `test_conversation_enqueue` — Dos agentes dentro de radio → messages en ambas colas
- `test_max_queue_size` — 60 mensajes → solo últimos 50 retenidos
- `test_max_pairs_per_tick` — 10 pares pendientes → 5 procesados, 5 diferidos
- `test_socialize_event_logged` — Conversación genera SimEvent type "socialize"

**Integration tests:**
- `test_social_tick_integration` — Engine tick completo con conversaciones entre agentes
- `test_conversation_prompt_context` — Agent con cola no vacía → prompt incluye contexto social

**Mock strategy:**
- Usar `MockLLMOrchestrator` para simular respuestas LLM
- Agentes con posición controlada para garantizar encuentros por proximidad

---

## Fase 3 — Society (F2: Percepción + F5: Trading)

### T11 — Añadir `subtype` y `hidden_properties` a `Tile` y actualizar generación del mundo
**Feature**: F2
**Fase**: 3
**Archivos**: `backend/app/simulation/world.py`, `backend/app/models/schemas.py`, `backend/app/simulation/snapshot.py`
**Depende de**: Ninguna (independiente de Fase 2)
**Estimación**: Media

**Descripción**:

1. **Tile** (`world.py`):
   - Añadir campos:
     - `subtype: str | None = None` — ej. "POISONOUS_BERRY", "SAFE_BERRY", "OAK_TREE", "PINE_TREE"
     - `hidden_properties: dict[str, Any] = field(default_factory=dict)` — ej. `{"is_poisonous": True}`
   - Definir diccionario `RESOURCE_SUBTYPES` que mapee resource_type → lista de subtipos con sus hidden_properties:
     ```python
     RESOURCE_SUBTYPES = {
         "berries": [
             {"name": "SAFE_BERRY", "hidden": {}, "weight": 70},
             {"name": "POISONOUS_BERRY", "hidden": {"is_poisonous": True}, "weight": 30},
         ],
         "tree": [
             {"name": "OAK_TREE", "hidden": {"wood_quality": "strong"}, "weight": 50},
             {"name": "PINE_TREE", "hidden": {"wood_quality": "light"}, "weight": 50},
         ],
     }
     ```

2. **World generation** (`world.py`):
   - En `_place_resource()` o post-generación: asignar `subtype` y `hidden_properties` aleatoriamente según los weights definidos.
   - No todos los recursos necesitan subtype — agua y stone pueden no tenerlo (o tenerlo opcional).

3. **TileUpdate schema** (`schemas.py`):
   - Añadir campo opcional `subtype: str | None = None`
   - **NO** incluir `hidden_properties` — eso es intencional (las propiedades ocultas no son visibles en el snapshot).

4. **Snapshot builder** (`snapshot.py`):
   - En `_build_agent_state()` y `build()/build_delta()`: incluir `tile.subtype` en los `TileUpdate` pero **NO** `tile.hidden_properties`.

**Criterios de aceptación**:
- [x] Tile tiene campos `subtype` y `hidden_properties` con defaults seguros
- [x] Recursos se generan con subtipos según weights definidos
- [x] TileUpdate schema incluye `subtype` pero NO `hidden_properties`
- [x] Snapshot del mundo muestra `subtype` pero nunca `hidden_properties`
- [x] Test `test_tile_with_subtype` y `test_snapshot_does_not_expose_hidden` pasan

---

### T12 — Añadir `knowledge` al Agent y revelar propiedades ocultas al comer
**Feature**: F2
**Fase**: 3
**Archivos**: `backend/app/simulation/agent.py`, `backend/app/simulation/actions.py`, `backend/app/models/schemas.py`, `backend/app/simulation/snapshot.py`
**Depende de**: T11
**Estimación**: Media

**Descripción**:

1. **Agent** (`agent.py`): Añadir campo `knowledge: dict[str, dict[str, Any]] = field(default_factory=dict)` al dataclass `Agent`. Key = subtype name, Value = dict de propiedades reveladas.

2. **handle_eat** (`actions.py`):
   - Modificar `handle_eat()` para que, después de consumir berries:
     - Si el tile de origen tiene `subtype` y `hidden_properties`:
       - Revelar: `agent.knowledge[tile.subtype] = dict(tile.hidden_properties)`
       - Añadir efecto en `action_summary`: `"... learned: POISONOUS_BERRY is poisonous"`
     - Si no hay subtype, no hay cambio en knowledge.
   - Nota: `handle_eat()` actualmente reduce hambre usando berries del inventario. Necesitamos saber de qué tile vino la berry. Opción: buscar en `_tiles_on_or_adjacent` un tile con subtype y restar de ahí. Alternativa: el step puede incluir la fuente. Revisar cómo se llama actualmente.

3. **AgentState** (`schemas.py`):
   - Añadir campo `knowledge: list[str] = []` — lista de nombres de subtipos conocidos (para UI, no el dict completo).

4. **Snapshot builder** (`snapshot.py`):
   - En `_build_agent_state()`: incluir `knowledge=list(agent.knowledge.keys())` (solo los nombres de subtipos conocidos).

**Criterios de aceptación**:
- [x] Agent tiene `knowledge: dict` vacío por defecto
- [x] Consumir un tile con `subtype` y `hidden_properties` → knowledge se actualiza
- [x] El action_summary incluye el learning (ej. "learned: POISONOUS_BERRY")
- [x] Dos agentes que comen diferentes cosas tienen knowledge independiente
- [x] Tests `test_eat_reveals_hidden_properties`, `test_knowledge_is_per_agent` pasan

---

### T13 — Añadir knowledge al prompt LLM
**Feature**: F2
**Fase**: 3
**Archivos**: `backend/app/ai/prompts.py`, `backend/app/ai/orchestrator.py`
**Depende de**: T12
**Estimación**: Baja

**Descripción**:

1. **Prompt template** (`prompts.py`):
   - Añadir nueva sección `KNOWLEDGE:` después de `NEARBY RESOURCES`:
   ```
   KNOWLEDGE:
   - You know: {knowledge_string}
   ```
   - Formato: si el agente sabe que POISONOUS_BERRY es peligroso: `"POISONOUS_BERRY is poisonous"`
   - Si no hay knowledge: `"(you have no special knowledge yet)"`

2. **MockLLMOrchestrator** (`agent.py`): Actualizar `build_prompt()` para incluir knowledge.

3. **RealLLMOrchestrator** (`orchestrator.py`): Actualizar `build_prompt()` para pasar knowledge al template. Extraer de `agent.knowledge` y formatear como string.

**Criterios de aceptación**:
- [x] Prompt incluye sección KNOWLEDGE con los subtipos conocidos formateados
- [x] Agente sin knowledge muestra "(you have no special knowledge yet)"
- [x] Test `test_knowledge_in_prompt` pasa

---

### T14 — Crear acción `TRADE` (ActionType + handler)
**Feature**: F5
**Fase**: 3
**Archivos**: `backend/app/simulation/actions.py`, `backend/app/simulation/engine.py`
**Depende de**: T2 (ActionResult fields)
**Estimación**: Media

**Descripción**:

1. **ActionType** (`actions.py`):
   - Añadir `TRADE = "trade"` al enum `ActionType`.
   - Añadir `SOCIALIZE = "socialize"` (necesario para F6, pero el enum se define aquí).
   - Añadir `FEED_CHILD = "feed_child"` (necesario para F3, pero el enum se define aquí).

2. **Handler** `handle_trade()` (`actions.py`):
   ```python
   def handle_trade(agent, world, target, step) -> ActionResult:
       # Validar que proposer tiene offer resources (step["offer"])
       # Validar que target existe y está cerca
       # NO ejecutar el swap aquí — solo validar y encolar propuesta
       # Retornar ActionResult con action_type=TRADE
       # El swap real se hace en el engine cuando el target acepta
   ```
   - `handle_trade()` valida que el proponente tiene los recursos de `offer`.
   - Enqueuea un `Message` de tipo `{"type": "trade_proposal", "from": proposer.id, "offer": {...}, "request": {...}}` en el conversation_queue del target.
   - Si el proponente no tiene suficientes recursos, falla con success=False.
   - Registra el `action_type` y `action_summary`.

3. **REGISTRY** (`actions.py`): Añadir `ActionType.TRADE: handle_trade` al registro.

4. **get_action_duration** (`actions.py`): Añadir duración para `ActionType.TRADE` (ej. 5 ticks).

5. **ACTION_EMOJIS** (`actions.py`): Añadir emoji para trade (ej. "🤝").

6. **Engine** (`engine.py`):
   - El handler `handle_trade()` solo valida y encola. El engine, en `_process_social_interactions()` o en `_fsm_evaluate()`, debe:
     - Detectar mensajes `trade_proposal` en la cola del target.
     - Pasar al LLM del target para decidir accept/reject.
     - Si accept: ejecutar el swap atómico (debitar offer de proponente, debitar request de target, acreditar ambos).
     - Si reject/timeout: no-op, loguear SimEvent.

7. **FSM evaluate**: Añadir comprobación: si el agente tiene un `trade_proposal` en su cola, priorizar la decisión sobre el trade (ir a LLM).

**Criterios de aceptación**:
- [x] `ActionType.TRADE` existe en el enum
- [x] `handle_trade()` valida recursos y encola propuesta como Message
- [x] Recursos insuficientes → fail, sin cambios en inventarios
- [x] `handle_trade()` registra `action_type` y `action_summary` correctamente
- [x] Tests `test_trade_insufficient_funds` pasa

---

### T15 — Flujo completo de trade: evaluación por LLM y swap atómico
**Feature**: F5
**Fase**: 3
**Archivos**: `backend/app/simulation/engine.py`, `backend/app/simulation/conversation.py`, `backend/app/simulation/actions.py`
**Depende de**: T14, T8 (conversation_queue en engine)
**Estimación**: Alta

**Descripción**:

1. **Trade evaluation flow** en `engine.py`:
   - En `_fsm_evaluate()`: si el agente tiene mensajes `trade_proposal` en su `conversation_queue`:
     - Ir a `llm_trigger` con contexto de "trade decision needed"
     - El prompt debe incluir la propuesta: "Agent X wants to trade: give {offer} for {request}"
     - El LLM responde con `{"action": "accept_trade"}` o `{"action": "reject_trade"}`
   - Nueva función `_execute_trade(proposer, target, offer, request) -> bool`:
     - Verifica que ambos aún tienen los recursos (race condition check)
     - Debita `offer` de proposer, debita `request` de target
     - Acredita `request` a proposer, acredita `offer` a target
     - Incrementa `interaction_count` para ambos via `_update_relationship`
     - Loguea SimEvent `type="trade"` con success=true
     - Si falla (alguien gastó recursos entremedio), rollback implícito (no hacer nada)
   - Si el LLM rejecta o timeout: loguear SimEvent `type="trade"` con success=false

2. **Procesamiento en `_process_social_interactions()`**:
   - Después de detectar encuentros, procesar propuestas de trade pendientes.
   - Para cada propuesta, verificar si el target ya respondió (tiene un accept/reject en su plan).
   - Si aceptó: ejecutar swap. Si rechazó: no-op.

3. **Trade proposer flow**:
   - Proposer ejecuta `handle_trade()` que valida y encola.
   - En tick siguiente, target procesa y responde.
   - En tick siguiente, proposer ve el resultado (SimEvent).

4. **Prompt instruction**: Añadir instrucción al JSON format para accept/reject trade:
   ```json
   {
     "decision": "accept" | "reject",
     "reason": "why"
   }
   ```

**Criterios de aceptación**:
- [x] Target LLM recibe contexto de trade proposal
- [x] Trade aceptado: swap atómico con ambos inventarios actualizados
- [x] Trade rechazado: no hay cambios en ningún inventario
- [x] Trade timeout: se trata como rechazo, no hay cambios
- [x] SimEvent "trade" se loguea con success=true/false
- [x] interaction_count se incrementa en trade exitoso
- [x] Tests `test_trade_atomic_swap`, `test_trade_interaction_count`, integración F5+F6+F8 pasan

---

### T16 — Compartir conocimiento vía conversaciones (F2 + F6)
**Feature**: F2, F6
**Fase**: 3
**Archivos**: `backend/app/simulation/conversation.py`, `backend/app/simulation/engine.py`
**Depende de**: T12 (knowledge en Agent), T8 (conversation_queue en engine)
**Estimación**: Media

**Descripción**:

1. **Compartir conocimiento en `_process_social_interactions()`**:
   - Cuando un agente A y B se encuentran (greeting), el sistema puede generar automáticamente un mensaje `share_knowledge` si A tiene knowledge relevante y B no.
   - Lógica: si A tiene `knowledge` y B no tiene entrada para alguno de esos subtipos, A comparte uno al azar.
   - El mensaje `Message.content = {"type": "share_knowledge", "subtype": "POISONOUS_BERRY", "properties": {"is_poisonous": True}}`.

2. **Procesar `share_knowledge` en el receptor**:
   - En `_fsm_evaluate()` (o en el processing de la cola): cuando un agente tiene un mensaje `share_knowledge`:
     - Actualizar `agent.knowledge[subtype] = properties`
     - Loguear SimEvent `type="knowledge_shared"`
   - Esto no requiere acción LLM — es automático.

3. **Incrementar interaction_count por knowledge share**:
   - Llamar a `_update_relationship(A, B, tick, score_delta=0.05)` cuando se comparte conocimiento.

**Criterios de aceptación**:
- [x] Agente A con knowledge y B sin knowledge → A comparte knowledge a B
- [x] B.knowledge se actualiza con la información compartida
- [x] SimEvent "knowledge_shared" se loguea
- [x] interaction_count se incrementa
- [x] Tests `test_knowledge_share_via_message`, `test_knowledge_shared_via_conversation` pasan

---

### T17 — Tests de Fase 3 (F2 + F5)
**Feature**: F2, F5
**Fase**: 3
**Archivos**: `backend/tests/test_social.py` (añadir a archivo existente de F6 tests)
**Depende de**: T11, T12, T13, T14, T15, T16
**Estimación**: Baja

**Descripción**:
Implementar todos los tests para F2 y F5:

**F2 Tests:**
- `test_tile_with_subtype` — Crear Tile con subtype+hidden, snapshot NO expone hidden
- `test_eat_reveals_hidden_properties` — Agent come POISONOUS_BERRY → knowledge poblado
- `test_knowledge_is_per_agent` — Dos agents, uno come → knowledge difiere
- `test_knowledge_in_prompt` — Agent con knowledge → string aparece en prompt
- `test_knowledge_share_via_message` — Actualización directa de knowledge vía Message

**F5 Tests:**
- `test_trade_atomic_swap` — Ambos tienen suficiente → ambos inventarios actualizados
- `test_trade_insufficient_funds` — Proponente no tiene recursos → fail, sin cambios
- `test_trade_interaction_count` — Trade exitoso incrementa interaction_count de ambos

**Integration tests:**
- `test_knowledge_shared_via_conversation` — Flujo completo conversación → knowledge propagado
- `test_trade_increments_interaction_count` — Trade completo → interaction_count actualizado

---

## Fase 4 — Lifecycle & Groups (F3: Infancia + F4: Facciones)

### T18 — Añadir campos de infancia al Agent y crear acción `FEED_CHILD`
**Feature**: F3
**Fase**: 4
**Archivos**: `backend/app/simulation/agent.py`, `backend/app/simulation/actions.py`, `backend/app/simulation/engine.py`
**Depende de**: T2 (ActionResult fields), Fase 2 (conversation_queue)
**Estimación**: Media

**Descripción**:

1. **Agent** (`agent.py`): Añadir campos:
   - `is_child: bool = False`
   - `parent_id: str | None = None`
   - `maturity_age: int = 500`

2. **AgentState** (`schemas.py`): Añadir:
   - `is_child: bool = False`
   - `faction_id: str | None = None` (se añade en T19, pero el schema se actualiza aquí)

3. **Snapshot** (`snapshot.py`): Actualizar `_build_agent_state()` para incluir `is_child` y `parent_id` (si existe).

4. **ActionType** (`actions.py`): Ya se añadió `FEED_CHILD` en T14. Verificar que esté en el enum.

5. **Handler** `handle_feed_child()` (`actions.py`):
   ```python
   def handle_feed_child(agent, world, target, step) -> ActionResult:
       # target = child_id
       # Buscar child agent en engine (o pasar como parámetro)
       # Validar: child está dentro de INTERACTION_RADIUS
       # Validar: caregiver tiene berries en inventario
       # child.hunger = max(0, child.hunger - 30)
       # agent.inventory["berries"] -= 1
       # action_summary incluye child hunger change
   ```
   - Necesita acceso al child Agent. El handler recibe el engine o la lista de agentes como parámetro extra. Alternativa: pasar `target` como `(child_id,)` y buscar en `engine.agents`.
   - **Importante**: `handle_feed_child` debe recibir referencia al engine o a la lista de agentes. Cambiar la firma del handler o añadir un contexto.

6. **REGISTRY** (`actions.py`): Añadir `ActionType.FEED_CHILD: handle_feed_child`.

7. **get_action_duration** y **ACTION_EMOJIS**: Añadir entrada para FEED_CHILD.

**Criterios de aceptación**:
- [x] Agent tiene `is_child`, `parent_id`, `maturity_age` con defaults seguros
- [x] `handle_feed_child()` reduce hambre del child en 30 y consume 1 berry del caregiver
- [x] Child fuera de radio → action falla
- [x] Caregiver sin berries → action falla
- [x] Tests `test_feed_child_action` pasa

---

### T19 — Spawn de child junto al padre, gating FSM de childhood, prioridad del caregiver
**Feature**: F3
**Fase**: 4
**Archivos**: `backend/app/simulation/engine.py`
**Depende de**: T18
**Estimación**: Alta

**Descripción**:

1. **Child spawning** en `_create_offspring()`:
   - Modificar para que el nuevo agente nazca con:
     - `is_child=True`
     - `parent_id=parent1.id` (el que inició la reproducción, o ambos padres)
     - `maturity_age=random.randint(300, 700)`
   - Posición: spawn en tile adyacente al padre (Manhattan distance ≤ 2). Reemplazar la lógica actual de posición promedio.
     ```python
     # Buscar tile vacío adyacente a parent1
     for dx, dy in [(0,0), (1,0), (-1,0), (0,1), (0,-1)]:
         nx, ny = int(parent1.position[0]) + dx, int(parent1.position[1]) + dy
         if not self._is_tile_occupied(nx, ny):
             child.position = (float(nx), float(ny))
             break
     ```
   - Stats heredados: `child.str = parent1.str ± random(0, 15)`, clamp [0, 100]. Usar el padre que inició la reproducción para la herencia primaria.

2. **FSM gating para children** en `_fsm_evaluate()`:
   - Si `agent.is_child`:
     - Bloquear EAT y DRINK: si la evaluación llega a los pasos 1-3 (comer/beber), ignorar y pasar directamente a "wait for caregiver" (no hacer nada, transition a idle).
     - No enviar child a LLM (saltar paso 7). Los children actúan por instinto: solo deambulan (move aleatorio) cerca del padre.
     - Energía y hambre/sed del child siguen decayendo normalmente.

3. **Caregiver priority** en `_fsm_evaluate()`:
   - Antes del paso 1 (incluso antes de las necesidades propias), si el agente tiene un child (buscar en `self.agents` donde `parent_id == agent.id`):
     - Verificar si child.hunger > 70 o child.thirst > 70
     - Si es crítico: ejecutar `FEED_CHILD(child_id)` como acción prioritaria, incluso por encima de las propias necesidades del caregiver.
     - El caregiver debe estar cerca del child (INTERACTION_RADIUS). Si no, mover hacia el child primero (pathfinding al child).

4. **Maturity check** en `_process_needs()`:
   - Por cada child: si `agent.age >= agent.maturity_age`:
     - `agent.is_child = False`
     - `agent.parent_id = None` (opcional, se puede mantener para registro)
     - Loguear SimEvent type="maturity"

**Criterios de aceptación**:
- [x] Newborn spawns adjacent to parent (Manhattan ≤ 2)
- [x] Newborn tiene `is_child=True`, `parent_id` seteado, `maturity_age` aleatorio 300-700
- [x] Stats del child están dentro de [parent ± 15]
- [x] Child no puede ejecutar EAT o DRINK
- [x] Caregiver prioriza FEED_CHILD cuando child está crítico (hambre/sed > 70)
- [x] Al alcanzar maturity_age, is_child=False y child gana autonomía
- [x] Tests `test_child_blocks_eat`, `test_child_stat_inheritance`, `test_child_maturity`, `test_child_spawn_adjacent_to_parent` pasan

---

### T20 — Sistema de adopción de huérfanos
**Feature**: F3
**Fase**: 4
**Archivos**: `backend/app/simulation/engine.py`, `backend/app/simulation/event_queue.py`
**Depende de**: T19
**Estimación**: Media

**Descripción**:

1. **Death handler** en `_process_needs()`:
   - Cuando un agente muere, antes de removerlo de `self.agents`:
     - Buscar en `self.agents` si algún child tiene `parent_id == dead_agent.id`
     - Si hay dependientes:
       - Buscar el adulto más cercano dentro de `INTERACTION_RADIUS` que no sea el fallecido
       - Si existe: reasignar `child.parent_id = new_caregiver.id`
       - Loguear SimEvent `type="adoption"` con descripción "X adopted Y after Z died"
       - Si no existe adulto cercano: el child se queda sin caregiver. Su salud decae 2x cada tick (hambre/sed suben 2x). Eventualmente muere.

2. **Añadir constante** `ORPHAN_DECAY_MULTIPLIER = 2.0` para acelerar decaimiento de huérfanos.

3. **Event types**: Añadir `"adoption"` a SimEvent types válidos.

**Criterios de aceptación**:
- [x] Cuando caregiver muere y hay adulto cercano → child es adoptado (parent_id actualizado)
- [x] SimEvent "adoption" se loguea con descripción informativa
- [x] Cuando caregiver muere sin adultos cerca → child entra en decadencia acelerada
- [x] Test `test_orphan_adoption` pasa

---

### T21 — Crear `Faction` dataclass y `FactionManager`
**Feature**: F4
**Fase**: 4
**Archivos**: `backend/app/simulation/faction.py` (NUEVO)
**Depende de**: Ninguna (se puede hacer en paralelo con T18-T20)
**Estimación**: Media

**Descripción**:
Crear nuevo módulo `backend/app/simulation/faction.py`:

1. **`FactionSummary` dataclass** (para respuesta API):
   ```python
   @dataclass
   class FactionSummary:
       id: str
       name: str
       color: str
       member_count: int
       shared_resources: dict[str, int]
   ```

2. **`Faction` dataclass**:
   ```python
   @dataclass
   class Faction:
       id: str
       name: str
       color: str  # hex, e.g. "#FF0000"
       member_ids: list[str] = field(default_factory=list)
       shared_resources: dict[str, int] = field(default_factory=dict)
   ```

3. **`FactionManager` class**:
   ```python
   class FactionManager:
       def __init__(self):
           self.factions: dict[str, Faction] = {}
       
       def create(self, name: str, color: str) -> Faction
       def delete(self, faction_id: str) -> bool
       def join(self, agent_id: str, faction_id: str) -> bool  # returns False if full/error
       def leave(self, agent_id: str, faction_id: str) -> bool
       def list_all(self) -> list[FactionSummary]
       def get_faction(self, faction_id: str) -> Faction | None
       def transfer_inventory_on_death(self, agent) -> None  # agent.inventory → faction.shared_resources
       def get_all(self) -> dict[str, Faction]
   ```
   - `create()` genera UUID para faction id
   - `join()` añade agent_id a member_ids
   - `leave()` remueve agent_id de member_ids
   - `transfer_inventory_on_death()` suma cada item del inventario del agente a `shared_resources`

4. **FactionManager config inicial**: Si no se pasa configuración de facciones, crear 3 facciones por defecto:
   - "River Clan" (#00AAFF)
   - "Stone Hold" (#FF8800)
   - "Green Ward" (#44BB44)

5. Registrar en `backend/app/simulation/__init__.py`.

**Criterios de aceptación**:
- [x] `Faction` dataclass con todos los campos requeridos
- [x] `FactionManager` soporta CRUD completo (create, delete, join, leave, list)
- [x] `transfer_inventory_on_death()` mueve inventario a shared_resources
- [x] Facciones por defecto se crean si no se provee configuración
- [x] Tests `test_faction_crud`, `test_faction_death_transfer` pasan

---

### T22 — Integrar facciones en el engine, snapshot y prompts
**Feature**: F4
**Fase**: 4
**Archivos**: `backend/app/simulation/agent.py`, `backend/app/simulation/engine.py`, `backend/app/models/schemas.py`, `backend/app/simulation/snapshot.py`, `backend/app/ai/prompts.py`, `backend/app/simulation/event_queue.py`
**Depende de**: T21
**Estimación**: Alta

**Descripción**:

1. **Agent** (`agent.py`): Añadir `faction_id: str | None = None` al dataclass `Agent`.

2. **Engine** (`engine.py`):
   - En `__init__()`: instanciar `self.faction_manager = FactionManager()`.
   - Al añadir agente (`add_agent()` o en start): asignar agente a una facción (distribuir uniformemente o aleatoria). Opción: mantener la lógica de distribución en el engine.
   - En `_process_needs()`: cuando un agente muere, llamar a `self.faction_manager.transfer_inventory_on_death(agent)` si el agente pertenece a una facción.
   - Añadir tick phase `_process_faction_agent_death(tick)` después de `_process_social_interactions()`.

3. **Event types** (`event_queue.py`): Añadir `"faction_join"`, `"faction_leave"` a tipos válidos.

4. **WorldSnapshot schema** (`schemas.py`):
   - Añadir campo `factions: list[dict] = []` con lista de resúmenes de facciones.
   - Añadir campo `colony_stats: dict | None = None` (placeholder para F7).

5. **Snapshot builder** (`snapshot.py`):
   - En `_build_agent_state()`: incluir `faction_id`.
   - En `build()` y `build_delta()`: incluir `factions` desde `engine.faction_manager.list_all()` como lista de dicts.
   - El builder necesita acceso al `faction_manager`. Pasar como parámetro en constructor o mantener referencia.

6. **Prompts** (`prompts.py`):
   - Añadir sección `FACTION:` en el prompt:
   ```
   FACTION:
   - You are a member of "{faction_name}" (color: {faction_color})
   ```
   - Si no tiene facción: "(you are not in a faction)".
   - En la sección de relaciones, si el otro agente es de la misma facción, añadir "(faction ally)".

7. **Orchestrator** (`orchestrator.py`):
   - Pasar `agent.faction_id` al build_prompt, resolver nombre de facción desde faction_manager si está disponible.

**Criterios de aceptación**:
- [x] Agent tiene `faction_id` con default None
- [x] Engine instancia FactionManager y asigna facciones a agentes al iniciar
- [x] Muerte de miembro de facción → inventory transferido a shared_resources
- [x] Snapshot incluye lista de facciones con id, name, color, member_count, shared_resources
- [x] Prompt incluye sección FACTION
- [x] Tests de integración F4 pasan

---

### T23 — Tests de Fase 4 (F3 + F4)
**Feature**: F3, F4
**Fase**: 4
**Archivos**: `backend/tests/test_social.py` (añadir)
**Depende de**: T18, T19, T20, T21, T22
**Estimación**: Baja

**Descripción**:
Implementar tests para F3 y F4:

**F3 Tests:**
- `test_child_blocks_eat` — is_child=True → handle_eat() falla/bloqueada
- `test_feed_child_action` — Caregiver tiene berries, child cerca → hunger child baja, inventario caregiver baja
- `test_child_stat_inheritance` — Stats parent ± random(0,15), child dentro de rango esperado
- `test_child_maturity` — Tick llega a maturity_age → is_child=False
- `test_orphan_adoption` — Caregiver muere, adulto más cercano dentro de radio adopta

**F4 Tests:**
- `test_faction_crud` — Create, delete, join, leave, list
- `test_faction_death_transfer` — Agent muere → inventory se mueve a faction.shared_resources
- `test_faction_defaults` — 3 facciones por defecto creadas al iniciar

**Integration tests:**
- `test_child_spawn_adjacent_to_parent` — Después de reproducción F8, child spawn adyacente
- `test_faction_in_snapshot` — Snapshot incluye lista de facciones con datos correctos

---

## Fase 5 — Colony UI (F7: Panel de colonia + Widgets HUD)

### T24 — Crear `ColonyStats` collector y endpoint REST `/api/colony`
**Feature**: F7
**Fase**: 5
**Archivos**: `backend/app/simulation/colony.py` (NUEVO), `backend/app/models/schemas.py`, `backend/app/main.py` o nueva ruta
**Depende de**: T22 (factions en snapshot), Fase 3 completa
**Estimación**: Alta

**Descripción**:

1. **ColonyStats dataclass** (`colony.py`):
   ```python
   @dataclass
   class ColonyStats:
       population: int
       births: int
       deaths: int
       role_distribution: dict[str, int]
       sex_distribution: dict[str, int]
       age_groups: dict[str, int]  # "child": N, "adult": N, "elder": N
       total_resources: dict[str, int]
       factions: list[FactionSummary]
   ```
   - `total_resources` = suma de todos los inventarios de todos los agentes
   - `age_groups`: child = is_child=True, elder = age > max_age*0.7, adult = resto
   - `births`/`deaths` = contadores de sesión (acumulados desde start)

2. **ColonyStatsCollector** (`colony.py`):
   ```python
   class ColonyStatsCollector:
       def __init__(self):
           self.births = 0
           self.deaths = 0
       
       def record_birth(self): self.births += 1
       def record_death(self): self.deaths += 1
       
       def collect(self, agents: list[Agent], faction_manager) -> ColonyStats:
           # Compute from current state
   ```
   - El engine debe llamar a `record_birth()` y `record_death()` cuando ocurren.

3. **Engine** (`engine.py`):
   - Instanciar `self.colony_stats_collector = ColonyStatsCollector()`.
   - En creación de agente y muerte, llamar a `record_birth()` / `record_death()`.

4. **REST endpoint** — Crear `backend/app/api/colony.py` o añadir a ruta existente:
   ```python
   @router.get("/api/colony")
   async def get_colony_stats(request: Request):
       engine = request.app.state.engine
       stats = engine.colony_stats_collector.collect(engine.agents, engine.faction_manager)
       return stats  # como dict
   ```
   - Requiere FastAPI, registrar router en `main.py` como `app.include_router(colony_router)`.

5. **Schema Pydantic** (`schemas.py`):
   - Añadir `class ColonyStatsResponse(BaseModel)` con todos los campos de ColonyStats.

**Criterios de aceptación**:
- [x] `ColonyStats` dataclass con todos los campos requeridos
- [x] `ColonyStatsCollector.collect()` produce estadísticas correctas de la población actual
- [x] `GET /api/colony` retorna JSON con estructura correcta
- [x] births y deaths son contadores de sesión (no se resetean cada tick)
- [x] Test `test_colony_endpoint` pasa

---

### T25 — Extender snapshot WebSocket con `colony_stats`
**Feature**: F7
**Fase**: 5
**Archivos**: `backend/app/models/schemas.py`, `backend/app/simulation/snapshot.py`
**Depende de**: T24
**Estimación**: Baja

**Descripción**:

1. **WorldSnapshot schema** (`schemas.py`):
   - Añadir campo `colony_stats: dict | None = None` al modelo `WorldSnapshot`.
   - Debe incluir subset de ColonyStats: population, births, deaths, total_resources.

2. **Snapshot builder** (`snapshot.py`):
   - En `build()` y `build_delta()`: incluir `colony_stats` con:
     ```python
     colony_stats = {
         "population": len(self.agents),
         "births": colony_collector.births,
         "deaths": colony_collector.deaths,
         "total_resources": {... aggregated from all agents ...}
     }
     ```
   - Requiere pasar `colony_stats_collector` al builder. Añadir como parámetro en `__init__()`.

3. **Engine** (`engine.py`):
   - Pasar `colony_stats_collector` al `WorldSnapshotBuilder` en `__init__()`.

**Criterios de aceptación**:
- [x] WorldSnapshot tiene campo `colony_stats` con population, births, deaths, total_resources
- [x] Datos en snapshot coinciden con endpoint REST
- [x] Test `test_colony_stats_in_snapshot` pasa

---

### T26 — Actualizar frontend store con `colony_stats` y `factions`
**Feature**: F7
**Fase**: 5
**Archivos**: `frontend/src/lib/stores/simulationStore.svelte.js`
**Depende de**: T25 (snapshot extendido), T22 (factions en snapshot)
**Estimación**: Baja

**Descripción**:

1. **SimulationState typedef** — Añadir campos:
   ```javascript
   colony_stats: { population: number, births: number, deaths: number, total_resources: Record<string, number> } | null
   factions: Record<string, { id: string, name: string, color: string, member_count: number, shared_resources: Record<string, number> }>
   ```

2. **INITIAL_STATE** — Añadir valores iniciales:
   - `colony_stats: null`
   - `factions: {}`

3. **updateFromSnapshot()** — Consumir `colony_stats` y `factions` del snapshot payload:
   ```javascript
   colony_stats: data.colony_stats ?? state.colony_stats,
   factions: data.factions ?? state.factions,
   ```

**Criterios de aceptación**:
- [x] Store tiene campo `colony_stats` con valores correctos desde snapshot
- [x] Store tiene campo `factions` con datos desde snapshot
- [x] Datos persisten entre snapshots (no se resetean si no vienen en un tick)
- [x] No rompe funcionalidad existente

---

### T27 — Crear `ColonyInfo.svelte`
**Feature**: F7
**Fase**: 5
**Archivos**: `frontend/src/lib/components/ColonyInfo.svelte` (NUEVO)
**Depende de**: T26 (store actualizado)
**Estimación**: Media

**Descripción**:

Crear componente Svelte 5 que muestre un panel completo de información de la colonia:

1. **Layout**: Panel plegable, estilo consistente con AgentInspector (fondo oscuro semi-transparente, misma tipografía).

2. **Secciones**:
   - **Population**: total, births (sesión), deaths (sesión)
   - **Demographics**:
     - Role distribution: barras simples (gatherer, builder, scout, etc.)
     - Sex distribution: male/female counts
     - Age groups: child / adult / elder counts
   - **Total Resources**: tabla de recursos agregados (berries, wood, stone, etc.) con emojis
   - **Active Factions**: tarjetas de cada facción con nombre, color swatch, member count, shared resources

3. **Data source**: Suscribirse a `$simulationStore.colony_stats` y `$simulationStore.factions`.

4. **Auto-refresh**: Se actualiza reactivamente via Svelte 5 stores (no polling). Cada snapshot actualiza los datos.

5. **Posición**: Panel anclado a la derecha o como overlay. Opcional: mostrar/ocultar con botón en HUD.

**Criterios de aceptación**:
- [x] Panel muestra population, births, deaths correctamente
- [x] Role/sex/age distribution se renderiza con barras o tabla
- [x] Total resources suma correctamente
- [x] Active factions muestra nombre, color, member_count, shared_resources
- [x] Se actualiza automáticamente con cada snapshot vía store reactivity
- [x] No rompe layout existente

---

### T28 — Crear `HudWidgets.svelte` con métricas clave de colonia
**Feature**: F7
**Fase**: 5
**Archivos**: `frontend/src/lib/components/HudWidgets.svelte` (NUEVO)
**Depende de**: T26 (store actualizado)
**Estimación**: Baja

**Descripción**:

Crear componente minimalista de widgets HUD que muestre métricas clave de la colonia:

1. **Widgets** (pequeños contadores numéricos):
   - Population count (icono: 👥)
   - Births this session (icono: 👶)
   - Deaths this session (icono: 💀)
   - Active factions (icono: 🚩)

2. **Data source**: `$simulationStore.colony_stats` y `$simulationStore.factions`.

3. **Posición**: Integrar en el HUD existente (`HUD.svelte`) o como barra separada cerca del HUD.

4. **Estilo**: Mínimo, solo números con iconos pequeños. Mismo fondo que HUD existente.

**Criterios de aceptación**:
- [x] Widgets muestran population, births, deaths correctamente
- [x] Se actualizan automáticamente vía store
- [x] Estilo consistente con HUD existente

---

### T29 — Actualizar `AgentInspector` con relaciones, facción, conocimiento y child status
**Feature**: F8, F4, F2, F3 (frontend)
**Fase**: 5
**Archivos**: `frontend/src/lib/components/AgentInspector.svelte`
**Depende de**: T26 (store con datos actualizados)
**Estimación**: Media

**Descripción**:

Añadir nuevas secciones al panel `AgentInspector.svelte`:

1. **Relationships section** (F8):
   - Lista de agentes conocidos: nombre, interaction_count, score (barra de color), last_interaction_tick
   - Si no hay relaciones: "(no relationships yet)"

2. **Faction section** (F4):
   - Si `agent.faction_id` existe: mostrar nombre de facción + color swatch (círculo de color) al lado
   - Si no: "(not in a faction)"

3. **Knowledge section** (F2):
   - Lista de subtipos conocidos (de `agent.knowledge` — array de strings)
   - Si no hay: "(no special knowledge)"

4. **Child Status section** (F3):
   - Si `agent.is_child`: mostrar "🧒 Child", parent_id, maturity progress bar (age / maturity_age)
   - Si no: mostrar "Adult"

5. **Actualizar interface AgentData** con los nuevos campos:
   ```typescript
   interface AgentData {
       // ... existing fields ...
       relationships?: Record<string, { interaction_count: number, last_interaction_tick: number, score: number }>;
       faction_id?: string;
       knowledge?: string[];
       is_child?: boolean;
       parent_id?: string;
       maturity_age?: number;
   }
   ```

**Criterios de aceptación**:
- [x] AgentInspector muestra sección "Relationships" con interacciones conocidas
- [x] AgentInspector muestra facción con color swatch si aplica
- [x] AgentInspector muestra subtipos conocidos en sección "Knowledge"
- [x] AgentInspector muestra child status con barra de madurez
- [x] No rompe secciones existentes (Vital Signs, Identity, Attributes, Inventory, Monologue, Prompt)

---

### T30 — Actualizar renderizado del canvas con colores de facción
**Feature**: F4 (frontend)
**Fase**: 5
**Archivos**: `frontend/src/lib/canvas/entities.ts`, `frontend/src/lib/canvas/engine.ts` (si aplica)
**Depende de**: T26 (store con datos de facciones)
**Estimación**: Media

**Descripción**:

1. **AgentRenderData** (`entities.ts`):
   - Añadir campo `factionColor: string | null = null`.

2. **updateFromSnapshot()**:
   - Leer `state.faction_id` desde el snapshot de cada agente.
   - Resolver color desde `simulationStore.factions[state.faction_id]?.color`.
   - Asignar a `a.factionColor`.

   Alternativa: pasar faction_id y resolver en el draw step mediante un lookup map.

3. **draw()**:
   - Después de dibujar el círculo del agente, si `a.factionColor` no es null:
     ```typescript
     if (a.factionColor) {
         ctx.beginPath();
         ctx.arc(px, py, RADIUS + 3, 0, Math.PI * 2);
         ctx.strokeStyle = a.factionColor;
         ctx.lineWidth = 3;
         ctx.stroke();
     }
     ```
   - El borde coloreado se dibuja por fuera del círculo del role.

4. **Faction color resolution**: El `entities.ts` necesita acceso a los datos de facciones. Opciones:
   - Opción A: pasar `factions` dict como parámetro a `updateFromSnapshot()`.
   - Opción B: resolver en el canvas engine (donde se llama a `updateFromSnapshot`) y pasar `factionColor` directamente.

**Criterios de aceptación**:
- [x] Agentes con facción muestran borde coloreado en el canvas
- [x] Agentes sin facción no muestran borde extra
- [x] Color del borde corresponde al color de la facción
- [x] No rompe renderizado existente (sombras, nombres, hunger bars, emojis)

---

## Resumen de Dependencias

```
T1 ──→ T2 ──→ T6 (tests F1)
  │
  └──→ T3 ──→ T4 ──→ T5 ──→ T6 (tests F8)
                │
                └──→ T7 ──→ T8 ──→ T9 ──→ T10 (tests F6)
                                    │
                    ┌───────────────┘
                    ▼
T11 ──→ T12 ──→ T13 ──→ T16 ──→ T17 (tests F2)
  │                 │
  │                 └──→ T14 ──→ T15 ──→ T17 (tests F5)
  │                               │
  │                               └──→ T16 (knowledge share)
  ▼
T18 ──→ T19 ──→ T20 ──→ T23 (tests F3)
  │
  ├──→ T21 ──→ T22 ──→ T23 (tests F4)
  │
  └──→ T24 ──→ T25 ──→ T26 ──→ T27 (ColonyInfo)
                                ├──→ T28 (HudWidgets)
                                ├──→ T29 (AgentInspector)
                                ├──→ T30 (Canvas factions)
                                └──→ T31 (HUD updates)
```

## Estimación total por fase

| Fase | Tareas | Archivos nuevos | Archivos modificados | Estimación |
|------|--------|-----------------|---------------------|------------|
| F1   | 6      | 0               | 4                   | ~3-4 días  |
| F2   | 4      | 1               | 4                   | ~3-4 días  |
| F3   | 7      | 0               | 7                   | ~4-5 días  |
| F4   | 6      | 1               | 6                   | ~4-5 días  |
| F5   | 7      | 3               | 5                   | ~3-4 días  |
| **Total** | **30** | **5**        | **~12**             | **~17-22 días** |
