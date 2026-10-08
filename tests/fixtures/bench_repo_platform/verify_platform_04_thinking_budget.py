import json
import os
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, os.environ["TETHER_BENCHMARK_REPO_ROOT"])

from tether.providers.clients import AnthropicCompatibleModelClient

received = []
state = {"first": True}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        received.append(json.loads(self.rfile.read(length).decode("utf-8")))
        if state["first"]:
            state["first"] = False
            # 第一次响应只有 thinking 块：正文缺失正是输出预算被思考吃满的表现。
            payload = {
                "content": [{"type": "thinking", "thinking": "很长的推理过程"}],
                "stop_reason": "max_tokens",
            }
        else:
            payload = {
                "content": [{"type": "text", "text": "<final>ok</final>"}],
                "stop_reason": "end_turn",
            }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        return


server = HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
port = server.server_address[1]
# 环境里的 HTTP 代理会把本机回环请求也带走，这里显式装一个空代理的 opener。
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))


def client(thinking_disabled):
    return AnthropicCompatibleModelClient(
        model="deepseek-flash",
        base_url=f"http://127.0.0.1:{port}",
        api_key="sk-platform-regression",
        temperature=0.0,
        timeout=30,
        thinking_disabled=thinking_disabled,
    )


guard_message = ""
try:
    client(False).complete("hello", 64)
except RuntimeError as exc:
    guard_message = str(exc)
assert guard_message, "只有 thinking 没有 text 时必须报错，不能静默返回空文本"
assert "占满了输出预算" in guard_message, guard_message
assert "--max-new-tokens" in guard_message, guard_message

assert client(True).complete("hello", 64) == "<final>ok</final>"
assert received[1].get("thinking") == {"type": "disabled"}, received[1]
assert received[0].get("thinking") is None, received[0]

server.shutdown()

print("platform regression 04 ok")
