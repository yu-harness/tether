import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tether.evaluation.cost import DEEPSEEK_FLASH_PRICES, compute_run_cost, summarize_run_costs  # noqa: E402

# 成本卡片生成入口：读取一个 runs 根目录（下面是 run_*/trace.jsonl），
# 算出每任务的 token、费用与 prefix 缓存命中带来的节省，输出 Markdown 卡片。
# 用法：
#   D:/Dev/miniconda3/python.exe scripts/build_cost_card.py --runs-root <runs目录>
# 数据里必须包含真实模型运行（合成模式的 run 没有 usage，会被单独计数跳过）。


def read_run_events(trace_path):
    return [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fmt_usd(value):
    return f"${value:.6f}"


def fmt_pct(value):
    return f"{value * 100:.1f}%" if value is not None else "null"


def render_card(summary, run_costs):
    lines = []
    total = summary["total"]
    per_task = summary["per_task"]
    lines.append(f"- 样本：{summary['runs']} 个 run（{summary['runs_without_usage']} 个无 usage 数据，不参与平均）")
    if total is None:
        lines.append("- 没有带 usage 的模型调用，无法出卡")
        return "\n".join(lines)
    lines.append(
        f"- 每任务平均：{per_task['model_calls']:.1f} 次模型调用，"
        f"输入 {per_task['input_miss_tokens']:.0f}（未命中）+ {per_task['cache_read_tokens']:.0f}（缓存命中）"
        f" / 输出 {per_task['output_tokens']:.0f} tokens，"
        f"成本 {fmt_usd(per_task['cost_usd'])}"
    )
    lines.append(
        f"- 缓存命中率 {fmt_pct(total['cache_hit_ratio'])}，"
        f"累计节省 {fmt_usd(total['cache_savings_usd'])}"
        f"（命中部分按未命中价计费的成本差）"
    )
    lines.append(
        f"- 合计：{total['model_calls']} 次调用，"
        f"成本 {fmt_usd(total['cost_usd'])}"
    )
    lines.append("- 逐 run 明细：")
    for run in run_costs:
        lines.append(
            f"  - {run['run_id']}：{run['model_calls']} 次调用，"
            f"命中率 {fmt_pct(run['cache_hit_ratio'])}，成本 {fmt_usd(run['cost_usd'])}"
        )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="从 runs 目录生成每任务成本卡片")
    parser.add_argument("--runs-root", required=True, help="runs 根目录（下面是 run_*/trace.jsonl）")
    parser.add_argument("--output", default=None, help="可选：把 Markdown 卡片写入该文件")
    args = parser.parse_args(argv)

    runs_root = Path(args.runs_root)
    # 兼容两种形态：直接的 runs 根（run_*/trace.jsonl）与
    # benchmark workspace 根（<任务目录>/.tether/runs/run_*/trace.jsonl）。
    trace_paths = sorted(runs_root.glob("**/run_*/trace.jsonl"))
    if not trace_paths:
        raise RuntimeError(f"{runs_root} 下没有找到 run_*/trace.jsonl")

    run_costs = []
    for trace_path in trace_paths:
        events = read_run_events(trace_path)
        run_cost = compute_run_cost(events, prices=DEEPSEEK_FLASH_PRICES)
        run_cost["run_id"] = trace_path.parent.name
        run_costs.append(run_cost)

    summary = summarize_run_costs(run_costs)
    card = render_card(summary, run_costs)
    print(card)
    if args.output:
        Path(args.output).write_text(card + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
