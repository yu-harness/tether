var SANDBOX_CASES = [
  {
    name: "容器内标识",
    command: "uname -s; id -u; echo home=$HOME",
    output: "Linux\n0\nhome=/tmp",
    note: "容器是 Linux，进入容器的是 root，临时目录指向可写的那一块。"
  },
  {
    name: "工作区可写",
    command: "printf 'sandbox-marker\\n' > sandbox-marker.txt; ls -l sandbox-marker.txt",
    output: "-rw-r--r--    1 root     root            15 Oct 11 00:55 sandbox-marker.txt",
    note: "工作区是唯一可写的宿主路径，写入后宿主机上能看到同一个文件。"
  },
  {
    name: "根文件系统只读",
    command: "printf x > /etc/should-fail 2>&1 || echo blocked-write-to-etc",
    output: "blocked-write-to-etc",
    note: "根文件系统以只读方式挂载，容器里改不了系统文件。"
  },
  {
    name: "无网络",
    command: "wget -q -T 3 -O - http://example.com 2>&1 || echo blocked-network",
    output: "wget: bad address 'example.com'\nblocked-network",
    note: "--network none 之后容器内没有网络接口，域名也解析不了。"
  },
  {
    name: "挂载边界",
    command: "cat /workspace/../host-sentinel.txt 2>&1 || echo blocked-outside-mount",
    output: "cat: can't open '/workspace/../host-sentinel.txt': No such file or directory\nblocked-outside-mount",
    note: "宿主机在工作区上一级放了哨兵文件，容器内看不见它。"
  },
  {
    name: "超时清理",
    command: "sleep 30",
    output: "超时上限 6 秒，实际耗时 7.09 秒终止\ndocker ps -a 残留容器：0",
    note: "超时后显式 docker rm -f，不留后台容器。"
  }
];

var TOOL_GATES = [
  {
    name: "list_files",
    risky: false,
    checks: ["路径解析后必须位于工作区之内", "目标必须是目录"],
    refusals: ["path is not a directory", "path escapes workspace: ../outside"]
  },
  {
    name: "read_file",
    risky: false,
    checks: ["路径解析后必须位于工作区之内", "目标必须是文件", "行号区间必须合法（start ≥ 1，end ≥ start）"],
    refusals: ["path is not a file", "invalid line range"]
  },
  {
    name: "search",
    risky: false,
    checks: ["关键字不能为空", "路径解析后必须位于工作区之内"],
    refusals: ["pattern must not be empty"]
  },
  {
    name: "run_shell",
    risky: true,
    checks: [
      "命令不能为空，超时上限 20 秒、可用区间 1 到 120 秒",
      "标记为高风险，必须过审批闸口",
      "只读运行模式下审批一律拒绝",
      "TETHER_SANDBOX=docker 时在一次性容器里执行"
    ],
    refusals: ["command must not be empty", "timeout must be in [1, 120]", "approval denied for run_shell"]
  },
  {
    name: "write_file",
    risky: true,
    checks: ["目标不能是目录", "必须带 content", "标记为高风险，必须过审批闸口"],
    refusals: ["path is a directory", "missing content", "approval denied for write_file"]
  },
  {
    name: "patch_file",
    risky: true,
    checks: ["目标必须是已存在的文件", "old_text 必须精确命中且只出现一次", "标记为高风险，必须过审批闸口"],
    refusals: ["old_text must occur exactly once, found 2", "approval denied for patch_file"]
  },
  {
    name: "delegate",
    risky: false,
    checks: ["任务描述不能为空", "子代理深度不能超过上限（默认 1 层）", "子代理只读"],
    refusals: ["delegate depth exceeded"]
  }
];

