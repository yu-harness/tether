import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.environ["PICO_BENCHMARK_REPO_ROOT"])

from pico.run_store import RunStore
from pico.task_state import TaskState

root = Path.cwd()
store = RunStore(root / "atomic-runs")
state = TaskState.create(task_id="task_lock", user_request="lock the target", run_id="run_lock")
store.start_run(state)
target = store.task_state_path(state.run_id)

if os.name == "nt":
    # Windows 上持有目标文件句柄会让 os.replace 持续抛 PermissionError，
    # 与 Defender / 索引服务的扫描锁表现一致。
    handle = target.open("r", encoding="utf-8")
    started = time.monotonic()
    blocked = False
    try:
        store.write_task_state(state)
    except PermissionError:
        blocked = True
    finally:
        handle.close()
    elapsed = time.monotonic() - started
    assert blocked, "目标文件被占用时应当抛出 PermissionError"
    # 5 次退避合计 0.75s，耗时下限证明退避重试确实跑满而不是直接抛出。
    assert elapsed >= 0.7, elapsed

store.write_task_state(state)
assert json.loads(target.read_text(encoding="utf-8"))["run_id"] == "run_lock"

print("platform regression 05 ok")
