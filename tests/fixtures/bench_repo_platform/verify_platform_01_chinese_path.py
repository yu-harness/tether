import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.environ["TETHER_BENCHMARK_REPO_ROOT"])

from tether.tool_context import ToolContext
from tether.tools import tool_search
from tether.workspace import WorkspaceContext

root = Path.cwd()
zh_dir = root / "中文工作区"
zh_dir.mkdir(exist_ok=True)
(zh_dir / "README.md").write_text("中文工作区说明\n", encoding="utf-8")
(zh_dir / "notes.txt").write_text("部署密钥是红色\n第二行\n", encoding="utf-8")

# 缺陷 01 出事的路径：无 repo_root_override 时靠 git 向上探测仓库根，
# git 输出 UTF-8，中文 Windows 按 GBK 解码会让仓库根变成乱码。
assert shutil.which("git"), "缺陷 01 的复现依赖 git 探测仓库根"
subprocess.run(["git", "init", "-q"], cwd=zh_dir, check=True, capture_output=True)

workspace = WorkspaceContext.build(zh_dir)
assert Path(workspace.repo_root) == zh_dir.resolve(), workspace.repo_root
assert Path(workspace.repo_root).is_dir()

context = ToolContext(
    root=zh_dir,
    path_resolver=lambda raw_path: (zh_dir / raw_path).resolve(),
    shell_env_provider=lambda: dict(os.environ),
    depth=0,
    max_depth=1,
    spawn_delegate=lambda args: "unused",
)
# rg 可用时走 rg 分支，不可用时走 Python 回退分支，两条路径都不能出乱码。
result = tool_search(context, {"pattern": "部署密钥", "path": "."})
assert "部署密钥是红色" in result, result

print("platform regression 01 ok")
