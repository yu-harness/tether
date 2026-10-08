import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pico.evaluation.evaluator import run_harness_regression_v2  # noqa: E402


def materialize_benchmark(source_path, target_path):
    # benchmark 的 verifier 写的是 python3，Windows 上通常只有 python.exe。
    # 与 reproduce_resume_archive.py 用同一套替换，原始定义不动。
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
        description="CI 门禁入口：合成模式跑固定回归任务，不是全部通过就返回非零。"
    )
    parser.add_argument("--benchmark-path", default="benchmarks/coding_tasks.json")
    parser.add_argument("--output-json", default="artifacts/ci/harness-regression.json")
    parser.add_argument("--workspace-root", default="artifacts/ci/workspaces")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    benchmark, replaced = materialize_benchmark(
        args.benchmark_path,
        Path(args.benchmark_path).parent / "coding_tasks.local.json",
    )
    if replaced:
        print(f"verifier 里的 python3 已换成本次解释器：{replaced} 个任务")

    artifact = run_harness_regression_v2(
        benchmark_path=benchmark,
        artifact_path=args.output_json,
        workspace_root=args.workspace_root,
    )
    summary = artifact["summary"]
    total = summary["total_tasks"]
    print(f"通过 {summary['passed']}/{total}  预算内 {summary['within_budget']}/{total}  verifier {summary['verifier_passes']}/{total}")
    for row in artifact["rows"]:
        if row["passed"]:
            continue
        detail = (row["verifier_stderr"] or row["verifier_stdout"] or "").strip()
        print(f"  FAIL  {row['id']}  {row['failure_category']}  {detail[:200]}")
    print(f"工件：{args.output_json}")

    if summary["passed"] != total:
        print(f"门禁未通过：{total - summary['passed']} 个固定任务失败", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
