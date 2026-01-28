"""Streaming-related routes for real-time test updates."""
import json
import asyncio
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session

from ..database import get_session as get_db_session
from ..models import Session as TestSession
from ..streaming import process_event
from ..services.broadcaster import broadcaster

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

    This endpoint allows remote test runners to send events as they happen.
    Accepts JSONL line directly as request body (text/plain) or as JSON object.
    Expects X-Session-ID header to identify which session events belong to.
    """
    session_id = None
    db = None
    try:
        # Get database session
        db_gen = get_db_session()
        db = next(db_gen)

        # Get session UUID from header
        session_uuid = request.headers.get("x-session-id")

        # Try to parse as JSON first (for API clients sending structured data)
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict) and "event" in body:
                # Structured format: {"session_id": ..., "event": "..."}
                event_line = body["event"]
                session_id = body.get("session_id", session_id)
            else:
                # Assume the JSON itself is the event
                event_line = json.dumps(body)
        else:
            # Plain text format - JSONL line directly in body
            body_bytes = await request.body()
            event_line = body_bytes.decode("utf-8").strip()

        # Look up session ID from UUID if we've seen this session before
        if session_uuid and session_uuid in session_uuid_map:
            session_id = session_uuid_map[session_uuid]

        session, event_type = process_event(event_line, session_id, db)

        # Store the mapping for new sessions
        if session_uuid and event_type == "session_start":
            session_uuid_map[session_uuid] = session.id

        # Clean up mapping when session finishes
        if session_uuid and event_type == "session_finish":
            if session_uuid in session_uuid_map:
                del session_uuid_map[session_uuid]

        # Broadcast update to SSE subscribers
        await broadcaster.broadcast(session.id, {
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
            }
        })

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
            }
        }
    except json.JSONDecodeError as e:
        if db:
            db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except ValueError as e:
        if db:
            db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if db:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        if db:
            try:
                next(db_gen, None)  # Close the generator
            except StopIteration:
                pass


@router.get("/api/stream/{session_id}")
async def stream_session_updates(session_id: int, db: Session = Depends(get_db_session)):
    """Server-Sent Events endpoint for real-time session updates.

    Clients can subscribe to this endpoint to receive live updates as tests run.
    Clients can subscribe before the session is created for real-time monitoring.
    """
    async def event_generator():
        queue = broadcaster.subscribe(session_id)
        try:
            # Send initial session state
            yield f"data: {json.dumps({'type': 'initial', 'session_id': session_id})}\n\n"

            # Stream updates
            while True:
                message = await queue.get()
                yield f"data: {json.dumps(message)}\n\n"

                # Stop streaming when session completes
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
            "X-Accel-Buffering": "no"
        }
    )
