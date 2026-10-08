import subprocess
import sys
from pathlib import Path

import mini_tether


def test_mini_tether_module_and_public_exports():
    assert mini_tether.Tether is not None
    assert mini_tether.FakeModelClient is not None
    assert not hasattr(mini_tether, "MiniAgent")
    result = subprocess.run([sys.executable, "-m", "mini_tether", "--help"], capture_output=True, text=True, check=True)
    assert "Teaching-sized Tether agent harness" in result.stdout


def test_readme_main_mapping_points_to_existing_files():
    repo_root = Path(__file__).resolve().parents[3]
    main_files = [
        "tether/cli.py",
        "tether/runtime.py",
        "tether/agent_loop.py",
        "tether/context_manager.py",
        "tether/providers/clients.py",
        "tether/tool_executor.py",
        "tether/tools.py",
        "tether/task_state.py",
        "tether/run_store.py",
        "tether/workspace.py",
    ]
    for path in main_files:
        assert (repo_root / path).exists()
