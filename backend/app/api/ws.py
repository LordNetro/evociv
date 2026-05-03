import logging
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Any

logger = logging.getLogger("evociv.ws")

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.latest_snapshot: dict | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]):
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()


def command_dispatcher(msg: dict, engine) -> None:
    """Dispatch a WebSocket command message to the simulation engine.

    Non-blocking, synchronous dispatch. Validates command type and agent_id
    before enqueuing to engine.command_queue.
    """
    ALLOWED_COMMANDS = {"move_to", "do_action", "set_plan", "inject_thought", "release", "release_all"}
    payload = msg.get("payload", {})
    command_type = payload.get("type", "")
    agent_id = payload.get("agent_id", "")
    cmd_payload = payload.get("payload", {})

    if command_type not in ALLOWED_COMMANDS:
        logger.warning(f"Unknown command type: {command_type}")
        return

    # release_all doesn't need an agent_id
    if command_type != "release_all":
        if not agent_id:
            logger.warning("command missing agent_id")
            return
        if not hasattr(engine, 'agents'):
            logger.warning("engine has no agents attribute")
            return
        if agent_id not in {a.id for a in engine.agents}:
            logger.warning(f"Unknown agent_id: {agent_id}")
            return

    if command_type == "release_all":
        engine.command_queue.clear()
        engine.director_mode = False
    else:
        # Auto-enable director mode on first command (R1.2)
        if not engine.director_mode:
            engine.command_queue.clear()  # R1.3: clear stale entries
            engine.director_mode = True
        engine.command_queue[agent_id] = {
            "type": command_type,
            "payload": cmd_payload,
        }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    # Send initial full snapshot if available
    if manager.latest_snapshot:
        try:
            await websocket.send_json({
                "type": "full_snapshot",
                "payload": manager.latest_snapshot,
            })
        except Exception:
            pass  # Non-critical — client will catch up via deltas

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "command":
                engine = websocket.app.state.engine
                command_dispatcher(data, engine)
            # Other message types pass through (placeholder for future)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
