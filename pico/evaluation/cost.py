from datetime import datetime, timezone

# 每任务成本与 prefix 缓存节省的计算。
#
# 价格表来源：DeepSeek 官方定价页 https://api-docs.deepseek.com/quick_start/pricing
# （2026-10-05 读取），单位是美元每百万 token，deepseek-flash：
# - 输入缓存命中：空闲 0.003，高峰 0.006
# - 输入缓存未命中：空闲 0.15，高峰 0.30
# - 输出：空闲 0.60，高峰 1.20
# 高峰时段：UTC 周一到周五 01:00-04:00 与 06:00-10:00，其余为空闲。
# 官方说明法定节假日全天空闲；这里没有节假日历，统一按普通工作日处理，
# 节假日的高峰时段会被算成高峰价，成本只会高估不会低估。
#
# 缓存命中与未命中的输入价差 50 倍，所以 hit ratio 是成本卡片的核心数字。
# pico 的稳定前缀设计（prefix 跨轮不变）正是命中率的来源。

_PRICE_PER_MILLION = 1_000_000

DEEPSEEK_FLASH_PRICES = {
    "model": "deepseek-flash",
    "off_peak": {"cache_hit": 0.003, "cache_miss": 0.15, "output": 0.60},
    "peak": {"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20},
}

# 高峰时段（UTC，周一到周五）：(开始小时, 结束小时)
_PEAK_WINDOWS_UTC = ((1, 4), (6, 10))


def is_peak_time(dt):
    # dt 必须带时区；统一转 UTC 再判断。
    utc_dt = dt.astimezone(timezone.utc)
    if utc_dt.weekday() >= 5:
        return False
    hour = utc_dt.hour
    return any(start <= hour < end for start, end in _PEAK_WINDOWS_UTC)


def _call_cost(metadata, created_at, prices):
    # 一次模型调用的费用。Anthropic 口径：input_tokens 不含缓存命中部分，
    # 未命中输入 = input_tokens，命中输入 = cache_read_input_tokens。
    tier = prices["peak"] if is_peak_time(created_at) else prices["off_peak"]
    miss = metadata.get("input_tokens") or 0
    hit = metadata.get("cache_read_tokens") or 0
    output = metadata.get("output_tokens") or 0
    cost = (miss * tier["cache_miss"] + hit * tier["cache_hit"] + output * tier["output"]) / _PRICE_PER_MILLION
    savings = hit * (tier["cache_miss"] - tier["cache_hit"]) / _PRICE_PER_MILLION
    return {
        "input_miss_tokens": miss,
        "cache_read_tokens": hit,
        "output_tokens": output,
        "cost_usd": cost,
        "cache_savings_usd": savings,
    }


def compute_run_cost(events, prices=None):
    # 逐 run 的成本：累加 trace 事件流里每次模型调用的 token 与费用。
    # 没有 usage 数据的调用（合成模式、旧格式工件）跳过并计数，
    # 不把零当成真实成本。
    prices = prices or DEEPSEEK_FLASH_PRICES
    total = {
        "model": prices["model"],
        "model_calls": 0,
        "calls_without_usage": 0,
        "input_miss_tokens": 0,
        "cache_read_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "cache_savings_usd": 0.0,
    }
    for event in events:
        if event.get("event") != "model_parsed":
            continue
        metadata = event.get("completion_metadata") or {}
        if not isinstance(metadata.get("input_tokens"), int):
            total["calls_without_usage"] += 1
            continue
        created_at = datetime.fromisoformat(event["created_at"])
        call = _call_cost(metadata, created_at, prices)
        total["model_calls"] += 1
        for key in ("input_miss_tokens", "cache_read_tokens", "output_tokens", "cost_usd", "cache_savings_usd"):
            total[key] += call[key]
    input_total = total["input_miss_tokens"] + total["cache_read_tokens"]
    total["cache_hit_ratio"] = total["cache_read_tokens"] / input_total if input_total else None
    return total


def summarize_run_costs(run_costs):
    # 跨 run 聚合：每任务平均与整体合计。
    # 一次模型调用都没有的 run（纯合成或异常中断）不参与平均，单独计数。
    usable = [run for run in run_costs if run["model_calls"] > 0]
    summary = {
        "runs": len(run_costs),
        "runs_without_usage": len(run_costs) - len(usable),
        "model": run_costs[0]["model"] if run_costs else None,
    }
    if not usable:
        summary.update({"per_task": None, "total": None})
        return summary
    keys = ("model_calls", "input_miss_tokens", "cache_read_tokens", "output_tokens", "cost_usd", "cache_savings_usd")
    total = {key: sum(run[key] for run in usable) for key in keys}
    input_total = total["input_miss_tokens"] + total["cache_read_tokens"]
    total["cache_hit_ratio"] = total["cache_read_tokens"] / input_total if input_total else None
    per_task = {key: total[key] / len(usable) for key in keys}
    per_task["cache_hit_ratio"] = total["cache_hit_ratio"]
    summary.update({"per_task": per_task, "total": total})
    return summary
