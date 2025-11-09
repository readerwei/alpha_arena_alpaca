import asyncio
from app.trading_engine.engine import TradingEngine

async def run_one_cycle():
    """
    Initializes the engine and runs the trading logic for a single cycle.
    """
    print("--- Initializing Trading Engine for a single debug cycle ---")
    # The engine initializes agents upon creation
    engine = TradingEngine()
    
    print(f"\n--- Starting single trading cycle for {len(engine.agents)} agent(s) ---")
    
    async def _run_agent_cycle(agent):
        try:
            # This is the core logic of the loop
            print(f"\n--- Deciding for agent: {agent.name} ---")
            await agent.decide_and_trade()
        except Exception as e:
            print(f"Error during trading cycle for agent {agent.name}: {e}")

    await asyncio.gather(*(_run_agent_cycle(agent) for agent in engine.agents))

    print("\n--- Single trading cycle finished ---")

if __name__ == "__main__":
    # This allows running the async function from a synchronous script
    asyncio.run(run_one_cycle())

