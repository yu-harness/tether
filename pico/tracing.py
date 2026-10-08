import hashlib
import json
import os
from datetime import datetime

# 外部追踪后端接入。
#
# 默认走 NoopTracer，什么都不记录，现有行为完全不变。
# 设置 PICO_TRACING=otel 后启用 OtelTracer，按 OpenTelemetry 的 GenAI 语义约定
# 把 emit_trace 的事件流映射成三层结构，经 OTLP 发给后端（Jaeger、Langfuse 等）：
# - trace：一次 run，trace id 由 run_id 经 sha256 确定性派生，和 .pico/runs 一一对应
# - span：run 内部的单次动作（模型调用 generation、工具调用 tool 等）
# - session.id：pico 的 session id，对应面试口径里的 thread 层
#
# Langfuse 原生收 OTLP，配置区别在端点与请求头（PICO_OTEL_HEADERS，
# key=value 逗号分隔）：端点指到 /api/public/otel/v1/traces，请求头带
# Authorization: Basic base64(public_key:secret_key) 与
# x-langfuse-ingestion-version: 4。
# langfuse.observation.type 属性对 Jaeger 是无害的多余属性，对 Langfuse
# 决定 span 显示成 agent / generation / tool 哪种类型，因此无条件带上。

TRACING_ENV_VAR = "PICO_TRACING"
TRACING_SAMPLE_RATE_ENV_VAR = "PICO_TRACING_SAMPLE_RATE"
OTEL_ENDPOINT_ENV_VAR = "PICO_OTEL_ENDPOINT"
OTEL_HEADERS_ENV_VAR = "PICO_OTEL_HEADERS"
DEFAULT_OTEL_ENDPOINT = "http://localhost:4318/v1/traces"
DEFAULT_TRACING_SAMPLE_RATE = 1.0

# Langfuse 的显式 observation 类型属性键，取值：agent / generation / tool 等。
LANGFUSE_OBSERVATION_TYPE = "langfuse.observation.type"


def _parse_headers(raw):
    # 与 OTEL_EXPORTER_OTLP_HEADERS 相同的格式：key=value 逗号分隔。
    headers = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise RuntimeError(f"{OTEL_HEADERS_ENV_VAR} 里有不是 key=value 的项：{item}")
        name, value = item.split("=", 1)
        headers[name.strip()] = value.strip()
    return headers

# payload 里这两个键是每个事件都有的信封字段，转发时不再重复进属性。
_ENVELOPE_KEYS = ("event", "created_at")

# OTel 的时间戳单位是纳秒。
def _iso_to_ns(iso_text):
    return int(datetime.fromisoformat(iso_text).timestamp() * 1_000_000_000)


def _event_span_times(payload):
    end_ns = _iso_to_ns(payload["created_at"])
    duration_ms = payload.get("duration_ms")
    start_ns = end_ns - int(duration_ms) * 1_000_000 if isinstance(duration_ms, int) else end_ns
    return start_ns, end_ns


def _flatten_metadata(prefix, value, out):
    # OTel 属性只接受标量与标量数组，嵌套结构拍平成点路径，复杂值转 JSON 字符串。
    # None 不是合法属性值，直接跳过这个键。
    if value is None:
        return
    if isinstance(value, (str, int, float, bool)):
        out[prefix] = value
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten_metadata(f"{prefix}.{key}", item, out)
        return
    if isinstance(value, (list, tuple)):
        if all(isinstance(item, (str, int, float, bool)) for item in value):
            out[prefix] = json.dumps(list(value), ensure_ascii=False)
        else:
            out[prefix] = json.dumps(list(value), ensure_ascii=False)
        return
    out[prefix] = str(value)


def _event_attributes(payload, prefix="pico.event"):
    attributes = {}
    for key, value in payload.items():
        if key in _ENVELOPE_KEYS:
            continue
        _flatten_metadata(f"{prefix}.{key}", value, attributes)
    return attributes


class NoopTracer:
    # 默认追踪器：所有事件直接丢弃，零开销。
    def record(self, agent, task_state, payload):
        return None

    def flush(self):
        return None


def parse_sample_rate(raw):
    # 采样率是 0 到 1 之间的浮点数；空值按全采样处理，非法取值就地报错。
    text = str(raw).strip()
    if not text:
        return DEFAULT_TRACING_SAMPLE_RATE
    rate = float(text)
    if rate < 0.0 or rate > 1.0:
        raise ValueError(f"{TRACING_SAMPLE_RATE_ENV_VAR} 必须在 0 与 1 之间：{text}")
    return rate


def sample_run(run_id, rate):
    # 按 run_id 做确定性采样：同一个 run 的全部事件一起进出，trace 不会只留一半；
    # 同一批 run 重复跑，被选中的集合也一样，采样结果可以复盘。
    digest = hashlib.sha256(str(run_id).encode("utf-8")).digest()
    point = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return point < rate


