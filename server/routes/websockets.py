from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from ..services.websocket_manager import manager
from ..dependencies import get_ws_auth_context, get_db
from sqlalchemy.orm import Session
from ..schemas import AuthContext
from typing import Optional

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    # Authenticate
    auth: Optional[AuthContext] = await get_ws_auth_context(token, db)
    if auth is None:
        await websocket.accept()
        await websocket.send_json({"error": "Unauthorized"})
        await websocket.close(code=1008)
        return

    # Connect to manager
    await manager.connect(websocket, auth.organization_id)
    
    try:
        while True:
            # Handle incoming messages if needed
            data = await websocket.receive_json()
            # For now, just echo or ignore as the user primarily wanted to "send appropriate data"
            # But we can handle heartbeats or simple commands here
            await manager.send_personal_message(
                {"event": "ack", "payload": {"message": "received", "data": data}}, 
                websocket
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket, auth.organization_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, auth.organization_id)
