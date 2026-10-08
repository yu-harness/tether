# Tether 实跑踩坑与修复记录

这份记录只收「真机跑起来才暴露」的问题：代码逻辑本身没写错，换个环境、换层目录、换个模型才现形。

环境：Windows + 中文路径（`D:\md\AI实习`）+ DeepSeek V4.1-Flash。

---

## 2026-09-16 · 01 中文路径下启动直接崩

**现象**：`python -m tether` 起不来，抛异常

```
File "tether/workspace.py", line 85, in build
    key = str(path.relative_to(repo_root))
ValueError: 'D:\md\AI实习\tether\tether\README.md' is not in the subpath of 'D:\md\AI瀹炰範'
```

注意 `AI瀹炰範` 是乱码。

**根因**：`WorkspaceContext.build()` 里的 `git()` 用

```python
subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
```

`text=True` 但不指定编码，就跟着系统默认走。系统是中文 Windows（cp936 / GBK），而 **git 永远输出 UTF-8**。于是 `rev-parse --show-toplevel` 返回的仓库根被按 GBK 解码，路径里的中文变成乱码，后面拿这个乱码路径做 `relative_to()` 直接抛异常。

**修复**：

- `tether/workspace.py`：`git()` 的 `subprocess.run` 加 `encoding="utf-8", errors="replace"`
- `tether/tools.py`：`rg` 搜索同因同修（否则中文匹配行会显示成乱码）
- `tether/tools.py`：`run_shell` 只加 `errors="replace"`，**不**硬编码 utf-8 —— Windows 原生命令输出多为 GBK，硬改反而会乱码，这里只需要"解码失败不要崩"

**验证**：`WorkspaceContext.build(".")` 不再抛异常，且 `repo_root` 是真实存在的目录（不只是"不报错"）。

---

## 2026-09-16 · 02 `.env` 放在子目录里不生效

**现象**：key 明明写在 `tether/tether/.env`，启动后调用模型报

```
401 ... "Your api key:  is invalid"
```

注意冒号后面是**空的**——不是 key 错，是根本没读到。

**根因**：两层叠出来的

1. `find_project_env(start)`（`tether/config.py`）是「**从起点逐级向上**找 `.env`」，只看自己和所有父目录；
2. `cli.py` 传的起点是 `workspace.repo_root`，而不是启动目录。

而 `tether/tether` 不是独立 git 仓库（`.git` 在 `D:\md\AI实习` 这一层），所以：

```
repo_root = D:\md\AI实习      → 找 D:\md\AI实习\.env   没有
                              → 找 D:\md\.env          没有
                              → 找 D:\.env             没有
                              → 放弃，key 为空

key 实际在 D:\md\AI实习\tether\tether\.env   ← 在起点下面，永远不会被看到
```

**修复**：`cli.py` 把起点从 `repo_root` 改成 `workspace.cwd`

```python
load_project_env(workspace.cwd)
```

从"你启动的目录"往上找，就近优先，`tether/tether/.env` 就是第一个命中的。这个口径和 `evaluation/metrics.py` 里本来就在用的 `load_project_env(Path.cwd())` 也一致了。

**验证**：`load_project_env(".")` 之后环境里能取到 key（只断言布尔值，不打印内容）。

**顺带发现**：`D:\md\AI实习` 的 `.gitignore` 里没有 `.env` 规则 —— 所以**不要把 `.env` 放到仓库根**，会被 git 跟踪。要么用系统环境变量，要么放在会自己 gitignore 的工作区里。

---

## 2026-09-16 · 03 新模型的工具调用标记解析不了

**现象**：给一句"在这个目录创建一个 py 文件，输出 hello word"，tether 把模型的这段文本原样打印出来，**文件没有创建**：

```
<|DSML| calls>
<|DSML| invoke name="write_file" path="hello.py"><content>print("hello word")
</content></tool>
```

**证据**：

- `.tether/runs/<run_id>/report.json`：`"attempts": 1`，`final_answer` 就是上面这段文本
- `.tether/runs/<run_id>/trace.jsonl`：`run_started → prompt_built → model_requested → model_parsed → checkpoint_created → run_finished`，**没有 `tool_executed`**

**根因**：也是两层

1. **模型层**：DeepSeek V4.1-Flash 会吐自己的特殊标记（`<|DSML| ...>` 这种带 `|` 的写法是训练期特殊 token 风格），而不是 prompt 里教的 `<tool>`。它甚至抄了示例的结尾 `</tool>`，属于"想调工具但格式学串了"。
2. **代码层**：`Tether.parse()` 的判定链只认字面量 `<tool>` 和 `<tool`，两个都不匹配、也没有 `<final>`，最后落到兜底「**非空文本 = 最终答案**」—— 于是一次工具调用被静默吞掉。

**修复**（`tether/runtime.py`）：

