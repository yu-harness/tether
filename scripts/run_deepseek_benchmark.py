#!/usr/bin/env python3
"""只跑 DeepSeek 的固定 benchmark 入口，产出可复盘的评测工件。

为什么存在：
1. `scripts/run_provider_experiments.py` 需要 GPT / Claude / DeepSeek 三家 key，
   只配了 DeepSeek 的环境跑不起来；
2. `run_fixed_benchmark()` 在不传 `model_client_factory` 时会退化成
   `FakeModelClient`（脚本化假模型），跑出来的不是真实模型结果；
3. benchmark 里的 verifier 写的是 `python3 -c ...`，Windows 上通常只有 `python.exe`，
   直接跑会让所有任务停在 `verifier_failed`，数字不可信。
这里把三件事接起来：用真实 DeepSeek client、跑同一批任务、verifier 换成本次运行的解释器。

用法：
    python scripts/run_deepseek_benchmark.py --output-json benchmarks/results/deepseek-flash.json
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico.config import load_project_env, provider_env  # noqa: E402
from pico.evaluation.evaluator import run_fixed_benchmark  # noqa: E402
from pico.providers.clients import AnthropicCompatibleModelClient  # noqa: E402

DEFAULT_BASE_URL = "https://api.deepseek.com/anthropic"
DEFAULT_MODEL = "deepseek-flash"


def build_client_factory(model, base_url, temperature, timeout):
    """每个任务单独造一个 client，避免上一轮的响应元数据串到下一轮。"""

    def factory(task=None, workspace=None):
        return AnthropicCompatibleModelClient(
            model=model,
            base_url=base_url,
            api_key=provider_env("PICO_DEEPSEEK_API_KEY", ("DEEPSEEK_API_KEY",)),
            temperature=temperature,
            timeout=timeout,
            # 与 CLI 保持一致：V4.1 默认思考模式会吃掉输出预算，这里关掉
            thinking_disabled=True,
        )

    return factory


def materialize_benchmark(source_path, target_path):
    """把 verifier 里的 `python3` 换成本次运行的解释器，返回 (可用路径, 替换条数)。

    原始 benchmark 的 verifier 写的是 `python3 -c ...`。Windows 上一般只有
    `python.exe`，直接跑会让每个任务都停在 verifier_failed，通过率就没意义了。
    这里生成一份本地副本，不动项目里的原始定义。
    """
    source = Path(source_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    replaced = 0
    for task in data.get("tasks", []):
        verifier = str(task.get("verifier", ""))
        if "python3" in verifier:
            task["verifier"] = verifier.replace("python3", f'"{sys.executable}"')
            replaced += 1
    if not replaced:
        return source, 0
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target, replaced


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="用 DeepSeek 跑 pico 的固定 benchmark，并把结果写成工件。"
    )
    parser.add_argument("--benchmark-path", default="benchmarks/coding_tasks.json")
    parser.add_argument("--output-json", required=True, help="benchmark 工件输出路径")
    parser.add_argument("--workspace-root", default="artifacts/deepseek-benchmark-workspaces")
    parser.add_argument("--model", default=None, help="默认取 PICO_DEEPSEEK_MODEL 或 deepseek-flash")
    parser.add_argument("--base-url", default=None, help="默认取 PICO_DEEPSEEK_API_BASE")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    return parser


def print_report(artifact):
    rows = artifact.get("rows", [])
    total = len(rows)
    passed = sum(1 for row in rows if row.get("passed"))
    print()
    if total:
        print(f"通过 {passed}/{total}  ({passed / total:.0%})")
    else:
        print("没有任务")
    counts = artifact.get("failure_category_counts", {})
    if counts:
        print("失败原因分布：")
        for name, count in sorted(counts.items(), key=lambda item: -item[1]):
            print(f"  {name}: {count}")
    print()
    print("逐条结果：")
    for row in rows:
        mark = "PASS" if row.get("passed") else "FAIL"
        detail = row.get("failure_category") or ""
        print(f"  {mark}  {row.get('id')}  [{row.get('category')}]  {detail}")
    print()


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    # .env 的查找口径和 CLI 保持一致：从当前工作目录往上找
    load_project_env(Path.cwd())
    if not provider_env("PICO_DEEPSEEK_API_KEY", ("DEEPSEEK_API_KEY",)):
        print(
            "没读到 DeepSeek key：请在项目 .env 或环境变量里设置 PICO_DEEPSEEK_API_KEY",
            file=sys.stderr,
        )
        return 1

    # 副本必须和原始 benchmark 放在同一层目录：BenchmarkEvaluator 用
    # benchmark_path.parent.parent 当 repo_root 去定位 fixture，
    # 放深一层（比如 benchmarks/results/ 里）就会找不到 fixture。
    benchmark_path, replaced = materialize_benchmark(
        args.benchmark_path,
        Path(args.benchmark_path).parent / "coding_tasks.local.json",
    )
    if replaced:
        print(f"verifier 里的 python3 已换成本次解释器：{replaced} 个任务")
        print(f"本地 benchmark 副本：{benchmark_path}")

    model = args.model or provider_env("PICO_DEEPSEEK_MODEL", ("DEEPSEEK_MODEL",), DEFAULT_MODEL)
    base_url = args.base_url or provider_env(
        "PICO_DEEPSEEK_API_BASE", ("DEEPSEEK_API_BASE",), DEFAULT_BASE_URL
    )
    print(f"model={model}")
    print(f"base_url={base_url}")
    print(f"max_new_tokens={args.max_new_tokens}  workspace_root={args.workspace_root}")

    artifact = run_fixed_benchmark(
        benchmark_path=benchmark_path,
        artifact_path=args.output_json,
        workspace_root=args.workspace_root,
        model_name=model,
        model_version="",
        temperature=args.temperature,
        max_new_tokens=args.max_new_tokens,
        model_client_factory=build_client_factory(model, base_url, args.temperature, args.timeout),
    )
    print_report(artifact)
    print(f"工件已写入：{args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
