import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import pico.cli as cli_module
import pico.evaluation.metrics as metrics_module
from pico import AnthropicCompatibleModelClient, Pico, WorkspaceContext
from pico.config import load_project_env
from pico.evaluation.metrics import (
    _build_memory_experiment_agent,
    _build_recovery_agent,
    _security_agent,
)
from pico.run_store import RunStore
from pico.task_state import TaskState
from pico.tool_context import ToolContext
from pico.tools import tool_run_shell, tool_search


def _tool_context(tmp_path):
    return ToolContext(
        root=tmp_path,
        path_resolver=lambda raw_path: (tmp_path / raw_path).resolve(),
        shell_env_provider=lambda: dict(os.environ),
        depth=0,
        max_depth=1,
        spawn_delegate=lambda args: "unused",
    )


# ---------------------------------------------------------------------------
# 01 中文路径 GBK 解码崩：git/rg 永远输出 UTF-8，解码失败不能崩、不能出乱码
# ---------------------------------------------------------------------------


def test_workspace_build_decodes_git_toplevel_as_utf8_on_chinese_path(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git 不可用，无法复现 rev-parse 解码路径")
    # 中文目录名自带非 ASCII 字节；在 zh_dir 里直接 git init，
    # 最近的 .git 就是它自己，repo_root 不会被上层仓库吞掉，
    # 因此这里可以安全走 git 探测路径（正是 bug 01 出事的代码路径）。
    zh_dir = tmp_path / "中文工作区"
    zh_dir.mkdir()
    (zh_dir / "README.md").write_text("demo\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=zh_dir, check=True, capture_output=True)

    workspace = WorkspaceContext.build(zh_dir)

    # GBK 误解码时 repo_root 会变成乱码路径，relative_to 直接抛 ValueError；
    # 修复后必须解析回真实存在的中文目录。
    assert Path(workspace.repo_root) == zh_dir.resolve()
    assert Path(workspace.repo_root).is_dir()


def test_tool_search_rg_decodes_utf8_match_lines(tmp_path):
    if shutil.which("rg") is None:
        pytest.skip("rg 不可用，走不到 rg 解码路径")
    (tmp_path / "notes.txt").write_text("部署密钥是红色\n第二行\n", encoding="utf-8")

    result = tool_search(_tool_context(tmp_path), {"pattern": "部署密钥", "path": "."})

    # GBK 误解码时匹配行会变成乱码，原文子串就对不上了
    assert "部署密钥是红色" in result


def test_run_shell_replaces_undecodable_output_bytes(tmp_path):
    # 命令输出混入任何编码都解不了的非法字节时，errors="replace" 必须兜住，
    # 不能整轮抛 UnicodeDecodeError。
    (tmp_path / "emit_bytes.py").write_text(
        "import sys\nsys.stdout.buffer.write(b'ok\\xff\\xfeend')\n",
        encoding="utf-8",
    )

    result = tool_run_shell(
        _tool_context(tmp_path),
        {"command": f'"{sys.executable}" "emit_bytes.py"', "timeout": 20},
    )

    assert "exit_code: 0" in result


# ---------------------------------------------------------------------------
# 02 .env 放子目录不生效：load_project_env 必须从 workspace.cwd 起步
# ---------------------------------------------------------------------------


def test_load_project_env_anchors_to_workspace_cwd_not_repo_root(tmp_path):
    repo_root = tmp_path / "repo"
    nested = repo_root / "sub" / "proj"
    nested.mkdir(parents=True)
    (nested / ".env").write_text("PICO_REGRESSION_NESTED_ENV=nested-value\n", encoding="utf-8")
    workspace = WorkspaceContext.build(nested, repo_root_override=repo_root)

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PICO_REGRESSION_NESTED_ENV", None)
        loaded = load_project_env(workspace.cwd, override=False)

        assert loaded == {"PICO_REGRESSION_NESTED_ENV": "nested-value"}
        assert os.environ["PICO_REGRESSION_NESTED_ENV"] == "nested-value"
        # 旧口径从 repo_root 出发只会向上找，永远看不到子目录里的 .env
        assert "PICO_REGRESSION_NESTED_ENV" not in load_project_env(workspace.repo_root, override=False)

    # 把 cli.py 的锚定口径钉死：起点必须是 workspace.cwd 且 override=False，
    # 改回 workspace.repo_root 或漏掉 override 参数都会让这条断言失败。
    cli_source = inspect.getsource(cli_module)
    assert "load_project_env(workspace.cwd, override=False)" in cli_source


# ---------------------------------------------------------------------------
# 03 DSML 工具标记解析：parse_dsml_tool / looks_like_malformed_tool 直接用例
# （Pico.parse 整链路的 malformed 降级已由 test_pico.py 覆盖，这里补直接覆盖面）
# ---------------------------------------------------------------------------


def test_parse_dsml_tool_write_file_with_content_tag():
    raw = (
        '<|DSML| calls>\n'
        '<|DSML| invoke name="write_file" path="hello.py"><content>print("hello word")\n</content></tool>'
    )

    payload = Pico.parse_dsml_tool(raw)

    assert payload == {
        "name": "write_file",
        "args": {"path": "hello.py", "content": 'print("hello word")\n'},
    }


def test_parse_dsml_tool_read_file_uses_attributes_as_args():
    raw = '<|DSML| invoke name="read_file" path="README.md">'

    payload = Pico.parse_dsml_tool(raw)

    assert payload == {"name": "read_file", "args": {"path": "README.md"}}


def test_parse_dsml_tool_strips_copied_tool_close_tag_from_body():
    # 模型抄示例抄来的 </tool> 结尾必须剥掉，正文整体当 content
    raw = '<|DSML| invoke name="write_file" path="a.py">print("hi")\n</tool>'

    payload = Pico.parse_dsml_tool(raw)

    assert payload == {"name": "write_file", "args": {"path": "a.py", "content": 'print("hi")'}}


def test_parse_dsml_tool_returns_none_for_unrecognized_shape():
    assert Pico.parse_dsml_tool("<|DSML| calls>") is None
    # 有 invoke 但缺 name，认不出来
    assert Pico.parse_dsml_tool('<|DSML| invoke path="a.py">') is None
    assert Pico.parse_dsml_tool("just a plain answer") is None


def test_parse_translates_dsml_output_into_tool_action():
    raw = '<|DSML| calls>\n<|DSML| invoke name="read_file" path="README.md">'

    kind, payload = Pico.parse(raw)

    assert kind == "tool"
    assert payload == {"name": "read_file", "args": {"path": "README.md"}}


def test_looks_like_malformed_tool_flags_known_tool_names_only():
    assert Pico.looks_like_malformed_tool('<invoke name="read_file" path="x">') is True
    assert Pico.looks_like_malformed_tool("plain final answer") is False
    # 没有尖括号、只出现工具名，不算疑似工具调用（保守识别）
    assert Pico.looks_like_malformed_tool('name="read_file" without brackets') is False


# ---------------------------------------------------------------------------
# 04 思考模式吃满输出预算：thinking_disabled 开关与可读的错误信息
# ---------------------------------------------------------------------------


class _FakeAnthropicResponse:
    def __init__(self, data):
        self.headers = {"Content-Type": "application/json"}
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._data).encode("utf-8")


def _anthropic_client(thinking_disabled):
    return AnthropicCompatibleModelClient(
        model="deepseek-flash",
        base_url="https://api.deepseek.com/anthropic",
        api_key="sk-test",
        temperature=0.0,
        timeout=30,
        thinking_disabled=thinking_disabled,
    )


def test_anthropic_client_sends_thinking_disabled_only_when_enabled():
    captured = []

    def fake_urlopen(request, timeout):
        captured.append(json.loads(request.data.decode("utf-8")))
        return _FakeAnthropicResponse({"content": [{"type": "text", "text": "<final>ok</final>"}]})

    with patch("urllib.request.urlopen", fake_urlopen):
        assert _anthropic_client(thinking_disabled=True).complete("hello", 64) == "<final>ok</final>"
        assert _anthropic_client(thinking_disabled=False).complete("hello", 64) == "<final>ok</final>"

    assert captured[0]["thinking"] == {"type": "disabled"}
    assert "thinking" not in captured[1]


def test_anthropic_client_explains_output_budget_consumed_by_thinking():
    def fake_urlopen(request, timeout):
        return _FakeAnthropicResponse(
            {
                "content": [{"type": "thinking", "thinking": "很长的推理过程"}],
                "stop_reason": "max_tokens",
            }
        )

    with patch("urllib.request.urlopen", fake_urlopen):
        with pytest.raises(RuntimeError) as excinfo:
            _anthropic_client(thinking_disabled=False).complete("hello", 64)

    message = str(excinfo.value)
    # 有 thinking 但没有 text 时，错误信息必须点明预算被思考占满，并给出两条出路
    assert "思考模式占满了输出预算" in message
    assert "--max-new-tokens" in message
    assert "关闭思考模式" in message


# ---------------------------------------------------------------------------
# 05 Windows 原子写 PermissionError 退避重试：5 次都失败才抛
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="只有 Windows 上被打开的目标文件才会挡住 replace")
def test_write_json_atomic_retries_with_backoff_then_raises_on_locked_target(tmp_path):
    store = RunStore(tmp_path / "runs")
    state = TaskState.create(run_id="run_lock", task_id="task_lock", user_request="lock the target")
    store.start_run(state)
    target = store.task_state_path(state.run_id)

    # 持有目标文件的读句柄：Windows 上不带 FILE_SHARE_DELETE 打开的文件会让
    # replace 持续抛 PermissionError，模拟 Defender/索引服务的扫描锁。
    handle = target.open("r", encoding="utf-8")
    started = time.monotonic()
    try:
        with pytest.raises(PermissionError):
            store.write_task_state(state)
    finally:
        handle.close()
    elapsed = time.monotonic() - started

    # 5 次退避 0.05+0.10+0.15+0.20+0.25 = 0.75s，必须重试满 5 次才抛，
    # 用耗时下限证明没有 fail-fast。
    assert elapsed >= 0.7

    # 锁释放后同一路径立刻恢复可写，验证不是路径本身坏了
    store.write_task_state(state)
    assert json.loads(target.read_text(encoding="utf-8"))["run_id"] == "run_lock"


