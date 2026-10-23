"""WebSocket живых событий: /api/live/ws. Протокол и коды закрытия — readme модуля.

Токен — первым сообщением, а не в адресе: адрес вместе с параметрами пишут журналы Traefik и uvicorn.
"""
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from live import hub
from user.auth import get_session_by_token

router = APIRouter()

#: Сколько секунд ждать сообщения с токеном: соединение без входа держит место в лимите Traefik
AUTH_TIMEOUT = 5
#: Закрытие «не вошёл»: токен не пришёл вовремя, негодный или не access. 4000–4999 — коды приложения
CLOSE_UNAUTHORIZED = 4401


@router.websocket("/ws")
async def live_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        user_id = await _authenticate(websocket)
        if user_id is None:
            await websocket.close(CLOSE_UNAUTHORIZED)
            return
        hub.connect(user_id, websocket)
        try:
            await websocket.send_json({"type": "ready"})
            while True:
                if (await _receive(websocket)).get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        finally:
            hub.disconnect(user_id, websocket)
    except WebSocketDisconnect:
        pass  # вкладку закрыли — обычный конец соединения


async def _authenticate(websocket: WebSocket) -> int | None:
    """Пользователь из первого сообщения `{"type": "auth", "token": "<access>"}`; не пришло вовремя или не то — None."""
    try:
        message = await asyncio.wait_for(_receive(websocket), AUTH_TIMEOUT)
    except TimeoutError:
        return None
    token = message.get("token")
    if message.get("type") != "auth" or not isinstance(token, str):
        return None
    session = await get_session_by_token(token, "access")
    return session.user_id if session else None


async def _receive(websocket: WebSocket) -> dict:
    """Следующее сообщение — объект JSON; двоичное, не JSON или не объект — пустой словарь."""
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    try:
        data = json.loads(message.get("text") or "")
    except (ValueError, RecursionError):
        return {}
    return data if isinstance(data, dict) else {}
