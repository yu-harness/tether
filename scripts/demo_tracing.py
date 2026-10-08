import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico import FakeModelClient, Pico, SessionStore, WorkspaceContext  # noqa: E402
from pico.tracing import tracer_from_env  # noqa: E402

# 追踪演示：在同一个 session 里跑多个 run，验证三层结构进追踪后端。
# - 每个 run 一条 trace（trace id 由 run_id 派生）
# - run 内部模型调用是 generation、工具调用是 tool span
# - 同一 session 的多个 run 共享 session.id（thread 层）
#
# 用法（Jaeger：先启动 infra/jaeger/jaeger.exe）：
#   set PICO_TRACING=otel
#   D:/Dev/miniconda3/python.exe scripts/demo_tracing.py
# 然后打开 http://localhost:16686 查 service=pico。
# 指向 Langfuse 时，追加 PICO_OTEL_ENDPOINT 与 PICO_OTEL_HEADERS，
# 取值见 .env.example 方案二，然后打开 http://localhost:3000 看 Tracing。

DEMO_WORKSPACE = ROOT / "tmp" / "tracing-demo-workspace"


def build_agent(workspace, outputs):
    store = SessionStore(workspace.repo_root + "/.pico/sessions")
    return Pico(
        model_client=FakeModelClient(outputs),
        workspace=workspace,
        session_store=store,
        approval_policy="auto",
    )


def main():
    if not os.environ.get("PICO_TRACING"):
        raise RuntimeError("PICO_TRACING 未设置，演示需要在环境变量里打开追踪（otel）")

    if DEMO_WORKSPACE.exists():
        shutil.rmtree(DEMO_WORKSPACE)
    DEMO_WORKSPACE.mkdir(parents=True)
    (DEMO_WORKSPACE / "README.md").write_text("tracing demo\n", encoding="utf-8")
    (DEMO_WORKSPACE / "note.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    workspace = WorkspaceContext.build(DEMO_WORKSPACE, repo_root_override=DEMO_WORKSPACE)

    tracer = tracer_from_env()

    # 同一个 session 里连跑三个 run：读文件、再读一次、最后直接回答。
    agent = build_agent(
        workspace,
        [
            '<tool>{"name":"read_file","args":{"path":"note.txt"}}</tool>',
            "<final>note.txt 有三行。</final>",
            '<tool>{"name":"read_file","args":{"path":"README.md"}}</tool>',
            "<final>README 是演示说明。</final>",
            "<final>不用再读文件了，直接回答。</final>",
        ],
    )
    print("session id:", agent.session["id"])
    print("run 1:", agent.ask("读一下 note.txt 有几行"))
    print("run 2:", agent.ask("README 里写了什么"))
    print("run 3:", agent.ask("还需要再读文件吗"))
    tracer.flush()
    print("session 内 run 数：3，请到追踪后端（Jaeger 查 service=pico，Langfuse 看 Tracing）核对 trace 数与 span 树。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