- 新增 `parse_dsml_tool(raw)`：把 `<|DSML| invoke name="..." path="...">` 翻译成标准 `{"name": ..., "args": {...}}`，属性当参数、`<content>` 之类的子标签也认，最后剥掉模型抄来的 `</tool>`；形状认不出时返回 `None`，不影响后续判断
- 新增 `looks_like_malformed_tool(raw)`：保守识别「像是想调工具，但格式没被认出来」，只检查是否出现已知工具名，不猜参数
- 兜底逻辑改成：**疑似工具调用 → `retry`**（让模型按 `retry_notice()` 里的正确格式重写），只有真的不像工具调用才当最终答案

**验证**：6 个 case 全部符合预期

```
[tool ]  DSML write_file        → {'name': 'write_file', 'args': {'path': 'hello.py', 'content': 'print("hello word")\n'}}
[tool ]  DSML read_file         → {'name': 'read_file', 'args': {'path': 'README.md'}}
[tool ]  原有 XML 格式          → 正常
[tool ]  原有 JSON 格式         → 正常
[final]  纯文本答案             → 正常（没误伤）
[retry]  带尖括号但认不出的格式  → 降级重试
```

**没做的事**：更彻底的做法是改用 Anthropic Messages API 原生的 `tools`（function calling）参数，把格式约束交给协议而不是 prompt。当前改动只是兼容层。

---

## 2026-09-16 · 04 输出预算被"思考模式"吃满

**现象**：模型调用能通了（key 已正常），但换一个任务就报

```
Anthropic-compatible error: could not extract text from response
```

**排查过程**：写探针直接打 DeepSeek 的 Anthropic 端点，看原始响应长什么样。

```
stop_reason : end_turn
usage       : {'input_tokens': 34, 'output_tokens': 19}
  block type='thinking' len=68     ← 先思考
  block type='text'     len=2      ← 再给正文
```

响应里其实**有** `text` 块，`_extract_anthropic_text()` 也能找到它。所以问题不在解析，而在**真实 prompt 比探针长得多**：模型思考得更久，而 tether 默认 `--max-new-tokens 512` 被 `thinking` 吃光，正文 `text` 块为空 → 提取不到 → 报错。

对照实测：

```
--max-new-tokens 512    失败（同一句任务）
--max-new-tokens 4096   成功（正常读文件、正常收工）
```

**根因**：DeepSeek V4.1 系列**默认开启思考模式**，每轮响应都先输出 `thinking` 再输出正文；而 tether 每轮只给 512 tokens 的输出预算。client 里没有传任何 `thinking` 参数，等于默认接受了这个行为。

**修复**：

- `tether/cli.py`：`--max-new-tokens` 默认 512 → 2048，给思考留余量
- `tether/providers/clients.py`：`AnthropicCompatibleModelClient` 新增 `thinking_disabled` 开关，payload 里带 `"thinking": {"type": "disabled"}`；`cli.py` 的 DeepSeek 路径默认传 `True`
- `tether/providers/clients.py`：错误信息改进——响应"有 thinking 但没有 text"时，直接说明是预算被思考占满，并提示加大 `--max-new-tokens` 或关闭思考

**为什么选择关掉思考而不是只放大预算**：探针实测同一个问题

```
thinking: {"type": "disabled"}     output_tokens: 1     只有 text 块
（默认，思考开启）                   output_tokens: 38    thinking + text
```

输出差 38 倍。tether 每轮都调模型（一次任务 6~18 轮），这个成本会被放大；而它的任务多是"读文件、改文件"，不需要长推理链。所以默认关掉，需要时把开关置回 `False` 即可。

**验证**：探针确认 `thinking.type=disabled` 被 DeepSeek 端点接受、响应不再含 `thinking` 块；`--max-new-tokens 4096` 下同一句任务正常完成。

---

## 附：默认模型更新（同日）

官方文档（2026-09 口径）当前两个模型 ID：

| 模型 ID | 版本 | 上下文 | 输出 | 图像 | 并发 | 价格（输入未命中 / 输出，元每百万 token） |
| --- | --- | --- | --- | --- | --- | --- |
| `deepseek-flash` | V4.1-Flash | 1M | 384K | 支持 | 2500 | 1 / 2（空闲）、2 / 4（高峰） |
| `deepseek-v4-pro` | V4-Pro-0813 | 1M | 384K | 不支持 | 500 | 4.5 / 9.0、13.5 / 27.0 |

`deepseek-v4-pro` 并未下线（官方 2026-09-14 之后继续提供），但 flash 是新架构主力：价格约 1/4、并发更高、支持图像，所以把默认值换成了 `deepseek-flash`。

改动位置：`tether/cli.py`（`DEFAULT_DEEPSEEK_MODEL`）、`.env.example`、`README.md`、`tether/evaluation/metrics.py`、`tests/test_tether.py` 两处"测默认值"的断言。要切回 Pro：`--model deepseek-v4-pro` 或 `.env` 里写 `TETHER_DEEPSEEK_MODEL=deepseek-v4-pro`。

---

## 2026-09-16 · 05 Windows 上原子写偶发 PermissionError

**现象**：跑 benchmark 时随机崩在落盘

```
File "tether/run_store.py", line 85, in _write_json_atomic
    Path(temp_name).replace(path)
PermissionError: [WinError 5] 拒绝访问: '...task_state.json.0ioer1e5.tmp' -> '...task_state.json'
```