class SamplingTracer:
    # 采样包装器：被选中的 run 全量转发，未选中的 run 一个事件都不转发。
    def __init__(self, inner, rate):
        self.inner = inner
        self.rate = rate
        self._selected = {}

    def record(self, agent, task_state, payload):
        run_id = task_state.run_id
        selected = self._selected.get(run_id)
        if selected is None:
            selected = sample_run(run_id, self.rate)
            self._selected[run_id] = selected
        if selected:
            self.inner.record(agent, task_state, payload)
        if payload["event"] == "run_finished":
            self._selected.pop(run_id, None)

    def flush(self):
        self.inner.flush()


def _make_otlp_exporter(exporter_cls, endpoint, headers):
    # 本机端点（localhost / 127.0.0.1）必须绕过环境变量里的 HTTP 代理：
    # 代理是为远端主机准备的，拦截本机流量只会让导出失败
    # （比如沙箱代理对本机端口回重定向，导出器报 Exceeded 30 redirects）。
    # trust_env=False 让 requests 完全忽略 *_PROXY 环境变量。
    from urllib.parse import urlparse

    host = urlparse(endpoint).hostname
    if host in ("localhost", "127.0.0.1", "::1"):
        import requests

        session = requests.Session()
        session.trust_env = False
        return exporter_cls(endpoint=endpoint, headers=headers or None, session=session)
    return exporter_cls(endpoint=endpoint, headers=headers or None)


