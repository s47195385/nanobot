import asyncio

import pytest

from nanobot.heartbeat.service import HeartbeatService
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class DummyProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse]):
        super().__init__()
        self._responses = list(responses)
        self.calls = 0

    async def chat(self, *args, **kwargs) -> LLMResponse:
        self.calls += 1
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(content="", tool_calls=[])

    def get_default_model(self) -> str:
        return "test-model"


@pytest.mark.asyncio
async def test_start_is_idempotent(tmp_path) -> None:
    provider = DummyProvider([])

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="openai/gpt-4o-mini",
        interval_s=9999,
        enabled=True,
    )

    await service.start()
    first_task = service._task
    await service.start()

    assert service._task is first_task

    service.stop()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_decide_returns_skip_when_no_tool_call(tmp_path) -> None:
    provider = DummyProvider([LLMResponse(content="no tool call", tool_calls=[])])
    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="openai/gpt-4o-mini",
    )

    action, tasks = await service._decide("heartbeat content")
    assert action == "skip"
    assert tasks == ""


@pytest.mark.asyncio
async def test_trigger_now_executes_when_decision_is_run(tmp_path) -> None:
    (tmp_path / "HEARTBEAT.md").write_text("- [ ] do thing", encoding="utf-8")

    provider = DummyProvider([
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="hb_1",
                    name="heartbeat",
                    arguments={"action": "run", "tasks": "check open tasks"},
                )
            ],
        )
    ])

    called_with: list[str] = []

    async def _on_execute(tasks: str) -> str:
        called_with.append(tasks)
        return "done"

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="openai/gpt-4o-mini",
        on_execute=_on_execute,
    )

    result = await service.trigger_now()
    assert result == "done"
    assert called_with == ["check open tasks"]


@pytest.mark.asyncio
async def test_trigger_now_returns_none_when_decision_is_skip(tmp_path) -> None:
    (tmp_path / "HEARTBEAT.md").write_text("- [ ] do thing", encoding="utf-8")

    provider = DummyProvider([
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="hb_1",
                    name="heartbeat",
                    arguments={"action": "skip"},
                )
            ],
        )
    ])

    async def _on_execute(tasks: str) -> str:
        return tasks

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="openai/gpt-4o-mini",
        on_execute=_on_execute,
    )

    assert await service.trigger_now() is None


@pytest.mark.asyncio
async def test_tick_notifies_when_evaluator_says_yes(tmp_path, monkeypatch) -> None:
    """Phase 1 run -> Phase 2 execute -> Phase 3 evaluate=notify -> on_notify called."""
    (tmp_path / "HEARTBEAT.md").write_text("- [ ] check deployments", encoding="utf-8")

    provider = DummyProvider([
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="hb_1",
                    name="heartbeat",
                    arguments={"action": "run", "tasks": "check deployments"},
                )
            ],
        ),
    ])

    executed: list[str] = []
    notified: list[str] = []

    async def _on_execute(tasks: str) -> str:
        executed.append(tasks)
        return "deployment failed on staging"

    async def _on_notify(response: str) -> None:
        notified.append(response)

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="openai/gpt-4o-mini",
        on_execute=_on_execute,
        on_notify=_on_notify,
    )

    async def _eval_notify(*a, **kw):
        return True

    monkeypatch.setattr("nanobot.utils.evaluator.evaluate_response", _eval_notify)

    await service._tick()
    assert executed == ["check deployments"]
    assert notified == ["deployment failed on staging"]


@pytest.mark.asyncio
async def test_tick_suppresses_when_evaluator_says_no(tmp_path, monkeypatch) -> None:
    """Phase 1 run -> Phase 2 execute -> Phase 3 evaluate=silent -> on_notify NOT called."""
    (tmp_path / "HEARTBEAT.md").write_text("- [ ] check status", encoding="utf-8")

    provider = DummyProvider([
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="hb_1",
                    name="heartbeat",
                    arguments={"action": "run", "tasks": "check status"},
                )
            ],
        ),
    ])

    executed: list[str] = []
    notified: list[str] = []

    async def _on_execute(tasks: str) -> str:
        executed.append(tasks)
        return "everything is fine, no issues"

    async def _on_notify(response: str) -> None:
        notified.append(response)

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="openai/gpt-4o-mini",
        on_execute=_on_execute,
        on_notify=_on_notify,
    )

    async def _eval_silent(*a, **kw):
        return False

    monkeypatch.setattr("nanobot.utils.evaluator.evaluate_response", _eval_silent)

    await service._tick()
    assert executed == ["check status"]
    assert notified == []


@pytest.mark.asyncio
async def test_decide_retries_transient_error_then_succeeds(tmp_path, monkeypatch) -> None:
    provider = DummyProvider([
        LLMResponse(content="429 rate limit", finish_reason="error"),
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="hb_1",
                    name="heartbeat",
                    arguments={"action": "run", "tasks": "check open tasks"},
                )
            ],
        ),
    ])

    delays: list[int] = []

    async def _fake_sleep(delay: int) -> None:
        delays.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="openai/gpt-4o-mini",
    )

    action, tasks = await service._decide("heartbeat content")

    assert action == "run"
    assert tasks == "check open tasks"
    assert provider.calls == 2
    assert delays == [1]


