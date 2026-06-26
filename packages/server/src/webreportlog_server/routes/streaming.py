"""Streaming-related routes for real-time test updates."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from ..database import engine
from ..database import get_session as get_db_session
from ..services.broadcaster import broadcaster
from ..streaming import process_event

router = APIRouter()


class StreamEventRequest(BaseModel):
    """Request model for streaming events."""

    session_id: int | None = None
    event: str  # JSONL line


# Map external session UUIDs to internal database session IDs
session_uuid_map: dict[str, int] = {}


@router.post("/api/stream/event")
async def stream_event(request: Request):
    """Receive a single test event and process it.

    Accepts JSONL line directly as request body (text/plain) or as JSON object.
    Expects X-Session-ID header to identify which session events belong to.
    """
    session_id = None

    # Get session UUID from header
    session_uuid = request.headers.get("x-session-id")

    # Parse request body
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        if isinstance(body, dict) and "event" in body:
            event_line = body["event"]
            session_id = body.get("session_id", session_id)
        else:
            event_line = json.dumps(body)
    else:
        body_bytes = await request.body()
        event_line = body_bytes.decode("utf-8").strip()

    # Look up session ID from UUID if seen before
    if session_uuid and session_uuid in session_uuid_map:
        session_id = session_uuid_map[session_uuid]

    with Session(engine) as db:
        try:
            session, event_type = process_event(event_line, session_id, db)
        except json.JSONDecodeError as e:
            db.rollback()
            raise HTTPException(
                status_code=400, detail=f"Invalid JSON: {str(e)}"
            ) from e
        except ValueError as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Internal server error: {str(e)}"
            ) from e

        if session is None:
            return {"status": "success", "event_type": event_type}
        assert session.id is not None  # a persisted session always has an id

        # Store/clean up UUID→ID mapping
        if session_uuid and event_type == "session_start":
            session_uuid_map[session_uuid] = session.id
        if session_uuid and event_type == "session_finish":
            session_uuid_map.pop(session_uuid, None)

        # Broadcast update to SSE subscribers
        await broadcaster.broadcast(
            session.id,
            {
                "type": event_type,
                "session_id": session.id,
                "session": {
                    "id": session.id,
                    "status": session.status,
                    "total_tests": session.total_tests,
                    "passed": session.passed,
                    "failed": session.failed,
                    "skipped": session.skipped,
                    "xfailed": session.xfailed,
                    "xpassed": session.xpassed,
                    "errors": session.errors,
                    "exitstatus": session.exitstatus,
                },
            },
        )

        return {
            "status": "success",
            "session_id": session.id,
            "event_type": event_type,
            "session": {
                "total_tests": session.total_tests,
                "passed": session.passed,
                "failed": session.failed,
                "skipped": session.skipped,
                "xfailed": session.xfailed,
                "xpassed": session.xpassed,
                "errors": session.errors,
            },
        }


@router.get("/api/stream/{session_id}")
async def stream_session_updates(
    session_id: int, db: Session = Depends(get_db_session)
):
    """Server-Sent Events endpoint for real-time session updates."""

    async def event_generator():
        queue = broadcaster.subscribe(session_id)
        try:
            yield f"data: {json.dumps({'type': 'initial', 'session_id': session_id})}\n\n"

            while True:
                message = await queue.get()
                yield f"data: {json.dumps(message)}\n\n"

                if message.get("type") == "session_finish":
                    break
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
