"""Agent orchestration.

We use a deterministic async DAG rather than a runtime DAG framework for two reasons:
  - the node sequence is fixed (Planner → loop(Executor → Critic) → Synthesizer → MessageGen → Responder),
  - it gives us tight control of SSE streaming.

The LangGraph package is included as a dependency and can host the same nodes via
StateGraph if a richer DAG is needed later; the node functions are pure and reusable.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.agent.nodes.critic import run_critic
from app.agent.nodes.intent import run_intent
from app.agent.nodes.message_generator import run_message_generator
from app.agent.nodes.planner import run_planner
from app.agent.nodes.responder import run_responder
from app.agent.nodes.synthesizer import run_synthesizer
from app.agent.nodes.tool_executor import execute_step
from app.agent.state import AgentState, TraceEvent
from app.observability import get_logger
from app.settings import get_settings

logger = get_logger(__name__)


async def run_agent(state: AgentState) -> AsyncIterator[TraceEvent]:
    """Run the agent and yield TraceEvents as they are produced.

    Consumers (the SSE endpoint) emit each event to the wire immediately, so the
    UI populates the trace pane in real time.
    """
    settings = get_settings()
    state.emit(TraceEvent(event="info", data={"msg": "agent_started", "session": state.session_id}))
    _drain(state)
    async for ev in _yield_drain(state):
        yield ev

    # 0. Intent gate — greetings / small talk get a conversational reply, no pipeline.
    is_task = await run_intent(state)
    async for ev in _yield_drain(state):
        yield ev
    if not is_task:
        await run_responder(state)
        async for ev in _yield_drain(state):
            yield ev
        return

    # 1. Planner
    await run_planner(state)
    async for ev in _yield_drain(state):
        yield ev
    if not state.plan or not state.plan.steps:
        state.error = "Planner produced no steps"
        async for ev in _yield_drain(state):
            yield ev
        return

    # 2. Loop: Tool → Critic
    while state.cursor < len(state.plan.steps) and state.iterations < settings.agent_max_iterations:
        state.iterations += 1
        await execute_step(state, state.cursor)
        async for ev in _yield_drain(state):
            yield ev
        await run_critic(state)
        async for ev in _yield_drain(state):
            yield ev

    # 3. Synthesizer
    await run_synthesizer(state)
    async for ev in _yield_drain(state):
        yield ev

    # 4. MessageGenerator
    await run_message_generator(state)
    async for ev in _yield_drain(state):
        yield ev

    # 5. Responder
    await run_responder(state)
    async for ev in _yield_drain(state):
        yield ev


# -------------------------------------------------------------------
# Internal: incremental event drain
# -------------------------------------------------------------------

def _drain(state: AgentState) -> list[TraceEvent]:
    out = list(state.events)
    state.events.clear()
    return out


async def _yield_drain(state: AgentState):
    for ev in _drain(state):
        yield ev
