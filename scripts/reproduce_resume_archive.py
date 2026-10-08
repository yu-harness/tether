import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico.evaluation.evaluator import run_harness_regression_v2  # noqa: E402
from pico.evaluation.metrics import (  # noqa: E402
    collect_resume_metrics,
    run_context_ablation_v2,
    run_memory_ablation_v2,
    run_recovery_ablation_v2,
    write_benchmark_core_report,
)


def materialize_benchmark(source_path, target_path):
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


def collection_head_commit():
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="在当前代码上重跑四层消融，写出一份可对外引用的统一归档。"
    )
    parser.add_argument("--out-dir", default="benchmarks/results/resume-archive")
    parser.add_argument("--benchmark-path", default="benchmarks/coding_tasks.json")
    parser.add_argument("--context-repetitions", type=int, default=5)
    parser.add_argument("--memory-repetitions", type=int, default=5)
    parser.add_argument("--recovery-repetitions", type=int, default=3)
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    benchmark, replaced = materialize_benchmark(
        args.benchmark_path,
        Path(args.benchmark_path).parent / "coding_tasks.local.json",
    )
    if replaced:
        print(f"verifier 里的 python3 已换成本次解释器：{replaced} 个任务")

    print("harness regression ...")
    harness_path = out_dir / "harness-regression-v2.json"
    run_harness_regression_v2(
        benchmark_path=benchmark,
        artifact_path=harness_path,
        workspace_root=out_dir / "harness-workspaces",
    )

    print("context ablation ...")
    context_path = out_dir / "context-ablation-v2.json"
    run_context_ablation_v2(context_path, repetitions=args.context_repetitions)

    print("memory ablation ...")
    memory_path = out_dir / "memory-ablation-v2.json"
    run_memory_ablation_v2(memory_path, repetitions=args.memory_repetitions)

    print("recovery ablation ...")
    recovery_path = out_dir / "recovery-ablation-v2.json"
    run_recovery_ablation_v2(recovery_path, repetitions=args.recovery_repetitions)

    print("core report ...")
    write_benchmark_core_report(
        report_path=out_dir / "pico-benchmark-core-report.md",
        harness_artifact_path=harness_path,
        context_artifact_path=context_path,
        memory_artifact_path=memory_path,
        recovery_artifact_path=recovery_path,
    )

    print("stress ablation / memory dependency / security ...")
    runs_root = out_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    metrics = collect_resume_metrics(
        str(harness_path),
        str(runs_root),
        memory_repetitions=3,
        large_memory_repetitions=args.memory_repetitions,
        context_repetitions=args.context_repetitions,
        security_repetitions=3,
        experiment_mode="synthetic",
    )
    (out_dir / "stress-security-metrics.json").write_text(
        json.dumps(
            {
                "experiment_mode": metrics["experiment_mode"],
                "facts": metrics["facts"],
                "benchmark": metrics["benchmark"],
                "stress_ablation": metrics["stress_ablation"],
                "memory_experiment": metrics["memory_experiment"],
                "memory_large_experiment": metrics["memory_large_experiment"],
                "context_experiment": metrics["context_experiment"],
                "security_experiment": metrics["security_experiment"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    provenance = {
        "captured_at": datetime.now().astimezone().isoformat(),
        "git_commit": collection_head_commit(),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "experiment_mode": "synthetic",
        "benchmark_tasks": args.benchmark_path,
        "context_repetitions": args.context_repetitions,
        "memory_repetitions": args.memory_repetitions,
        "recovery_repetitions": args.recovery_repetitions,
    }
    (out_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    harness = json.loads(harness_path.read_text(encoding="utf-8"))["summary"]
    context = json.loads(context_path.read_text(encoding="utf-8"))["summary"]
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))["variants"]["resume_enabled"]["summary"]
    memory = json.loads(memory_path.read_text(encoding="utf-8"))["variants"]
    print()
    print(f"harness      : {harness['passed']}/{harness['total_tasks']}")
    print(f"context      : {context['avg_raw_prompt_chars']:.2f} -> {context['avg_full_prompt_chars']:.2f} ({context['avg_prompt_compression_ratio']:.2%})")
    print(f"memory       : {memory['memory_off']['repeated_reads']} -> {memory['memory_on']['repeated_reads']}")
    print(f"recovery     : resume_success={recovery['resume_success_rate']:.2%} drift_detection={recovery['workspace_drift_detection_rate']:.2%} false_accept={recovery['resume_false_accept_rate']:.2%}")
    print(f"归档目录     : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
