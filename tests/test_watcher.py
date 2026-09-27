"""Hermetic tests for bridge.watcher (no network, no Azure, no AWS)."""

from __future__ import annotations

from bridge.watcher import (
    ESCALATIONS_CHANNEL,
    WatcherConfig,
    escalate,
    load_watcher_config,
    process_channel,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeStore:
    def __init__(self) -> None:
        self.channels: dict[str, list[dict]] = {}
        self._n = 0

    def send_message(self, channel: str, author: str, text: str) -> dict:
        self._n += 1
        msg = {"id": f"m{self._n}", "ts": "2026-09-27T00:00:00+00:00",
               "author": author, "text": text}
        self.channels.setdefault(channel, []).append(msg)
        return msg

    def read_messages(self, channel: str, limit: int = 50) -> list[dict]:
        return self.channels.get(channel, [])[-limit:]

    def list_channels(self) -> list[str]:
        return sorted(self.channels)


class FakeBackend:
    def __init__(self, briefs: dict[str, str] | None = None) -> None:
        self.briefs = briefs or {}

    def list_briefs(self) -> list[str]:
        return sorted(self.briefs)

    def read_brief(self, name: str) -> str:
        if name not in self.briefs:
            raise FileNotFoundError(name)
        return self.briefs[name]


class _Block:
    def __init__(self, kind: str, **kw) -> None:
        self.type = kind
        for k, v in kw.items():
            setattr(self, k, v)


class _Resp:
    def __init__(self, blocks: list[_Block]) -> None:
        self.content = blocks


class FakeBedrock:
    """Scripted Bedrock client: each messages.create pops the next script item.

    Script items are lists of ("text", str) / ("tool", name, input) tuples.
    """

    def __init__(self, script: list[list[tuple]]) -> None:
        self.script = list(script)
        self.calls: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        step = self.script.pop(0) if self.script else [("text", "done")]
        blocks, n = [], 0
        for item in step:
            if item[0] == "text":
                blocks.append(_Block("text", text=item[1]))
            else:
                n += 1
                blocks.append(
                    _Block("tool_use", id=f"tu{n}", name=item[1], input=item[2])
                )
        return _Resp(blocks)


def _cfg(**kw) -> WatcherConfig:
    base = dict(
        channels=["demo"],
        state_container="watcher-state",
        aws_region="us-east-1",
        bedrock_model="global.anthropic.claude-sonnet-4-6",
        max_rounds=6,
        max_tool_iters=10,
        history_limit=30,
        max_tokens=64,
    )
    base.update(kw)
    return WatcherConfig(**base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_new_messages_makes_no_bedrock_call():
    store, backend = FakeStore(), FakeBackend()
    client = FakeBedrock([])
    state: dict = {}
    process_channel(_cfg(), store, backend, client, state, "demo")
    assert client.calls == []
    assert state == {}


def test_new_message_triggers_claude_reply():
    store, backend = FakeStore(), FakeBackend()
    store.send_message("demo", "chitti", "draft the launch post")
    client = FakeBedrock([[("tool", "send_message", {"text": "here is the draft"})]])
    state: dict = {}
    process_channel(_cfg(), store, backend, client, state, "demo")
    msgs = store.read_messages("demo")
    assert msgs[-1]["author"] == "claude"
    assert msgs[-1]["text"] == "here is the draft"
    assert state["demo"]["count"] == 2
    assert client.calls[0]["model"] == "global.anthropic.claude-sonnet-4-6"


def test_prose_answer_without_tool_call_gets_posted():
    store, backend = FakeStore(), FakeBackend()
    store.send_message("demo", "chitti", "status?")
    client = FakeBedrock([[("text", "all good")]])
    state: dict = {}
    process_channel(_cfg(), store, backend, client, state, "demo")
    assert store.read_messages("demo")[-1] == {
        "id": "m2", "ts": "2026-09-27T00:00:00+00:00",
        "author": "claude", "text": "all good",
    }


def test_own_echo_does_not_nudge():
    store, backend = FakeStore(), FakeBackend()
    store.send_message("demo", "claude", "earlier reply")
    client = FakeBedrock([])
    state = {"demo": {"count": 0, "rounds": 0, "paused": False}}
    process_channel(_cfg(), store, backend, client, state, "demo")
    assert client.calls == []
    assert state["demo"]["count"] == 1


def test_claude_can_read_briefs_via_tools():
    store = FakeStore()
    backend = FakeBackend({"plan.md": "# plan"})
    store.send_message("demo", "chitti", "summarize the plan brief")
    client = FakeBedrock([
        [("tool", "get_brief", {"name": "plan.md"})],
        [("tool", "send_message", {"text": "summary here"})],
    ])
    state: dict = {}
    process_channel(_cfg(), store, backend, client, state, "demo")
    assert store.read_messages("demo")[-1]["text"] == "summary here"


def test_needs_human_escalates_and_pauses():
    store, backend = FakeStore(), FakeBackend()
    store.send_message("demo", "chitti", "go with option A")
    client = FakeBedrock(
        [[("tool", "send_message", {"text": "[NEEDS-HUMAN] A or B? blocked."})]]
    )
    state: dict = {}
    process_channel(_cfg(), store, backend, client, state, "demo")
    esc = store.read_messages(ESCALATIONS_CHANNEL)
    assert len(esc) == 1
    assert esc[0]["author"] == "watcher"
    assert "demo" in esc[0]["text"]
    assert state["demo"]["paused"] is True
    # While paused, further chitti messages do not trigger Bedrock...
    calls_before = len(client.calls)
    store.send_message("demo", "chitti", "hello?")
    process_channel(_cfg(), store, backend, client, state, "demo")
    assert len(client.calls) == calls_before
    # ...until a human weighs in, which resumes the channel.
    process_channel(_cfg(), store, backend, client, state, "demo")
    assert state["demo"]["paused"] is False


def test_rounds_tripwire_escalates_without_resolution():
    store, backend = FakeStore(), FakeBackend()
    store.send_message("demo", "chitti", "iterate on the copy")
    client = FakeBedrock([[("tool", "send_message", {"text": "v1"})]])
    state: dict = {}
    process_channel(_cfg(max_rounds=1), store, backend, client, state, "demo")
    assert len(store.read_messages(ESCALATIONS_CHANNEL)) == 1
    assert state["demo"]["paused"] is True


def test_resolved_tag_resets_rounds():
    store, backend = FakeStore(), FakeBackend()
    store.send_message("demo", "chitti", "ship it")
    client = FakeBedrock([[("tool", "send_message", {"text": "shipped [RESOLVED]"})]])
    state = {"demo": {"count": 0, "rounds": 4, "paused": False}}
    process_channel(_cfg(), store, backend, client, state, "demo")
    assert state["demo"]["rounds"] == 0
    assert store.read_messages(ESCALATIONS_CHANNEL) == []


def test_escalate_writes_summary():
    store = FakeStore()
    store.send_message("demo", "chitti", "context message")
    escalate(store, "demo", "test reason", store.read_messages("demo"))
    esc = store.read_messages(ESCALATIONS_CHANNEL)[-1]
    assert "test reason" in esc["text"]
    assert "#demo" in esc["text"]


def test_load_watcher_config_defaults(monkeypatch):
    for var in ("WATCH_CHANNELS", "AWS_REGION", "BEDROCK_MODEL_ID"):
        monkeypatch.delenv(var, raising=False)
    cfg = load_watcher_config()
    assert cfg.channels == ["voice-agent-gtm"]
    assert cfg.aws_region == "us-east-1"
    assert cfg.bedrock_model == "global.anthropic.claude-sonnet-4-6"
    assert cfg.max_rounds == 6


def test_load_watcher_config_env_override(monkeypatch):
    monkeypatch.setenv("WATCH_CHANNELS", "a, b")
    monkeypatch.setenv("WATCH_MAX_ROUNDS", "3")
    cfg = load_watcher_config()
    assert cfg.channels == ["a", "b"]
    assert cfg.max_rounds == 3