class OtelTracer:
    def __init__(self, endpoint, headers=None):
        # 放在函数内 import：只有真正启用追踪时才加载 OTel SDK，
        # 默认路径（Noop）不需要这套依赖。
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.semconv._incubating.attributes import gen_ai_attributes, session_attributes
        from opentelemetry.semconv.attributes.service_attributes import SERVICE_NAME

        self._trace = trace
        self._gen_ai = gen_ai_attributes
        self._session = session_attributes

        resource = Resource.create({SERVICE_NAME: "pico"})
        provider = TracerProvider(resource=resource)
        exporter = _make_otlp_exporter(OTLPSpanExporter, endpoint, headers)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        self.provider = provider
        self.tracer = provider.get_tracer("pico")
        self._assert_endpoint_reachable(endpoint)
        self._runs = {}

    def _assert_endpoint_reachable(self, endpoint):
        # 启动时确认 collector 能连上，配置错了就地报错，
        # 不允许追踪静默丢失。
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(endpoint)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        probe = socket.create_connection((host, port), timeout=3)
        probe.close()

    def flush(self):
        self.provider.force_flush()

    def _trace_context(self, run_id):
        # 用 run_id 的 sha256 前 16 字节当 trace id：
        # 同一个 run 的全部 span 进同一条 trace，且可从 run_id 直接算回来。
        digest = hashlib.sha256(run_id.encode("utf-8")).digest()
        trace_id = int.from_bytes(digest[:16], "big")
        span_id = int.from_bytes(digest[16:24], "big")
        context = self._trace.SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=True,
            trace_flags=self._trace.TraceFlags(self._trace.TraceFlags.SAMPLED),
        )
        return self._trace.set_span_in_context(self._trace.NonRecordingSpan(context))

    def record(self, agent, task_state, payload):
        event = payload["event"]
        handler = getattr(self, f"_on_{event}", self._on_generic)
        handler(agent, task_state, payload)

    def _require_run(self, task_state):
        state = self._runs.get(task_state.run_id)
        if state is None:
            raise RuntimeError(f"收到 run_started 之前的追踪事件：run_id={task_state.run_id}")
        return state

    def _on_run_started(self, agent, task_state, payload):
        gen_ai = self._gen_ai
        session_id = str(agent.session["id"])
        root = self.tracer.start_span(
            "pico-run",
            context=self._trace_context(task_state.run_id),
            start_time=_iso_to_ns(payload["created_at"]),
            attributes={
                gen_ai.GEN_AI_OPERATION_NAME: "invoke_agent",
                gen_ai.GEN_AI_SYSTEM: str(getattr(agent.model_client, "model", "fake")),
                self._session.SESSION_ID: session_id,
                LANGFUSE_OBSERVATION_TYPE: "agent",
                "pico.run_id": task_state.run_id,
                "pico.task_id": task_state.task_id,
                "pico.user_request": str(payload.get("user_request", "")),
            },
        )
        self._runs[task_state.run_id] = {"root": root, "generation": None, "session_id": session_id}

    def _start_event_span(self, agent, task_state, payload, name, extra_attributes=None):
        state = self._require_run(task_state)
        start_ns, end_ns = _event_span_times(payload)
        attributes = _event_attributes(payload)
        # session.id 要传播到每个 span，Langfuse 的 session 聚合只统计带这个属性的行。
        attributes[self._session.SESSION_ID] = state["session_id"]
        if extra_attributes:
            attributes.update(extra_attributes)
        span = self.tracer.start_span(
            name,
            context=self._trace.set_span_in_context(state["root"]),
            start_time=start_ns,
            attributes=attributes,
        )
        return span, end_ns

    def _on_prompt_built(self, agent, task_state, payload):
        span, end_ns = self._start_event_span(agent, task_state, payload, "prompt_built")
        span.end(end_time=end_ns)

    def _on_model_requested(self, agent, task_state, payload):
        state = self._require_run(task_state)
        # generation 在这里打开、在 model_parsed 关闭，跨度就是一次真实的模型调用。
        generation = self.tracer.start_span(
            "model_complete",
            context=self._trace.set_span_in_context(state["root"]),
            start_time=_iso_to_ns(payload["created_at"]),
            attributes={
                self._gen_ai.GEN_AI_OPERATION_NAME: "chat",
                self._gen_ai.GEN_AI_SYSTEM: str(getattr(agent.model_client, "model", "fake")),
                self._gen_ai.GEN_AI_REQUEST_MODEL: str(getattr(agent.model_client, "model", "fake")),
                self._session.SESSION_ID: state["session_id"],
                LANGFUSE_OBSERVATION_TYPE: "generation",
            },
        )
        state["generation"] = generation

    def _on_model_parsed(self, agent, task_state, payload):
        state = self._require_run(task_state)
        generation = state.get("generation")
        if generation is None:
            raise RuntimeError("model_parsed 之前没有 model_requested，generation 生命周期对不上")
        completion_metadata = payload.get("completion_metadata") or {}
        input_tokens = completion_metadata.get("input_tokens")
        output_tokens = completion_metadata.get("output_tokens")
        if isinstance(input_tokens, int):
            generation.set_attribute(self._gen_ai.GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
        if isinstance(output_tokens, int):
            generation.set_attribute(self._gen_ai.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)
        cache_read_tokens = completion_metadata.get("cache_read_tokens")
        if isinstance(cache_read_tokens, int):
            generation.set_attribute("pico.completion.cache_read_tokens", cache_read_tokens)
        generation.set_attribute("pico.completion.cache_hit", bool(completion_metadata.get("cache_hit")))
        generation.set_attribute("pico.parse.kind", str(payload.get("kind")))
        generation.end(end_time=_iso_to_ns(payload["created_at"]))
        state["generation"] = None

    def _on_tool_executed(self, agent, task_state, payload):
        gen_ai = self._gen_ai
        span, end_ns = self._start_event_span(
            agent,
            task_state,
            payload,
            f"tool.{payload.get('name')}",
            extra_attributes={
                gen_ai.GEN_AI_OPERATION_NAME: "execute_tool",
                gen_ai.GEN_AI_TOOL_NAME: str(payload.get("name")),
                gen_ai.GEN_AI_TOOL_CALL_ARGUMENTS: json.dumps(payload.get("args") or {}, ensure_ascii=False),
                gen_ai.GEN_AI_TOOL_CALL_RESULT: str(payload.get("result", "")),
                LANGFUSE_OBSERVATION_TYPE: "tool",
            },
        )
        span.end(end_time=end_ns)

    def _on_runtime_identity_mismatch(self, agent, task_state, payload):
        from opentelemetry.trace import StatusCode

        span, end_ns = self._start_event_span(agent, task_state, payload, "runtime_identity_mismatch")
        span.set_status(StatusCode.ERROR, "runtime identity mismatch")
        span.end(end_time=end_ns)

    def _on_run_finished(self, agent, task_state, payload):
        state = self._runs.pop(task_state.run_id)
        generation = state.get("generation")
        if generation is not None:
            # 模型调用还没收口 run 就结束了（比如步数上限），先把 generation 关掉，
            # 否则后端会留一条永远不结束的 span。
            generation.end(end_time=_iso_to_ns(payload["created_at"]))
        root = state["root"]
        root.set_attribute("pico.run.status", str(payload.get("status")))
        root.set_attribute("pico.run.stop_reason", str(payload.get("stop_reason")))
        root.set_attribute("pico.run.final_answer", str(payload.get("final_answer", "")))
        root.end(end_time=_iso_to_ns(payload["created_at"]))
        self.provider.force_flush()

    def _on_generic(self, agent, task_state, payload):
        span, end_ns = self._start_event_span(agent, task_state, payload, payload["event"])
        span.end(end_time=end_ns)


def tracer_from_env():
    backend = os.environ.get(TRACING_ENV_VAR, "").strip().lower()
    if not backend:
        return NoopTracer()
    if backend != "otel":
        raise RuntimeError(f"未知的 {TRACING_ENV_VAR} 取值：{backend}（当前支持：otel）")
    rate = parse_sample_rate(os.environ.get(TRACING_SAMPLE_RATE_ENV_VAR, ""))
    if rate == 0.0:
        # 采样率为 0 等于彻底关闭：不建连接，也不做 collector 探测。
        return NoopTracer()
    endpoint = os.environ.get(OTEL_ENDPOINT_ENV_VAR, DEFAULT_OTEL_ENDPOINT).strip()
    headers = _parse_headers(os.environ.get(OTEL_HEADERS_ENV_VAR, ""))
    tracer = OtelTracer(endpoint=endpoint, headers=headers)
    if rate >= 1.0:
        return tracer
    return SamplingTracer(tracer, rate)
