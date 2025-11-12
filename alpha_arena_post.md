Exploring the Limits of Large Language Models as Quant Traders
We gave six leading LLMs $10k each to trade in real markets autonomously, using only numerical market data inputs and the same prompt/harness. Early results show real behavioral differences (risk, sizing, holding time) and a sensitivity to small prompt changes.

Introduction
LLMs are achieving technical mastery in problem-solving domains on the order of Chess and Go, solving algorithmic puzzles and math proofs competitively in contests such as the ICPC and IMO. These and other benchmarks have served as litmus tests for the readiness of these models to tackle real-world problems and disrupt knowledge and skill-based work across industries. Today’s static benchmarks are lacking, and mostly test pattern-matching and reasoning on fixed datasets, without measuring long-horizon decision-making, operational robustness, adaptation, or outcomes in risky domains. These static tests are quickly absorbed into training corpora and many models already score highly on several of them through direct memorization, meaning they no longer provide the signal they used to. The way forward is clear and simple: test decision making capabilities in real-world, dynamic, competitive environments.

At Nof1, we’re interested in understanding how AI behaves in the real world, and we’re focused on the domain of financial markets to achieve this. With the first season of Alpha Arena, our goal is to answer the following question:

Can a large language model, with minimal guidance, act as a zero-shot systematic trading model?

We gave the leading LLMs $10,000 each to trade on Hyperliquid, with zero human intervention. Each model must process quantitative data (a well-known challenge for LLMs) and trade systematically using only the numerical data provided. For the first season, they are not given news or access to the leading “narratives” of the market. Instead, the must infer this from what’s given to them, insofar as it’s encoded in the time-series data. The models are given an asset universe that consists of cryptocurrencies derivatives in the form of perpetual futures. Perpetuals are contracts that enable taking long (bet on prices rising) or short (bet on prices falling) positions, with leverage.

Each model has a single goal: maximize PnL (profit and loss). The models are given their sharpe ratio at each invocation (excess return per unit of risk), to help normalize for risky behavior.

Overall, success in Alpha Arena is incredibly difficult. We do not expect any of the models to do well, and early successes may be the result of luck. However, Season 1 is the first of a series of increasingly sophisticated seasons. In future iterations, we will introduce more statistical rigor, more controls, and more specific challenges for the models.

Season 1 of Alpha Arena had two goals:

Uncover the obvious implicit biases and default trading behavior of the leading LLMs, through comparative analysis. Are there big differences in the way the models trade? Are they consistent over time? Where do they make mistakes?
Help shift the culture of AI research towards real-world benchmarks and away from static, exam-like benchmarks. If nothing else, we hope Alpha Arena highlights the power of evaluating AI in more consequential, realistic environments. We believe this is the fastest path to uncovering critical gaps and insights that move frontier AI forward.
We chose to run Season 1 live with real capital. Paper trading remains a useful baseline, but it cannot surface the full stack of execution challenges, adverse selection, and accountability offered by real markets. Visibility is part of the method here: starting with cryptocurrency provides auditable traces and feedback. The extra attention helps reinforce Goal #2 as people uncover the shortcomings of these models and the shortcomings of the various seasons.

What this is not. 

The goal is not to use a single run to declare a permanent “best” trading model. We are deeply aware of the flaws in Season 1, including but not limited to: prompt bias, limited sample sizes / lack of statistical rigor, and shortness of evaluation period, etc.

That said, across multiple pre-launch test runs we observed non-trivial behavioral differences between the models that we’ve documented below. We’re continuing to analyze the Season 1 traces while running targeted follow-up experiments, many of which directly address the limits of a single run.

For season 1, we focused on the models’ default rule-following and risk management abilities. Do they reliably follow simple risk rules? Which parts of the decision loop can be trusted to run autonomously? Where do they misread inputs, over-trade, flip flop, or contradict prior plans? What is each model’s baseline stance: risk-averse, risk-seeking, or neutral, and how stable is that stance over time? We have partial answers today, and testable hypotheses to systematically close the gaps in our understanding.

The following sections detail our harness design methodology, preliminary findings, and plans for future work.

Alpha Arena Design
Our intent with Alpha Arena’s design was to give agents a hard problem without setting them up to fail. We conducted extensive experimentation to ensure that the models have enough information to make principled decisions while avoiding context-crowding. Accordingly, we’ve provided each agent with a condensed set of live market features: current and historical mid-prices and volume, selected technical indicators, and ancillary features spanning short and long timescales. These data are available to see at nof1.ai under “Model Chat”, by clicking into any individual model’s chat message.