@pytest.mark.asyncio
async def test_decide_prompt_includes_current_time(tmp_path) -> None:
    """Phase 1 user prompt must contain current time so the LLM can judge task urgency."""

    captured_messages: list[dict] = []

    class CapturingProvider(LLMProvider):
        async def chat(self, *, messages=None, **kwargs) -> LLMResponse:
            if messages:
                captured_messages.extend(messages)
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="hb_1", name="heartbeat",
                        arguments={"action": "skip"},
                    )
                ],
            )

        def get_default_model(self) -> str:
            return "test-model"

    service = HeartbeatService(
        workspace=tmp_path,
        provider=CapturingProvider(),
        model="test-model",
    )

    await service._decide("- [ ] check servers at 10:00 UTC")

    user_msg = captured_messages[1]
    assert user_msg["role"] == "user"
    assert "Current Time:" in user_msg["content"]


@pytest.mark.asyncio
async def test_triage_complexity_returns_simple(tmp_path) -> None:
    """_triage_complexity returns 'simple' when LLM calls classify_task with simple."""
    provider = DummyProvider([
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="triage_1",
                    name="classify_task",
                    arguments={"complexity": "simple"},
                )
            ],
        )
    ])
    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="test-model",
    )
    result = await service._triage_complexity("fix typo in README")
    assert result == "simple"


@pytest.mark.asyncio
async def test_triage_complexity_returns_complex(tmp_path) -> None:
    """_triage_complexity returns 'complex' when LLM calls classify_task with complex."""
    provider = DummyProvider([
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="triage_2",
                    name="classify_task",
                    arguments={"complexity": "complex"},
                )
            ],
        )
    ])
    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="test-model",
    )
    result = await service._triage_complexity("Design a new microservices architecture")
    assert result == "complex"


@pytest.mark.asyncio
async def test_triage_complexity_defaults_to_complex_on_no_tool_call(tmp_path) -> None:
    """_triage_complexity falls back to 'complex' when LLM makes no tool call."""
    provider = DummyProvider([LLMResponse(content="unclear", tool_calls=[])])
    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="test-model",
    )
    result = await service._triage_complexity("some task")
    assert result == "complex"


@pytest.mark.asyncio
async def test_tick_sets_simple_model_override(tmp_path, monkeypatch) -> None:
    """_tick sets _selected_model_override to triage_model for a simple task."""
    (tmp_path / "HEARTBEAT.md").write_text("- [ ] fix typo", encoding="utf-8")

    decide_response = LLMResponse(
        content="",
        tool_calls=[
            ToolCallRequest(
                id="hb_1",
                name="heartbeat",
                arguments={"action": "run", "tasks": "fix typo"},
            )
        ],
    )
    triage_response = LLMResponse(
        content="",
        tool_calls=[
            ToolCallRequest(
                id="t_1",
                name="classify_task",
                arguments={"complexity": "simple"},
            )
        ],
    )
    provider = DummyProvider([decide_response, triage_response])

    observed_overrides: list[str | None] = []

    async def _on_execute(tasks: str) -> str:
        observed_overrides.append(service._selected_model_override)
        return "done"

    async def _eval_notify(*a, **kw):
        return False

    monkeypatch.setattr("nanobot.utils.evaluator.evaluate_response", _eval_notify)

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="gemini/gemini-3-pro",
        on_execute=_on_execute,
        triage_model="ollama_chat/rnj-1",
        planning_model="gemini/gemini-3-pro",
    )

    await service._tick()
    assert observed_overrides == ["ollama_chat/rnj-1"]


@pytest.mark.asyncio
async def test_tick_sets_complex_model_override(tmp_path, monkeypatch) -> None:
    """_tick sets _selected_model_override to planning_model for a complex task."""
    (tmp_path / "HEARTBEAT.md").write_text("- [ ] design system", encoding="utf-8")

    decide_response = LLMResponse(
        content="",
        tool_calls=[
            ToolCallRequest(
                id="hb_1",
                name="heartbeat",
                arguments={"action": "run", "tasks": "design system"},
            )
        ],
    )
    triage_response = LLMResponse(
        content="",
        tool_calls=[
            ToolCallRequest(
                id="t_1",
                name="classify_task",
                arguments={"complexity": "complex"},
            )
        ],
    )
    provider = DummyProvider([decide_response, triage_response])

    observed_overrides: list[str | None] = []

    async def _on_execute(tasks: str) -> str:
        observed_overrides.append(service._selected_model_override)
        return "done"

    async def _eval_notify(*a, **kw):
        return False

    monkeypatch.setattr("nanobot.utils.evaluator.evaluate_response", _eval_notify)

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="gemini/gemini-3-pro",
        on_execute=_on_execute,
        triage_model="ollama_chat/rnj-1",
        planning_model="gemini/gemini-3-pro",
    )

    await service._tick()
    assert observed_overrides == ["gemini/gemini-3-pro"]


@pytest.mark.asyncio
async def test_tick_no_override_without_triage_config(tmp_path, monkeypatch) -> None:
    """When triage_model/planning_model not set, _selected_model_override stays None."""
    (tmp_path / "HEARTBEAT.md").write_text("- [ ] some task", encoding="utf-8")

    provider = DummyProvider([
        LLMResponse(
            content="",
            tool_calls=[
                ToolCallRequest(
                    id="hb_1",
                    name="heartbeat",
                    arguments={"action": "run", "tasks": "some task"},
                )
            ],
        ),
    ])

    observed_overrides: list[str | None] = []

    async def _on_execute(tasks: str) -> str:
        observed_overrides.append(service._selected_model_override)
        return "done"

    async def _eval_notify(*a, **kw):
        return False

    monkeypatch.setattr("nanobot.utils.evaluator.evaluate_response", _eval_notify)

    service = HeartbeatService(
        workspace=tmp_path,
        provider=provider,
        model="gemini/gemini-3-pro",
        on_execute=_on_execute,
    )

    await service._tick()
    assert observed_overrides == [None]

