from fastapi import APIRouter, HTTPException
from app.trading_engine.engine import engine
from app.models import AgentState
from typing import List
import asyncio

router = APIRouter()


@router.on_event("startup")
async def startup_event():
    # Start the trading loop in the background
    asyncio.create_task(engine.run_trading_loop())


@router.on_event("shutdown")
def shutdown_event():
    engine.stop_trading_loop()


@router.get("/agents", response_model=List[AgentState])
async def get_agents():
    """
    Get the current state of all trading agents.
    """
    return await engine.get_all_agent_states()


@router.get("/agents/{agent_id}", response_model=AgentState)
async def get_agent(agent_id: str):
    """
    Get the state of a specific agent by its ID.
    """
    for agent_state in await engine.get_all_agent_states():
        if agent_state.agent_id == agent_id:
            return agent_state
    raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/engine/status")
async def get_engine_status():
    """
    Get the status of the trading engine.
    """
    return {"is_running": engine.is_running}
