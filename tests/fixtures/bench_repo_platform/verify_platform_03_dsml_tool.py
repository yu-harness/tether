import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["PICO_BENCHMARK_REPO_ROOT"])

from pico.runtime import Pico

root = Path.cwd()
hello = root / "hello.py"
assert hello.is_file(), "脚本化模型给出的 DSML 工具调用没有变成文件写入"
assert hello.read_text(encoding="utf-8") == 'print("hello word")\n', hello.read_text(encoding="utf-8")

dsml = (
    '<|DSML| calls>\n'
    '<|DSML| invoke name="write_file" path="hello.py"><content>print("hello word")\n</content></tool>'
)
payload = Pico.parse_dsml_tool(dsml)
assert payload == {
    "name": "write_file",
    "args": {"path": "hello.py", "content": 'print("hello word")\n'},
}, payload

run_dir = next((root / ".pico" / "runs").glob("*"))
events = [
    json.loads(line)
    for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
writes = [
    event
    for event in events
    if event.get("event") == "tool_executed" and event.get("name") == "write_file"
]
assert writes, events

print("platform regression 03 ok")