**根因**：Windows 上 `os.replace` 偶尔会撞上 Defender / 索引服务对新文件的短暂扫描锁，随机且间歇。

**顺带解开了之前那个"遗留问题"**：`pytest tests` 全量跑约 10 个失败、单独跑却能过（`test_run_store_writes_report_json` 报的就是 `PermissionError`），根源在这里。

**修复**（`run_store.py`）：`_write_json_atomic` 的 replace 加 5 次退避重试（`time.sleep(0.05 * (attempt + 1))`），一直失败才抛出异常，避免掩盖真正的权限问题。

**验证**：`run_ablation_experiments.py` 从"随机崩在落盘"变成可连续跑完。

---

## 2026-09-16 · 06 消融实验解析不出临时工作区

**现象**：记忆消融跑出 `memory_hit_rate = 0.0`（三个变体一模一样），跟作者基线（`0 vs 60`）完全不符。

**排查**：把 followup 轮的 prompt 打出来

```
workspace.cwd        -> C:\Users\Administrator\AppData\Local\Temp\tmp95x8emhe   ✓ 对
workspace.repo_root  -> C:\Users\Administrator                                  ✗ 错

Memory:
- file_summaries: -
- episodic_notes: 0

Transcript:
[tool:read_file] {"path": "facts.txt"}
error: invalid arguments for read_file: path is not a file
```

**根因是一条链**

```
① 用户主目录被 git init 过 → C:\Users\Administrator\.git 存在
② 实验用 tempfile 建临时工作区 → 位于 C:\Users\...\Temp 下面
③ WorkspaceContext.build(临时目录) 靠 git 向上探测 → 命中主目录那个 .git
   → repo_root 被解析成 C:\Users\Administrator
④ 工具以主目录为根 → fixture 里的文件全部读不到
⑤ 文件没读到 → 没有文件摘要进记忆 → prompt 的 Memory 段落是空的
⑥ followup 时 prompt 里没有 fact → 模型只能重复读文件 → memory_hit_rate = 0
```

**修复**（`evaluation/metrics.py` 6 处）：`WorkspaceContext.build(workspace_root)` → `WorkspaceContext.build(workspace_root, repo_root_override=workspace_root)`，显式锚定，不再依赖 git 向上探测。

`evaluator.py:452` 本来就是这么写的，这 6 处漏了：`build_stress_agent_metrics` / `_build_memory_experiment_agent` / context matrix / `_security_agent` / `_build_real_agent` / `_build_recovery_agent`。

**验证**：修复后 `memory_on repeated_reads = 0`、`memory_off = 12`（repetitions=1）；完整跑出 `60 → 0`。

**环境侧**：根因①那个主目录 `.git` 是本地误操作留下的，已删除——它会影响所有依赖上级目录探测的 git 操作。

---

## 实战复现结果（2026-09-16）

环境：Windows + 中文路径 + `deepseek-flash`（关闭思考模式）+ synthetic 模式。

命令：

```powershell
python scripts/run_ablation_experiments.py --runs-root '<靶场>\.tether\runs' --out-dir artifacts/ablation
```

结果（`artifacts/ablation/ablation-report.md`）：

| 指标 | 本次复现 | 作者基线（2026-06-07） |
| --- | --- | --- |
| 固定 benchmark 任务数 | 12 | 12 |
| 大样本记忆实验 repeated reads | **0 vs 60** | 0 vs 60 |
| 大样本记忆实验 avg tool steps | **0.00 vs 1.00** | 0.00 |
| 上下文平均压缩率 | **25.11%** | 16.36% |
| 上下文最大压缩率 | **37.19%** | 33.59% |
| 安全场景数 | 10（path_escape 9 / approval_denied 3 / read_only_block 3） | — |

记忆那两组和作者基线完全一致；上下文压缩率略高（可能是提示词内容与版本差异）。

**附：真模型跑 harness regression 的结论**（`scripts/run_deepseek_benchmark.py`）：18 个任务通过 9 个——3 个真实编辑类任务全过，6 个平台回归任务全过，其余 9 个"剧本类"任务失败（documentation 1、tool-boundary 3、recovery 3、durable-contract 2）。**这不是 harness 或模型的问题**：这 9 个任务的 verifier 在找约定字符串（如 `recovered after invalid patch args`），是配脚本化模型设计的回归用例，作者报告里也写明"Harness regression 只证明 runtime 合同稳定，不证明 provider 上限"。

## 遗留问题

- `scripts/run_provider_experiments.py` 与 `scripts/run_large_scale_experiments.py` 仍写着 `from tether.metrics import ...`，重构到 `tether/evaluation/` 后未同步，直接跑会 ImportError。已用 `scripts/run_deepseek_benchmark.py` 和 `scripts/run_ablation_experiments.py` 两个新入口替代，旧脚本未改。
- `tests/` 里 `run_shell` 相关用例在清理过的环境变量下会因找不到 `%ComSpec%` 失败（Windows 特有），未修。