var MCP_CALLS = [
  {
    name: "工具发现",
    request: "list_tools",
    output: "list_files · Tether 的只读工具集\nread_file · 参数：path / start / end\nsearch · 参数：pattern / path",
    error: false
  },
  {
    name: "列目录",
    request: 'list_files {"path": "tether"}',
    output: "[F] tether\\mcp_server.py\n[F] tether\\runtime.py\n[F] tether\\tools.py\n（共 22 个文件与目录）",
    error: false
  },
  {
    name: "读文件",
    request: 'read_file {"path": "README.md", "start": 1, "end": 8}',
    output: "# README.md\n   1: # tether\n   2: \n   3: `tether` 是一个面向代码仓库的轻量本地 coding agent。",
    error: false
  },
  {
    name: "检索",
    request: 'search {"pattern": "def validate_tool", "path": "tether"}',
    output: "tether\\runtime.py:580:    def validate_tool(self, name, args):\ntether\\tools.py:86:def validate_tool(context, name, args):",
    error: false
  },
  {
    name: "越界路径",
    request: 'read_file {"path": "../outside.txt"}',
    output: "Error executing tool read_file: path escapes workspace: ../outside.txt",
    error: true
  },
  {
    name: "空关键字",
    request: 'search {"pattern": "   "}',
    output: "Error executing tool search: pattern must not be empty",
    error: true
  }
];

var LOADTEST_ROWS = [
  { concurrency: 1, cache: false, throughput: 2.41, p50: 2252.57, p95: 3155.75, hitRate: 0.0, hitP50: null, missP50: 2252.57 },
  { concurrency: 1, cache: true, throughput: 3.71, p50: 1589.79, p95: 3620.96, hitRate: 0.5, hitP50: 0.05, missP50: 2763.41 },
  { concurrency: 4, cache: false, throughput: 2.13, p50: 2689.82, p95: 3560.29, hitRate: 0.0, hitP50: null, missP50: 2689.82 },
  { concurrency: 4, cache: true, throughput: 3.68, p50: 1446.17, p95: 3515.86, hitRate: 0.5, hitP50: 0.07, missP50: 2994.73 },
  { concurrency: 8, cache: false, throughput: 2.04, p50: 2860.12, p95: 3743.15, hitRate: 0.0, hitP50: null, missP50: 2860.12 },
  { concurrency: 8, cache: true, throughput: 3.9, p50: 1553.66, p95: 3313.05, hitRate: 0.5, hitP50: 0.07, missP50: 2770.63 }
];

var OWASP_ITEMS = [
  {
    title: "功能过多",
    measures: "工具集是显式注册的白名单，只有六个基础工具；每次运行还能再收窄（任务级 allowed_tools 子集）；子代理最深一层且只读；对外暴露的 MCP 面只有三个只读工具。",
    missing: "没有工具数量的运行时上限，也没有「这个任务是否真需要写权限」的自动判定，目前靠调用方传参数。"
  },
  {
    title: "权限过多",
    measures: "所有文件类工具先过路径边界检查；写操作与 shell 标为高风险并强制审批；只读模式下审批一律拒绝；环境变量走允许清单；容器内去掉全部 capability、禁止提权、断网、根文件系统只读。",
    missing: "容器隔离只覆盖 run_shell，写文件仍然直接写宿主机；镜像名没有校验；网络只有全断一档，没有受限白名单那一档。"
  },
  {
    title: "自主度过高",
    measures: "主循环有步数预算、重试上限与重复调用拦截；停机原因是显式记录的，不靠模型自称结束；高风险动作要过审批闸口；恢复前校验文件新鲜度与工作区指纹，不盲信旧检查点。",
    missing: "审批结论只进 trace，没有单独归档成审计事件；不可逆动作没有二次确认；容器运行时长与次数没有配额统计。"
  }
];

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderTabButtons(container, items, onSelect) {
  items.forEach(function (item, index) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "tab" + (index === 0 ? " tab-active" : "");
    button.textContent = item.label;
    button.addEventListener("click", function () {
      Array.prototype.forEach.call(container.querySelectorAll(".tab"), function (node) {
        node.classList.remove("tab-active");
      });
      button.classList.add("tab-active");
      onSelect(index);
    });
    container.appendChild(button);
  });
}

function renderSandbox() {
  var tabs = document.getElementById("sandbox-tabs");
  var body = document.getElementById("sandbox-body");
  var items = SANDBOX_CASES.map(function (item) {
    return { label: item.name };
  });
  function show(index) {
    var item = SANDBOX_CASES[index];
    body.innerHTML =
      '<div class="cmd-title">命令</div>' +
      '<pre class="cmd-block"><code>' + escapeHtml(item.command) + "</code></pre>" +
      '<div class="cmd-title">容器内输出</div>' +
      '<pre class="cmd-block"><code>' + escapeHtml(item.output) + "</code></pre>" +
      '<p class="panel-note">' + escapeHtml(item.note) + "</p>";
  }
  renderTabButtons(tabs, items, show);
  show(0);
}