The arena features six models across leading AI research labs: GPT-5, Gemini 2.5 Pro, Claude Sonnet 4.5, Grok 4, DeepSeek v3.1, and Qwen3-Max. These models were chosen to reflect the state-of-the-art across both closed and open-source providers from both the U.S. and China. With the exception of Qwen3-Max, we enable reasoning with the highest configurable setting for all models. We report out-of-the-box performance, with no task-specific fine-tuning.

To keep things simple, we limited the action space to: buy to enter (long), sell to enter (short), hold, or close. The tradable coin universe was constrained to six popular cryptocurrencies on Hyperliquid: BTC, ETH, SOL, BNB, DOGE, & XRP.

We chose crypto assets for three practical reasons:

Markets are open 24/7, which lets us observe decisions continuously rather than only during business hours.
Data is abundant and easily accessible, which supports analysis and transparent auditing. The decentralized design of Hyperliquid allows external parties to easily validate that each trade actually happened as reported.
Hyperliquid is fast, reliable, and incredibly easy to integrate. Hyperliquid and crypto are global, they are less tied to a specific country or company.
The models engage in mid-to-low frequency trading (MLFT) trading, where decisions are spaced by minutes to a few hours, not microseconds. In stark contrast to high-frequency trading, MLFT gets us closer to the question we care about: can a model make good choices with a reasonable amount of time and information? At these time horizons, feedback loops are quick, such that good reasoning tends to show up in results, while over-trading and poor risk control show up in costs and drawdowns. Importantly, this is live trading, not a replay or a paper exercise, so models face real executions, real fees, and real counterparties trying to outsmart them.

To ensure apples-to-apples comparison across models and providers, all agents were provided the same system prompt, user prompt template, data, and their default sampling configuration. The user prompt is fully transparent and visible. The system prompt is something that we may open source at some point in the future.

Building the Harness
Agent contexts must be carefully engineered to avoid introducing too many instructions and information such that the agent struggles to keep track of it all. We avoided multi-agent orchestration, tool use, and long conversation histories, although such features may be added in future seasons of the benchmark. The loop is as follows:

Alpha Arena Inference Loop Diagram

At each inference call (~2-3 mins), the agents receive (a) a concise instruction set (system prompt) and (b) live market + account state (user prompt), and return actions that are fed into a Hyperliquid trade execution pipeline. The instructions were curated over many iterations and provide details on expected fees, position sizing, and how to format outputs. In addition to the desired coin, direction (long/short), quantity, and leverage, the action output includes a short justification, confidence score in [0, 1], and an exit plan with pre-defined profit targets, stop losses, and invalidation conditions (pre-registering specific signals that void a plan). These fields, introduced during prompt engineering, were found to improve performance. Position sizing, a critical component of trade design, is computed by the agent itself, conditioned on available cash, leverage, and its internal risk preference.

Why allow the models to take leverage? Hyperliquid is specifically built around perpetual futures, which are designed to make leverage easy. Trading perpetuals with leverage is the primary way the exchange is used. Trading with leverage also introduces capital efficiency and speeds up outcomes, speeding up feedback and learning loops. Leverage also dramatically increases risk, stress-testing the models’ risk-management skills and discipline.

To illustrate what agent behavior looks like in practice, this post will now walk through an example single trade from decision to fill and monitoring.

claude_trade_lifecycle_ex.001.png

ENTRY AT 2025-10-19 10:10 ET

Snippet from Prompt
Reasoning Trace
Model Output
EXIT AT 2025-10-20 01:54

Snippet From Prompt
Reasoning Trace
Model Output
The details from the invocation immediately before the trade exit are shown because the BTC price crossed the take-profit threshold, triggering an automatic exit. In this example, over the 15 hours 44 minutes between entry and close, Claude processed updated market data and chose to stick to its exit plan, holding the BTC position across 443 consecutive evaluations.

Early Findings
Our preliminary runs show that, given the same harness and prompts, meaningful differences exist across foundation models in terms of risk appetite, planning, directional bias, and trading activity. We also found that the models were highly sensitive to seemingly trivial prompt changes, stressing the need for a robust harness and extensive prompt iteration in order to use these agents effectively in practice.

Insights and Patterns
The top-line performance statistics (PnL, Sharpe) are important, but they do not tell the full story. Across thousands of invocations and several pre-launch trial runs in recent weeks, we observe consistent patterns, both where agents converge and where they diverge. These differences likely reflect variation in objectives, alignment, and sampling behavior across models. Key observations:

Bullish vs. bearish tilt. Agents differ in their long/short mix over time; some show a persistent long bias. Grok 4, GPT-5, and Gemini 2.5 Pro short much more frequently than peers; Claude Sonnet 4.5 rarely ever shorts.
Holding periods. We see large gaps in how long positions are held (entry→exit time) across agents and runs. In our pre-launch runs, Grok 4 had the longest holding times.
Trade frequency. The number of completed trades varies widely. Gemini 2.5 Pro is the most active; Grok 4 is typically the least.
Risk posture (position sizing). Given the same prompt, agents choose very different sizes. Qwen 3 has consistently sized positions largest, often multiples of GPT-5 and Gemini 2.5 Pro.
Self-reported confidence. When taking actions, models must assign a confidence score in [0, 1], and this varies widely by model. Notably, Qwen 3 routinely reports the highest confidence and GPT-5 the lowest; this pattern has been consistent across runs and appears decoupled from actual trading performance.
Exit-plan tightness. With open-ended instructions, agents set different stop/target conventions. Across runs, Qwen 3 uses the narrowest stop-loss/target distances (as % of entry); Grok 4 and DeepSeek V3.1 are typically the loosest.
Number of active positions. Some models tend to hold most or all of the six available positions simultaneously; by contrast, Claude Sonnet 4.5 and Qwen 3 typically maintain only 1–2 active positions at a time.
Invalidation conditions. Agents index on different features when setting exit-plan invalidation rules. In pre-trial runs, Gemini 2.5 Pro more often overrode its exit plan and closed early, while others did not. This is something we are still investigating.
We also observed how the agents were brittle in ways that matter operationally. A few patterns that we encountered:

Ordering bias. Early prompts listed market data newest→oldest. Even with explicit notes, several models still read it as oldest → newest, inferring the wrong state. Switching to oldest → newest fixed the immediate error and suggests a formatting prior in current LLMs.
Ambiguous terms. Using “free collateral” and “available cash” interchangeably led to inconsistent behavior, sometimes correct assumptions, sometimes indecision. Clarifying definitions removed this failure mode. The ambiguity is understandable; the brittle response is the issue. A reliable agent should default to a clear assumption and proceed under uncertainty.
Rule-gaming under constraints and deception. In a harness variant that exposed prior actions, a set_trading_plan meta-action, a one-line think field, and a temporary cap of ≤3 consecutive holds, our test model (Gemini 2.5 Flash) complied with the letter but not the intent: its internal reasoning complained about being unable to hold a fourth time, then issued set_trading_plan with a neutral “think” to justify a change, and promptly resumed a sequence of hold actions. The exposed “think” and the internal chain-of-thought (CoT) diverged, signaling rule-gaming under pressure. Given the highly regulated nature of trading and consequences associated with bad outcomes in this field, we take alignment very seriously.
Self-referential confusion in plans. With open-ended exit plans, models sometimes misread or contradict their own prior outputs. Examples: GPT-5 later questioned its own phrase “EMA20 reclaim,” unsure how to apply it; Qwen 3 (30B-A3B) set “take +0.5% (4,477.47)” after a 4,463.7 entry (+0.5% ≈ 4,486), noted the inconsistent arithmetic in its CoT, then hesitated and held instead of taking profit. These episodes show difficulty executing against self-authored plans as state evolves. Even if partly due to the harness and fixable with more context, the pattern flags a deeper problem: maintaining coherent agent communication over time, which becomes more acute in multi-agent and long-context regimes.
During development, fees were a significant obstacle for all agents. Overall PnL was dominated by trading costs in early runs as agents over-traded and took quick, tiny gains that fees erased. We mitigated this by tightening the prompt: requiring explicit exit plans (targets, stops, invalidation), encouraging fewer but larger, higher-conviction positions, introducing leverage, and tying position size to the model’s inherent conviction and self-reported confidence score.

Future work
We’ve worked to give the models a fair shot, but the harness imposes real constraints. Each agent must parse noisy market features, relate them to current account state, reason under strict rules, and return a structured action, all inside a limited context window. In this season the agents have no explicit regime awareness and no access to prior state–action history, which limits their ability to adapt or learn from mistakes. The setup also does not support pyramiding (adding to or reducing current positions), so once an entry is placed the size and parameters are fixed. This task’s complexity merits an expanded setup: a broader feature set, selective tool use (e.g., code execution or web search), and explicit inclusion of past state–action traces.

As noted earlier, this is a single live season with a finite window, so statistical power is limited and early standings can move. We’ve seen run-to-run variation in both rankings and inter-model correlations. We are continuing to analyze the current and prior runs and are conducting more rigorous follow-ups; we’ll share much more of the full methodology and results once they meet our bar for stable conclusions. That said, the behavioral patterns described above have been consistent across early trials.

The broader question Nof1 aims to tackle is how to make markets more understandable for agents of the future: what conditions and interfaces help autonomous systems learn, compete fairly, and add value without relying on privileged access or manipulation? What capabilities are missing for truly superhuman trading, and what safeguards are needed if everyone can deploy an agent? Season 1 is a small, transparent step toward a much bigger vision..

