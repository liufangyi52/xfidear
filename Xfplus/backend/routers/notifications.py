import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status

from backend.models import NotificationTestRequest, UserPublic
from backend.permissions import require_admin_role
from backend.services.auth_service import current_user, get_user_for_token
from backend.services.notification_service import reserve_sms_notification
from backend.services.realtime_service import notification_hub

router = APIRouter(prefix="/api", tags=["notifications"])


@router.post("/notifications/test")
def test_notification(payload: NotificationTestRequest, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    return {
        "success": True,
        "message": "短信通道已预留，v1 仅记录日志，不真实发送。",
        "record": reserve_sms_notification(payload),
    }


@router.websocket("/ws/notifications")
async def notifications_socket(websocket: WebSocket, token: str = Query(default="")):
    user = get_user_for_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await notification_hub.connect(user, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}, ensure_ascii=False))
    except WebSocketDisconnect:
        pass
    finally:
        notification_hub.disconnect(user, websocket)
