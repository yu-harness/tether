import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo_root = Path(os.environ["PICO_BENCHMARK_REPO_ROOT"])
sys.path.insert(0, str(repo_root))

from pico.evaluation import metrics as metrics_module
from pico.evaluation.metrics import (
    _build_memory_experiment_agent,
    _build_recovery_agent,
    _security_agent,
)

root = Path.cwd()
outer = root / "outer_repo"
workspace_root = outer / "nested" / "workspace"
workspace_root.mkdir(parents=True, exist_ok=True)
(workspace_root / "README.md").write_text("platform regression\n", encoding="utf-8")

# 缺陷 06 的场景：实验工作区在别的 git 仓库下面，靠 git 向上探测会把上层仓库当成根。
assert shutil.which("git"), "缺陷 06 的复现依赖 git 向上探测仓库根"
subprocess.run(["git", "init", "-q"], cwd=outer, check=True, capture_output=True)

agents = (
    _security_agent(workspace_root),
    _build_memory_experiment_agent(workspace_root, "deploy key is red", "facts.txt"),
    _build_recovery_agent(workspace_root, ["fragment"]),
)
for agent in agents:
    assert Path(agent.workspace.repo_root) == workspace_root.resolve(), agent.workspace.repo_root
    assert Path(agent.workspace.repo_root) != outer.resolve()

# 失败模式是漏传 repo_root_override，这里对 metrics.py 的每一处调用都要求显式锚定。
source = Path(metrics_module.__file__).read_text(encoding="utf-8")
build_calls = re.findall(r"WorkspaceContext\.build\([^)]*\)", source)
assert len(build_calls) == 6, build_calls
for call in build_calls:
    assert "repo_root_override=" in call, call

print("platform regression 06 ok")
