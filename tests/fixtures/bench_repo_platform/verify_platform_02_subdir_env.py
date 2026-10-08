import os
import sys
from pathlib import Path

repo_root = Path(os.environ["PICO_BENCHMARK_REPO_ROOT"])
sys.path.insert(0, str(repo_root))

from pico.config import load_project_env
from pico.workspace import WorkspaceContext

root = Path.cwd()
outer = root / "env_outer"
nested = outer / "sub" / "proj"
nested.mkdir(parents=True, exist_ok=True)
(nested / ".env").write_text("PICO_PLATFORM_REGRESSION_ENV=nested-value\n", encoding="utf-8")

workspace = WorkspaceContext.build(nested, repo_root_override=outer)
os.environ.pop("PICO_PLATFORM_REGRESSION_ENV", None)

# 旧口径从 repo_root 起步只会逐级向上找，起点下面子目录里的 .env 永远看不到。
from_repo_root = load_project_env(workspace.repo_root, override=False)
assert "PICO_PLATFORM_REGRESSION_ENV" not in from_repo_root, from_repo_root

loaded = load_project_env(workspace.cwd, override=False)
assert loaded == {"PICO_PLATFORM_REGRESSION_ENV": "nested-value"}, loaded
assert os.environ["PICO_PLATFORM_REGRESSION_ENV"] == "nested-value"

# CLI 的锚定口径：起点必须是 workspace.cwd，改回 repo_root 这条断言就会失败。
cli_source = (repo_root / "pico" / "cli.py").read_text(encoding="utf-8")
assert "load_project_env(workspace.cwd, override=False)" in cli_source

print("platform regression 02 ok")
