"""
WebSocket endpoint — streams live events to the Electron frontend.
Clients subscribe to a task_id and receive all events as JSON.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.events import event_bus, Event
import structlog

log = structlog.get_logger()
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{task_id}")
async def task_websocket(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for a specific task.
    Streams all events for that task in real-time.
    Connect as: ws://localhost:8000/ws/{task_id}
    """
    await websocket.accept()
    queue = event_bus.subscribe(task_id)
    log.info("ws_client_connected", task_id=task_id)

    try:
        # Send a welcome message
        await websocket.send_json({
            "event_type": "CONNECTED",
            "task_id": task_id,
            "message": "Connected to Naukar event stream",
        })

        while True:
            try:
                # Wait for event with timeout (for heartbeat)
                event: Event = await asyncio.wait_for(
                    queue.get(), timeout=30.0
                )
                await websocket.send_json(event.to_dict())

                # If final result is ready, close gracefully after sending
                if event.event_type.value in ("FINAL_RESULT_READY", "TASK_FAILED"):
                    await asyncio.sleep(0.1)  # ensure message sent
                    break

            except asyncio.TimeoutError:
                # Heartbeat
                try:
                    await websocket.send_json({"event_type": "HEARTBEAT", "task_id": task_id})
                except Exception:
                    break

    except WebSocketDisconnect:
        log.info("ws_client_disconnected", task_id=task_id)
    finally:
        event_bus.unsubscribe(task_id, queue)


@router.websocket("/ws")
async def global_websocket(websocket: WebSocket):
    """
    Global WebSocket — receives events for ALL tasks.
    Used by the frontend dashboard.
    """
    await websocket.accept()
    queue = event_bus.subscribe("*")
    log.info("ws_global_client_connected")

    try:
        await websocket.send_json({
            "event_type": "CONNECTED",
            "task_id": "*",
            "message": "Connected to Naukar global event stream",
        })

        while True:
            try:
                event: Event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(event.to_dict())
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"event_type": "HEARTBEAT"})
                except Exception:
                    break

    except WebSocketDisconnect:
        log.info("ws_global_client_disconnected")
    finally:
        event_bus.unsubscribe("*", queue)
