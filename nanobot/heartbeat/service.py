"""Heartbeat service - periodic agent wake-up to check for tasks."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider

_TRIAGE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "classify_task",
            "description": "Classify the complexity of the pending tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "complexity": {
                        "type": "string",
                        "enum": ["simple", "complex"],
                        "description": (
                            "simple = short, self-contained task a lightweight local model can handle; "
                            "complex = multi-step planning, coding, or research requiring a capable model"
                        ),
                    },
                },
                "required": ["complexity"],
            },
        },
    }
]

_HEARTBEAT_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "heartbeat",
            "description": "Report heartbeat decision after reviewing tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["skip", "run"],
                        "description": "skip = nothing to do, run = has active tasks",
                    },
                    "tasks": {
                        "type": "string",
                        "description": "Natural-language summary of active tasks (required for run)",
                    },
                },
                "required": ["action"],
            },
        },
    }
]


class HeartbeatService:
    """
    Periodic heartbeat service that wakes the agent to check for tasks.

    Phase 1 (decision): reads HEARTBEAT.md and asks the LLM — via a virtual
    tool call — whether there are active tasks.  This avoids free-text parsing
    and the unreliable HEARTBEAT_OK token.

    Phase 2 (execution): only triggered when Phase 1 returns ``run``.  The
    ``on_execute`` callback runs the task through the full agent loop and
    returns the result to deliver.
    """

    def __init__(
        self,
        workspace: Path,
        provider: LLMProvider,
        model: str,
        on_execute: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        on_notify: Callable[[str], Coroutine[Any, Any, None]] | None = None,
        interval_s: int = 30 * 60,
        enabled: bool = True,
        triage_model: str | None = None,
        planning_model: str | None = None,
    ):
        self.workspace = workspace
        self.provider = provider
        self.model = model
        self.on_execute = on_execute
        self.on_notify = on_notify
        self.interval_s = interval_s
        self.enabled = enabled
        self.triage_model = triage_model
        self.planning_model = planning_model
        self._running = False
        self._task: asyncio.Task | None = None
        # Populated during _tick() so on_execute closures can read the chosen model.
        self._selected_model_override: str | None = None

    @property
    def heartbeat_file(self) -> Path:
        return self.workspace / "HEARTBEAT.md"

    def _read_heartbeat_file(self) -> str | None:
        if self.heartbeat_file.exists():
            try:
                return self.heartbeat_file.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    async def _decide(self, content: str) -> tuple[str, str]:
        """Phase 1: ask LLM to decide skip/run via virtual tool call.

        Returns (action, tasks) where action is 'skip' or 'run'.
        """
        from nanobot.utils.helpers import current_time_str

        response = await self.provider.chat_with_retry(
            messages=[
                {"role": "system", "content": "You are a heartbeat agent. Call the heartbeat tool to report your decision."},
                {"role": "user", "content": (
                    f"Current Time: {current_time_str()}\n\n"
                    "Review the following HEARTBEAT.md and decide whether there are active tasks.\n\n"
                    f"{content}"
                )},
            ],
            tools=_HEARTBEAT_TOOL,
            model=self.model,
        )

        if not response.has_tool_calls:
            return "skip", ""

        args = response.tool_calls[0].arguments
        return args.get("action", "skip"), args.get("tasks", "")

    async def _triage_complexity(self, tasks: str) -> str:
        """Classify task complexity via a virtual tool call.

        Returns 'simple' or 'complex'.  Falls back to 'complex' when the LLM
        does not call the tool (safe default keeps the capable model).
        """
        response = await self.provider.chat_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a task classifier. "
                        "Call classify_task to indicate whether the pending tasks are "
                        "simple (a lightweight local model can handle them) or "
                        "complex (they require a capable planning model)."
                    ),
                },
                {"role": "user", "content": tasks},
            ],
            tools=_TRIAGE_TOOL,
            model=self.model,
        )
        if response.has_tool_calls:
            return response.tool_calls[0].arguments.get("complexity", "complex")
        return "complex"

    async def start(self) -> None:
        """Start the heartbeat service."""
        if not self.enabled:
            logger.info("Heartbeat disabled")
            return
        if self._running:
            logger.warning("Heartbeat already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Heartbeat started (every {}s)", self.interval_s)

    def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval_s)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat error: {}", e)

    async def _tick(self) -> None:
        """Execute a single heartbeat tick."""
        from nanobot.utils.evaluator import evaluate_response

        content = self._read_heartbeat_file()
        if not content:
            logger.debug("Heartbeat: HEARTBEAT.md missing or empty")
            return

        logger.info("Heartbeat: checking for tasks...")

        self._selected_model_override = None

        try:
            action, tasks = await self._decide(content)

            if action != "run":
                logger.info("Heartbeat: OK (nothing to report)")
                return

            # Triage: route task to the appropriate model when configured.
            if self.triage_model and self.planning_model:
                complexity = await self._triage_complexity(tasks)
                if complexity == "simple":
                    self._selected_model_override = self.triage_model
                    logger.info("Heartbeat: simple task → {}", self.triage_model)
                else:
                    self._selected_model_override = self.planning_model
                    logger.info("Heartbeat: complex task → {}", self.planning_model)

            logger.info("Heartbeat: tasks found, executing...")
            if self.on_execute:
                response = await self.on_execute(tasks)

                if response:
                    should_notify = await evaluate_response(
                        response, tasks, self.provider, self.model,
                    )
                    if should_notify and self.on_notify:
                        logger.info("Heartbeat: completed, delivering response")
                        await self.on_notify(response)
                    else:
                        logger.info("Heartbeat: silenced by post-run evaluation")
        except Exception:
            logger.exception("Heartbeat execution failed")

    async def trigger_now(self) -> str | None:
        """Manually trigger a heartbeat."""
        content = self._read_heartbeat_file()
        if not content:
            return None
        action, tasks = await self._decide(content)
        if action != "run" or not self.on_execute:
            return None
        return await self.on_execute(tasks)
