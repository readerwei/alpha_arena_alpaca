import asyncio
from app.trading_engine.agent import Agent
from app.llm.mock_provider import MockLLMProvider
from app.llm.ollama_provider import OllamaProvider
from app.config import settings


class TradingEngine:
    def __init__(self):
        self.agents: list[Agent] = []
        self._initialize_agents()
        self.is_running = False

    def _initialize_agents(self):
        """
        Initializes the trading agents based on the configuration.
        """
        if settings.LLM_PROVIDER == "ollama":
            print(
                f"Using Ollama provider with model {settings.OLLAMA_MODEL} at {settings.OLLAMA_URL}"
            )
            llm_provider = OllamaProvider(
                model_name=settings.OLLAMA_MODEL, url=settings.OLLAMA_URL
            )
            # Create one agent for the specified Ollama model
            agent = Agent(
                agent_id=f"ollama-{settings.OLLAMA_MODEL.replace(':', '-')}",
                name=f"Ollama ({settings.OLLAMA_MODEL})",
                llm_provider=llm_provider,
            )
            self.agents = [agent]
        else:  # Default to mock provider
            print("Using Mock LLM provider.")
            agent1 = Agent(
                agent_id="mock-gpt5",
                name="Mock GPT-5",
                llm_provider=MockLLMProvider(model_name="gpt-5-mock"),
            )
            agent2 = Agent(
                agent_id="mock-gemini",
                name="Mock Gemini 2.5",
                llm_provider=MockLLMProvider(model_name="gemini-2.5-pro-mock"),
            )
            self.agents = [agent1, agent2]

        print(f"Initialized {len(self.agents)} agent(s).")

    async def _run_agent_cycle(self, agent: Agent):
        try:
            await agent.decide_and_trade()
        except Exception as e:
            print(f"Error during trading cycle for agent {agent.name}: {e}")

    async def run_trading_loop(self):
        """
        The main trading loop that runs periodically.
        """
        self.is_running = True
        print("Trading engine started. Running trading loop...")
        while self.is_running:
            print(
                f"--- New trading cycle started at {asyncio.get_event_loop().time():.2f} ---"
            )

            # Run all agents concurrently
            await asyncio.gather(
                *(self._run_agent_cycle(agent) for agent in self.agents)
            )

            await asyncio.sleep(settings.LOOP_INTERVAL_SECONDS)

    def stop_trading_loop(self):
        """
        Stops the trading loop.
        """
        self.is_running = False
        print("Stopping trading engine...")

    async def get_all_agent_states(self):
        """
        Returns the state of all agents.
        """
        return [await agent.get_state() for agent in self.agents]


# Global engine instance
engine = TradingEngine()
