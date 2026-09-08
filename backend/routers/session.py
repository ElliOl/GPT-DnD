"""
The multi-agent turn endpoint.

Deliberately separate from ``/api/action``, which still runs the legacy DM agent.
Both work; this one goes through the state machine in ``orchestrator/turn_loop``
and can be pointed at any module.

    POST /api/session                      -> create a campaign from a module
    POST /api/session/{id}/action          -> take a turn
    GET  /api/session/modules              -> what modules are installed
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.content.module import Module, ModuleError, available_modules
from backend.content.schema import validate_path
from backend.orchestrator.turn_loop import TurnLoop
from backend.state.db import session_scope
from backend.state.models import Campaign

router = APIRouter(prefix="/api/session", tags=["session"])

#: One loop per campaign, holding its module and its session budget.
_loops: dict[str, TurnLoop] = {}


def _ai_client():
    from backend.routers.dependencies import dm_agent

    if dm_agent is None or dm_agent.ai_client is None:
        raise HTTPException(status_code=503, detail="AI client not initialized")
    return dm_agent.ai_client


def get_loop(campaign_id: str) -> TurnLoop:
    """Build (and cache) the loop for a campaign, loading its module by id."""
    if campaign_id in _loops:
        return _loops[campaign_id]

    with session_scope() as session:
        campaign = session.get(Campaign, campaign_id)
        if campaign is None:
            raise HTTPException(status_code=404, detail=f"No campaign {campaign_id!r}")
        module_id = campaign.adventure_id
        module_path = campaign.module_path

    # The recorded path wins so a module outside the search paths still loads,
    # but a moved module falls back to its id rather than bricking the campaign.
    module = None
    errors: list[str] = []
    for ref in (module_path, module_id):
        if not ref:
            continue
        try:
            module = Module.load(ref, campaign_id=campaign_id)
            break
        except ModuleError as exc:
            errors.append(str(exc))
    if module is None:
        raise HTTPException(status_code=500, detail="\n".join(errors) or "module not found")

    _loops[campaign_id] = TurnLoop(_ai_client(), module)
    return _loops[campaign_id]


def forget_loop(campaign_id: str) -> None:
    """Drop the cached loop — call after generated content lands or a rewind."""
    _loops.pop(campaign_id, None)


class CreateSessionRequest(BaseModel):
    module: str = Field(..., description="module id, or a path to a module directory")
    campaign_id: str | None = None
    party_dir: str | None = Field(None, description="directory of PC sheets")


@router.get("/modules")
async def list_modules() -> list[dict[str, Any]]:
    """Every installed module, with whether it currently validates."""
    out = []
    for entry in available_modules():
        from pathlib import Path

        report = validate_path(Path(entry["path"]))
        out.append({**entry, "valid": report.ok, "errors": report.errors,
                    "warnings": report.warnings})
    return out


@router.post("")
async def create_session(request: CreateSessionRequest) -> dict[str, Any]:
    """Seed a campaign from any module that satisfies the contract."""
    from pathlib import Path

    from scripts.migrate_state import DEFAULT_PARTY_DIR, migrate

    campaign_id = request.campaign_id or request.module.rstrip("/").split("/")[-1]
    party = Path(request.party_dir) if request.party_dir else DEFAULT_PARTY_DIR
    try:
        payload = migrate(request.module, campaign_id, party_dir=party)
    except SystemExit as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ModuleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    forget_loop(campaign_id)
    return {
        "campaign_id": campaign_id,
        "module": payload["campaign"]["adventure_id"],
        "name": payload["campaign"]["name"],
        "seeded": {k: len(v) for k, v in payload.items() if isinstance(v, list)},
    }


class ActionRequest(BaseModel):
    message: str
    actor_id: str | None = None


@router.post("/{campaign_id}/action")
async def take_turn(campaign_id: str, request: ActionRequest) -> dict[str, Any]:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    loop = get_loop(campaign_id)
    try:
        result = await loop.take_turn(
            campaign_id, request.message, actor_id=request.actor_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.to_dict()