function renderTools() {
  var tabs = document.getElementById("tools-tabs");
  var body = document.getElementById("tools-body");
  var items = TOOL_GATES.map(function (item) {
    return { label: item.name };
  });
  function show(index) {
    var item = TOOL_GATES[index];
    var checks = item.checks.map(function (text) {
      return "<li>" + escapeHtml(text) + "</li>";
    }).join("");
    var refusals = item.refusals.map(function (text) {
      return "<li><code>" + escapeHtml(text) + "</code></li>";
    }).join("");
    body.innerHTML =
      '<p class="panel-note">' +
      (item.risky
        ? '<span class="badge-err">高风险，必须过审批闸口</span>'
        : '<span class="badge-ok">只读，直接放行</span>') +
      "</p>" +
      '<div class="cmd-title">执行网关的检查项</div><ul class="panel-list">' + checks + "</ul>" +
      '<div class="cmd-title">实际会出现这些拒绝</div><ul class="panel-list">' + refusals + "</ul>";
  }
  renderTabButtons(tabs, items, show);
  show(0);
}

function renderMcp() {
  var tabs = document.getElementById("mcp-tabs");
  var body = document.getElementById("mcp-body");
  var items = MCP_CALLS.map(function (item) {
    return { label: item.name };
  });
  function show(index) {
    var item = MCP_CALLS[index];
    body.innerHTML =
      '<div class="cmd-title">请求</div>' +
      '<pre class="cmd-block"><code>' + escapeHtml(item.request) + "</code></pre>" +
      '<div class="cmd-title">' + (item.error ? "错误回传" : "返回值") + "</div>" +
      '<pre class="cmd-block"><code>' + escapeHtml(item.output) + "</code></pre>";
  }
  renderTabButtons(tabs, items, show);
  show(0);
}

function renderLoadtest() {
  var tabs = document.getElementById("loadtest-tabs");
  var body = document.getElementById("loadtest-body");
  function show(index) {
    var row = LOADTEST_ROWS[index];
    var hit = row.hitP50 === null ? "无命中" : row.hitP50 + " 毫秒";
    body.innerHTML =
      '<div class="metrics-grid">' +
      '<div class="metric-card"><div class="metric-value">' + row.throughput + '</div><div class="metric-label">吞吐（请求/秒）</div></div>' +
      '<div class="metric-card"><div class="metric-value">' + row.p50 + '</div><div class="metric-label">P50 单请求延迟（毫秒）</div></div>' +
      '<div class="metric-card"><div class="metric-value">' + row.p95 + '</div><div class="metric-label">P95 单请求延迟（毫秒）</div></div>' +
      '<div class="metric-card"><div class="metric-value">' + hit + '</div><div class="metric-label">命中缓存的请求 P50</div></div>' +
      "</div>" +
      '<p class="panel-note">缓存命中率 ' + row.hitRate * 100 + '%，未命中请求 P50 ' + row.missP50 +
      " 毫秒。并发度提高没有换来吞吐增长，瓶颈来自每次请求重建工作区事实的那几次 git 子进程；" +
      "只读任务的回答缓存命中后不再重建，命中请求的延迟降到毫秒以下。</p>";
  }
  var items = LOADTEST_ROWS.map(function (row) {
    return { label: "并发 " + row.concurrency + " · 缓存" + (row.cache ? "开" : "关") };
  });
  renderTabButtons(tabs, items, show);
  show(0);
}

function renderOwasp() {
  var container = document.getElementById("owasp-list");
  OWASP_ITEMS.forEach(function (item) {
    var block = document.createElement("div");
    block.className = "owasp-item";
    block.innerHTML =
      "<h4>" + escapeHtml(item.title) + "</h4>" +
      '<div class="cmd-title">现有措施</div><p class="panel-note">' + escapeHtml(item.measures) + "</p>" +
      '<div class="cmd-title">还缺的地方</div><p class="panel-note">' + escapeHtml(item.missing) + "</p>";
    container.appendChild(block);
  });
}

document.addEventListener("DOMContentLoaded", function () {
  if (!document.getElementById("boundary")) {
    return;
  }
  renderSandbox();
  renderTools();
  renderMcp();
  renderLoadtest();
  renderOwasp();
});
