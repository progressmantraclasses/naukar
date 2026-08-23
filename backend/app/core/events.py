"""
Event Bus — Redis Pub/Sub + in-process broadcast to WebSocket clients.
All system events flow through here so the UI stays live.
"""
import json
import asyncio
from enum import Enum
from typing import Any, Callable, Dict, List
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import redis.asyncio as aioredis
import structlog

from app.core.config import settings

log = structlog.get_logger()


class EventType(str, Enum):
    # Task lifecycle
    TASK_CREATED = "TASK_CREATED"
    TASK_ANALYZED = "TASK_ANALYZED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_REPLANNED = "TASK_REPLANNED"

    # Workforce
    WORKFORCE_CREATED = "WORKFORCE_CREATED"
    WORKFORCE_ADJUSTED = "WORKFORCE_ADJUSTED"

    # Employee
    EMPLOYEE_CREATED = "EMPLOYEE_CREATED"
    EMPLOYEE_REMOVED = "EMPLOYEE_REMOVED"
    EMPLOYEE_STATUS_CHANGED = "EMPLOYEE_STATUS_CHANGED"
    EMPLOYEE_CREATED_DURING_EXECUTION = "EMPLOYEE_CREATED_DURING_EXECUTION"

    # Step / execution
    TASK_ASSIGNED = "TASK_ASSIGNED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"

    # Model / tool
    LLM_CALLED = "LLM_CALLED"
    LLM_RESPONSE = "LLM_RESPONSE"
    TOOL_CALLED = "TOOL_CALLED"

    # Quality
    QUALITY_CHECKED = "QUALITY_CHECKED"

    # Final
    FINAL_RESULT_READY = "FINAL_RESULT_READY"

    # System
    THINKING = "THINKING"
    LOG = "LOG"

    # Token tracking & web search
    TOKEN_USAGE = "TOKEN_USAGE"
    WEB_SEARCH_RESULT = "WEB_SEARCH_RESULT"
    TASK_TOKEN_SUMMARY = "TASK_TOKEN_SUMMARY"


@dataclass
class Event:
    event_type: EventType
    task_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class EventBus:
    """
    Central event bus.
    - Publishes events to Redis channel (for multi-process scenarios)
    - Broadcasts to in-process WebSocket subscribers
    """

    CHANNEL_PREFIX = "naukar:events:"

    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._ws_subscribers: Dict[str, List[asyncio.Queue]] = {}  # task_id → queues

    async def connect(self):
        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        log.info("event_bus_connected")

    async def disconnect(self):
        if self._redis:
            await self._redis.aclose()

    async def publish(self, event: Event):
        """Emit an event: push to Redis + broadcast in-process."""
        log.debug("event_published", event_type=event.event_type, task_id=event.task_id)

        # In-process WebSocket broadcast
        queues = self._ws_subscribers.get(event.task_id, [])
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

        # Also broadcast to "*" subscribers (global listeners)
        for q in self._ws_subscribers.get("*", []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

        # Redis publish (fire-and-forget)
        if self._redis:
            try:
                channel = f"{self.CHANNEL_PREFIX}{event.task_id}"
                await self._redis.publish(channel, event.to_json())
            except Exception as e:
                log.warning("redis_publish_failed", error=str(e))

    def subscribe(self, task_id: str) -> asyncio.Queue:
        """Register a WebSocket connection to receive events for a task."""
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=500)
        self._ws_subscribers.setdefault(task_id, []).append(q)
        return q

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        queues = self._ws_subscribers.get(task_id, [])
        try:
            queues.remove(queue)
        except ValueError:
            pass


# Global singleton
event_bus = EventBus()