# ---------------------------------------------------------------------------
# 06 实验工作区 repo_root 被 git 向上吞：metrics 的构建函数必须显式锚定
# ---------------------------------------------------------------------------


def test_metrics_agent_builders_anchor_repo_root_inside_outer_git_repo(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git 不可用，无法复现向上吞 repo_root 的场景")
    # 父链存在 .git（outer 是仓库），实验工作区在它下面；
    # 不显式锚定的话 repo_root 会被解析成 outer，fixture 文件全部读不到。
    outer = tmp_path / "outer"
    workspace_root = outer / "nested" / "workspace"
    workspace_root.mkdir(parents=True)
    (workspace_root / "README.md").write_text("demo\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=outer, check=True, capture_output=True)

    security_agent = _security_agent(workspace_root)
    memory_agent = _build_memory_experiment_agent(workspace_root, "deploy key is red", "facts.txt")
    recovery_agent = _build_recovery_agent(workspace_root, ["fragment"])

    for agent in (security_agent, memory_agent, recovery_agent):
        assert Path(agent.workspace.repo_root) == workspace_root.resolve()
        assert Path(agent.workspace.repo_root) != outer.resolve()


def test_metrics_module_always_passes_repo_root_override():
    # bug 06 的失败模式是"漏传 repo_root_override"：
    # 这里直接钉死 metrics.py 里每一处 WorkspaceContext.build 调用都必须显式锚定。
    source = Path(metrics_module.__file__).read_text(encoding="utf-8")
    build_calls = re.findall(r"WorkspaceContext\.build\([^)]*\)", source)

    assert len(build_calls) == 6
    for call in build_calls:
        assert "repo_root_override=" in call
