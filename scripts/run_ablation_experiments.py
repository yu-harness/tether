#!/usr/bin/env python3
"""跑 pico 的消融实验（synthetic 模式，脚本化模型，不调用真实 API）。

为什么存在：
1. `scripts/run_large_scale_experiments.py` 写的是 `from pico.metrics import ...`，
   重构到 `pico/evaluation/` 之后没有同步，已经 ImportError；
2. benchmark 的 verifier 写的是 `python3 -c ...`，Windows 上没有 `python3`，
   不处理的话 harness regression 会整批停在 verifier_failed。

这份脚本用新的包路径重写入口，只跑 synthetic 模式，产出四组消融：
- harness regression：18 个固定任务的通过情况（证明 runtime 合同稳定）
- memory：记忆开关对重复读次数的影响
- context：上下文压缩前后的 prompt 大小
- security：工具边界的拦截场景

用法：
    python scripts/run_ablation_experiments.py --runs-root 'D:\\tmp\\pico-playground\\.pico\\runs'
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico.evaluation.evaluator import run_harness_regression_v2  # noqa: E402
from pico.evaluation.metrics import (  # noqa: E402
    collect_resume_metrics,
    render_large_scale_experiment_report,
    render_resume_metrics_markdown,
)


def materialize_benchmark(source_path, target_path):
    """把 verifier 里的 `python3` 换成本次运行的解释器（与 run_deepseek_benchmark.py 同一逻辑）。

    副本必须和原始 benchmark 同层目录：BenchmarkEvaluator 用
    `benchmark_path.parent.parent` 当 repo_root 去定位 fixture。
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
        description="跑 pico 的 synthetic 消融实验并输出 Markdown 报告（不需要 API key）。"
    )
    parser.add_argument("--out-dir", default="artifacts/ablation", help="实验工件输出目录")
    parser.add_argument(
        "--runs-root",
        required=True,
        help="用来聚合运行工件的 .pico/runs 根目录，例如 'D:\\tmp\\pico-playground\\.pico\\runs'",
    )
    parser.add_argument("--benchmark-path", default="benchmarks/coding_tasks.json")
    parser.add_argument("--benchmark-artifact", default=None, help="已有的 harness regression 工件；不给就先跑一次")
    parser.add_argument("--memory-repetitions", type=int, default=3)
    parser.add_argument("--large-memory-repetitions", type=int, default=5)
    parser.add_argument("--context-repetitions", type=int, default=5)
    parser.add_argument("--security-repetitions", type=int, default=3)
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    benchmark_artifact = args.benchmark_artifact
    if not benchmark_artifact:
        benchmark, replaced = materialize_benchmark(
            args.benchmark_path,
            Path(args.benchmark_path).parent / "coding_tasks.local.json",
        )
        if replaced:
            print(f"verifier 里的 python3 已换成本次解释器：{replaced} 个任务")
        benchmark_artifact = out_dir / "harness-regression.json"
        print("跑 harness regression（脚本化模型，不花 API 钱）...")
        run_harness_regression_v2(
            benchmark_path=benchmark,
            artifact_path=benchmark_artifact,
            workspace_root=out_dir / "harness-workspaces",
        )
        print(f"  工件：{benchmark_artifact}")

    print("跑消融实验（memory / context / security，全部脚本化）...")
    metrics = collect_resume_metrics(
        str(benchmark_artifact),
        args.runs_root,
        memory_repetitions=args.memory_repetitions,
        large_memory_repetitions=args.large_memory_repetitions,
        context_repetitions=args.context_repetitions,
        security_repetitions=args.security_repetitions,
        experiment_mode="synthetic",
    )

    (out_dir / "resume-metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "resume-metrics.md").write_text(
        render_resume_metrics_markdown(metrics) + "\n", encoding="utf-8"
    )
    (out_dir / "ablation-report.md").write_text(
        render_large_scale_experiment_report(metrics) + "\n", encoding="utf-8"
    )

    benchmark_summary = metrics["benchmark"]
    runs_summary = metrics["runs"]
    print()
    print(f"harness regression：{benchmark_summary.get('task_count')} 个任务")
    print(f"聚合运行数        ：{runs_summary.get('run_count')}")
    print()
    print("要点：")
    for line in metrics["resume_highlights"]:
        print(f"  - {line}")
    print()
    print(f"报告：{out_dir / 'ablation-report.md'}")
    print(f"指标：{out_dir / 'resume-metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
