from typing import Dict, List, Any
from fastapi import WebSocket
from uuid import UUID

class ConnectionManager:
    def __init__(self):
        # organization_id -> list of WebSockets
        self.active_connections: Dict[UUID, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, organization_id: UUID):
        await websocket.accept()
        if organization_id not in self.active_connections:
            self.active_connections[organization_id] = []
        self.active_connections[organization_id].append(websocket)

    def disconnect(self, websocket: WebSocket, organization_id: UUID):
        if organization_id in self.active_connections:
            self.active_connections[organization_id].remove(websocket)
            if not self.active_connections[organization_id]:
                del self.active_connections[organization_id]

    async def send_personal_message(self, message: Any, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast_to_org(self, organization_id: UUID, message: Any):
        if organization_id in self.active_connections:
            for connection in self.active_connections[organization_id]:
                await connection.send_json(message)

manager = ConnectionManager()
