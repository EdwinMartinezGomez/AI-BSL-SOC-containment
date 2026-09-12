# -*- coding: utf-8 -*-
"""AI-BSL platform — API FastAPI: ingesta, enforcement, revisiones, ledger, Lab.

Sirve el contrato REST + WebSocket (/ws/events) + SSE (/sse/events) y, si existe
el build del dashboard, lo sirve en '/'. El dashboard consume eventos en vivo y
la cola de revisiones humanas (ceiling/P4).
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Body, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..controller import Platform
from ..seeder import seed_agents
from ..gateway.echo import start_echo_server
from ..gateway.failclosed import FailClosedGuard
from ..policy_store import validate_policy

ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = ROOT / "web" / "dist"
ECHO_PORT = 8099

PLATFORM = Platform()


@asynccontextmanager
async def lifespan(app: FastAPI):
    PLATFORM.hub.bind_loop(asyncio.get_running_loop())
    start_echo_server(ECHO_PORT)
    seeded = seed_agents(PLATFORM)
    app.state.seeded = seeded

    async def _idle_ticker():
        while True:
            await asyncio.sleep(1.0)
            try:
                PLATFORM.tick_all_idle()
            except Exception:  # noqa: BLE001
                pass

    t = asyncio.create_task(_idle_ticker())
    yield
    t.cancel()


app = FastAPI(title="AI-BSL Platform", version="0.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def _err(status: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": detail})


# ---------------------------------------------------------------- health/policy
@app.get("/api/v1/health")
def health():
    return PLATFORM.health()


@app.get("/api/v1/policy")
def policy():
    return {"config": PLATFORM.policy.get(),
            "meta": PLATFORM.policy.to_dict()}


@app.post("/api/v1/policy")
def register_policy(cfg: Dict = Body(...), author: str = "operator", note: str = ""):
    err = validate_policy(cfg)
    if err:
        return _err(422, err)
    version = PLATFORM.policy.register(cfg, author, note)
    return {"version": version, "registered": True}


@app.get("/api/v1/policy_versions")
def policy_versions():
    return PLATFORM.policy.to_dict()


# ---------------------------------------------------------------- agents
@app.post("/api/v1/agents")
def create_agent(name: str = Body(...), profile: str = Body("med"),
                 mode: str = Body("live")):
    try:
        return PLATFORM.register_agent(name, profile, mode)
    except ValueError as e:
        return _err(422, str(e))


@app.get("/api/v1/agents")
def list_agents():
    return {"agents": PLATFORM.list_agents()}


@app.get("/api/v1/agents/{agent_id}")
def get_agent(agent_id: str):
    try:
        return PLATFORM.get_agent(agent_id, include_history=True)
    except KeyError as e:
        return _err(404, str(e))


@app.post("/api/v1/agents/{agent_id}/events")
def inject_events(agent_id: str, events: List[dict] = Body(...)):
    try:
        return PLATFORM.inject_events(agent_id, events)
    except KeyError as e:
        return _err(404, str(e))


@app.post("/api/v1/agents/{agent_id}/actions/preexec")
def preexec(agent_id: str, req: dict = Body(...)):
    """Gate del agente controlado: ALLOW/BLOCK/HOLD_REVIEW ANTES de ejecutar."""
    try:
        return PLATFORM.preexec_action(agent_id, req)
    except KeyError as e:
        return _err(404, str(e))


@app.post("/api/v1/agents/{agent_id}/actions/result")
def action_result(agent_id: str, res: dict = Body(...)):
    """Telemetria post-ejecucion: si el runtime reporto una divergencia real,
    se ingesta como senal observada (p.ej. exec_layer_divergence)."""
    try:
        rt = PLATFORM._require(agent_id)
        sig = res.get("signal_hint") or res.get("signal")
        if sig:
            return rt.ingest([{"kind": sig, "target": res.get("target", ""),
                               "detail": {"action_id": res.get("action_id")}}],
                             source="api_result")
        return {"ok": True, "ingested": False}
    except KeyError as e:
        return _err(404, str(e))


@app.get("/api/v1/agents/{agent_id}/history")
def agent_history(agent_id: str):
    try:
        snap = PLATFORM.get_agent(agent_id, include_history=True)
        return {"posture_history": snap.get("posture_history", []),
                "transitions": snap.get("transitions", []),
                "events": snap.get("events", [])}
    except KeyError as e:
        return _err(404, str(e))


@app.get("/api/v1/agents/{agent_id}/events")
def agent_events(agent_id: str, limit: int = 200):
    return {"events": PLATFORM.db.events(agent_id, limit)}


@app.get("/api/v1/agents/{agent_id}/ledger")
def agent_ledger(agent_id: str):
    try:
        entries = PLATFORM.db.ledger_entries(agent_id)
        rt = PLATFORM.runtimes.get(agent_id)
        extend = {}
        if rt is not None:
            extend = {"count": rt.ledger.count(),
                      "final_hash": rt.ledger.final_hash(),
                      "verify_ok": rt.ledger_verify_ok(),
                      "mirror_len": len(rt.ledger.outer_mirror())}
        return {"agent_id": agent_id, "entries": entries, **extend}
    except KeyError:
        return _err(404, "agente no encontrado")


@app.post("/api/v1/agents/{agent_id}/ledger/verify")
def verify_ledger(agent_id: str):
    try:
        bad = PLATFORM.db.ledger_verify(agent_id)
        return {"ok": len(bad) == 0, "bad_seqs": bad,
                "count": len(PLATFORM.db.ledger_entries(agent_id))}
    except KeyError:
        return _err(404, "agente no encontrado")


@app.get("/api/v1/agents/{agent_id}/reviews")
def list_reviews(agent_id: str, status: str = "open"):
    return {"reviews": PLATFORM.db.reviews(agent_id, status)}


@app.post("/api/v1/agents/{agent_id}/reviews/{review_id}/decide")
def decide_review(agent_id: str, review_id: str,
                  decision: str = Body(...), by: str = Body("operator"),
                  note: str = Body("")):
    if decision not in ("approve", "deny"):
        return _err(422, "decision debe ser approve|deny")
    try:
        return PLATFORM.decide_review(agent_id, review_id, decision, by, note)
    except KeyError as e:
        return _err(404, str(e))


@app.post("/api/v1/agents/{agent_id}/offline")
def set_offline(agent_id: str, body: dict = Body(default={})):
    """Simula la perdida del canal de control (fail-closed test). body: {offline: bool}."""
    offline = body.get("offline", True) if isinstance(body, dict) else bool(body)
    try:
        return PLATFORM.set_offline(agent_id, offline)
    except KeyError as e:
        return _err(404, str(e))


@app.get("/api/v1/agents/{agent_id}/metrics")
def agent_metrics(agent_id: str):
    try:
        return PLATFORM.metrics(agent_id)
    except KeyError as e:
        return _err(404, str(e))


# ---------------------------------------------------------------- Lab
@app.get("/api/v1/scenarios")
def list_scenarios():
    return {"scenarios": PLATFORM.list_scenarios()}


@app.post("/api/v1/scenarios/{scenario_id}/run")
def run_scenario(scenario_id: str):
    try:
        return PLATFORM.run_lab(scenario_id)
    except KeyError as e:
        return _err(404, str(e))


# ---------------------------------------------------------------- streaming
@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await ws.accept()
    PLATFORM.hub.register_ws(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        PLATFORM.hub.unregister_ws(ws)


@app.get("/sse/events")
async def sse_events(request: Request, agent_id: Optional[str] = None):
    q = PLATFORM.hub.add_sse()

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                line = await q.get()
                if agent_id:
                    try:
                        msg = json.loads(line[len("data: "):])
                        if msg.get("agent_id") != agent_id:
                            continue
                    except Exception:  # noqa: BLE001
                        continue
                yield line
        finally:
            PLATFORM.hub.remove_sse(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------------------------------------------------------- frontend
if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()