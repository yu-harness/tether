import json
from types import SimpleNamespace

import pytest

from tether import FakeModelClient, Tether, SessionStore, WorkspaceContext
from tether.tracing import (
    NoopTracer,
    SamplingTracer,
    _make_otlp_exporter,
    _parse_headers,
    parse_sample_rate,
    sample_run,
    tracer_from_env,
)


class RecordingTracer:
    # 手写记录器：把 emit_trace 转发来的 payload 原样存下来，
    # 用来验证「事件流同时进 trace.jsonl 和外部追踪后端」这条链路。
    def __init__(self):
        self.events = []

    def record(self, agent, task_state, payload):
        self.events.append((task_state.run_id, payload["event"]))

    def flush(self):
        return None


def build_workspace(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    return WorkspaceContext.build(tmp_path, repo_root_override=tmp_path)


def build_agent(tmp_path, outputs, **kwargs):
    store = SessionStore(tmp_path / ".tether" / "sessions")
    return Tether(
        model_client=FakeModelClient(outputs),
        workspace=build_workspace(tmp_path),
        session_store=store,
        approval_policy="auto",
        **kwargs,
    )


def test_tracer_defaults_to_noop(monkeypatch):
    monkeypatch.delenv("TETHER_TRACING", raising=False)
    tracer = tracer_from_env()
    assert isinstance(tracer, NoopTracer)


def test_tracer_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("TETHER_TRACING", "jaeger")
    with pytest.raises(RuntimeError):
        tracer_from_env()


def test_tracer_fails_fast_when_collector_unreachable(monkeypatch):
    monkeypatch.setenv("TETHER_TRACING", "otel")
    # 19999 端口上没有 collector，必须就地报错，不允许追踪静默丢失。
    monkeypatch.setenv("TETHER_OTEL_ENDPOINT", "http://localhost:19999/v1/traces")
    with pytest.raises(OSError):
        tracer_from_env()


def test_parse_headers_accepts_otlp_format():
    # base64 填充的 == 必须完整保留在 value 里，只允许按第一个 = 切分。
    headers = _parse_headers("Authorization=Basic cGs6c2s=, x-langfuse-ingestion-version=4")
    assert headers == {
        "Authorization": "Basic cGs6c2s=",
        "x-langfuse-ingestion-version": "4",
    }


def test_parse_headers_rejects_malformed_item():
    with pytest.raises(RuntimeError):
        _parse_headers("Authorization")


def test_localhost_exporter_bypasses_env_proxy(monkeypatch):
    # 本机端点必须忽略环境里的 HTTP 代理，否则沙箱代理会让导出失败。
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    exporter = _make_otlp_exporter(OTLPSpanExporter, "http://localhost:4318/v1/traces", {"a": "b"})
    assert exporter._session.trust_env is False


def test_remote_exporter_keeps_default_session(monkeypatch):
    # 远端端点保持 requests 默认行为，公司代理等环境配置继续生效。
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    exporter = _make_otlp_exporter(OTLPSpanExporter, "https://otel.example.com/v1/traces", None)
    assert exporter._session.trust_env is True


def test_agent_uses_noop_tracer_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("TETHER_TRACING", raising=False)
    agent = build_agent(tmp_path, ["<final>done</final>"])
    assert isinstance(agent.tracer, NoopTracer)
    agent.ask("hello")


def test_emit_trace_forwards_full_event_stream(tmp_path):
    (tmp_path / "hello.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    tracer = RecordingTracer()
    agent = build_agent(
        tmp_path,
        [
            '<tool>{"name":"read_file","args":{"path":"hello.txt"}}</tool>',
            "<final>Read the file successfully.</final>",
        ],
        tracer=tracer,
    )

    agent.ask("Inspect hello.txt")

    forwarded = [event for _, event in tracer.events]
    trace_path = agent.current_run_dir / "trace.jsonl"
    persisted = [json.loads(line)["event"] for line in trace_path.read_text(encoding="utf-8").splitlines()]
    # 转发给外部后端的事件流必须和落盘的 trace.jsonl 完全一致，
    # 这样 Langfuse 里的 span 树和本地工件才能互相印证。
    assert forwarded == persisted
    assert forwarded[0] == "run_started"
    assert forwarded[-1] == "run_finished"
    assert "model_requested" in forwarded
    assert "model_parsed" in forwarded
    assert "tool_executed" in forwarded
    run_ids = {run_id for run_id, _ in tracer.events}
    assert len(run_ids) == 1


def test_parse_sample_rate_defaults_to_full_and_rejects_invalid():
    assert parse_sample_rate("") == 1.0
    assert parse_sample_rate("0.25") == 0.25
    assert parse_sample_rate("1") == 1.0
    with pytest.raises(ValueError):
        parse_sample_rate("1.5")
    with pytest.raises(ValueError):
        parse_sample_rate("abc")


def test_sample_run_is_deterministic_and_bounded():
    run_id = "run_20261008-101010-abcdef"
    assert sample_run(run_id, 0.5) == sample_run(run_id, 0.5)
    assert sample_run(run_id, 0.0) is False
    assert sample_run(run_id, 1.0) is True


def test_sampling_tracer_keeps_each_run_atomic():
    inner = RecordingTracer()
    tracer = SamplingTracer(inner, 0.5)
    task_states = [SimpleNamespace(run_id=f"run_{index}") for index in range(40)]

    for task_state in task_states:
        for event in ("run_started", "model_requested", "run_finished"):
            tracer.record(None, task_state, {"event": event})

    counts = {}
    for run_id, _ in inner.events:
        counts[run_id] = counts.get(run_id, 0) + 1
    # 每个 run 的事件要么全部转发，要么一条都不转发，不能只留半条 trace。
    assert set(counts.values()) == {3}
    assert 0 < len(counts) < len(task_states)


def test_tracer_disabled_when_sample_rate_zero(monkeypatch):
    monkeypatch.setenv("TETHER_TRACING", "otel")
    monkeypatch.setenv("TETHER_TRACING_SAMPLE_RATE", "0")
    # 采样率为 0 时不建连接，端点不可达也不报错。
    monkeypatch.setenv("TETHER_OTEL_ENDPOINT", "http://localhost:19999/v1/traces")
    assert isinstance(tracer_from_env(), NoopTracer)
