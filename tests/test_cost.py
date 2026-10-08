from datetime import datetime, timezone

import pytest

from tether.evaluation.cost import (
    DEEPSEEK_FLASH_PRICES,
    compute_run_cost,
    is_peak_time,
    summarize_run_costs,
)


def _model_parsed(created_at, input_tokens=None, output_tokens=None, cache_read_tokens=None):
    metadata = {}
    if input_tokens is not None:
        metadata["input_tokens"] = input_tokens
    if output_tokens is not None:
        metadata["output_tokens"] = output_tokens
    if cache_read_tokens is not None:
        metadata["cache_read_tokens"] = cache_read_tokens
    return {"event": "model_parsed", "created_at": created_at, "completion_metadata": metadata}


def test_peak_window_weekday_hours():
    # 2026-10-05 是周一。高峰：UTC 01:00-04:00 与 06:00-10:00。
    assert is_peak_time(datetime(2026, 10, 5, 1, 0, tzinfo=timezone.utc)) is True
    assert is_peak_time(datetime(2026, 10, 5, 3, 59, tzinfo=timezone.utc)) is True
    assert is_peak_time(datetime(2026, 10, 5, 4, 0, tzinfo=timezone.utc)) is False
    assert is_peak_time(datetime(2026, 10, 5, 6, 0, tzinfo=timezone.utc)) is True
    assert is_peak_time(datetime(2026, 10, 5, 9, 59, tzinfo=timezone.utc)) is True
    assert is_peak_time(datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)) is False
    assert is_peak_time(datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)) is False


def test_peak_window_weekend_and_timezone():
    # 周末全天空闲；带时区的时间统一转 UTC 判断。
    assert is_peak_time(datetime(2026, 10, 4, 2, 30, tzinfo=timezone.utc)) is False
    # 北京时间 10:30 等于 UTC 02:30，工作日，是高峰。
    assert is_peak_time(datetime.fromisoformat("2026-10-05T10:30:00+08:00")) is True


def test_compute_run_cost_sums_tokens_and_cost():
    events = [
        {"event": "run_started", "created_at": "2026-10-04T12:00:00+00:00"},
        # 周日（空闲）：未命中 1000、输出 100 → (1000×0.15 + 100×0.60)/1e6 = 0.00021
        _model_parsed("2026-10-04T12:00:00+00:00", input_tokens=1000, output_tokens=100),
        # 周一高峰：未命中 500、命中 2000、输出 50
        # → (500×0.30 + 2000×0.006 + 50×1.20)/1e6 = 0.000222
        _model_parsed("2026-10-05T02:30:00+00:00", input_tokens=500, output_tokens=50, cache_read_tokens=2000),
        {"event": "run_finished", "created_at": "2026-10-05T02:31:00+00:00"},
    ]
    cost = compute_run_cost(events)
    assert cost["model_calls"] == 2
    assert cost["calls_without_usage"] == 0
    assert cost["input_miss_tokens"] == 1500
    assert cost["cache_read_tokens"] == 2000
    assert cost["output_tokens"] == 150
    assert cost["cost_usd"] == pytest.approx(0.00021 + 0.000222)
    # 节省 = 2000×(0.30 − 0.006)/1e6 = 0.000588
    assert cost["cache_savings_usd"] == pytest.approx(0.000588)
    assert cost["cache_hit_ratio"] == pytest.approx(2000 / 3500)


def test_compute_run_cost_skips_calls_without_usage():
    events = [
        _model_parsed("2026-10-04T12:00:00+00:00"),
        _model_parsed("2026-10-04T12:01:00+00:00", input_tokens=100, output_tokens=10),
    ]
    cost = compute_run_cost(events)
    assert cost["model_calls"] == 1
    assert cost["calls_without_usage"] == 1


def test_compute_run_cost_ratio_none_when_no_input():
    events = [_model_parsed("2026-10-04T12:00:00+00:00", input_tokens=0, output_tokens=10)]
    cost = compute_run_cost(events)
    assert cost["cache_hit_ratio"] is None


def test_summarize_run_costs_averages_only_usable_runs():
    usable = compute_run_cost([
        _model_parsed("2026-10-04T12:00:00+00:00", input_tokens=1000, output_tokens=100, cache_read_tokens=1000),
    ])
    empty = compute_run_cost([{"event": "run_started", "created_at": "2026-10-04T12:00:00+00:00"}])
    summary = summarize_run_costs([usable, empty])
    assert summary["runs"] == 2
    assert summary["runs_without_usage"] == 1
    assert summary["total"]["model_calls"] == 1
    assert summary["per_task"]["cost_usd"] == pytest.approx(usable["cost_usd"])
    assert summary["total"]["cache_hit_ratio"] == pytest.approx(0.5)


def test_summarize_run_costs_empty():
    summary = summarize_run_costs([])
    assert summary["per_task"] is None
    assert summary["total"] is None


def test_price_table_matches_official_off_peak_half_of_peak():
    # 官方规则：空闲价是高峰价的一半，价格表必须守住这个关系。
    for key in ("cache_hit", "cache_miss", "output"):
        assert DEEPSEEK_FLASH_PRICES["off_peak"][key] * 2 == DEEPSEEK_FLASH_PRICES["peak"][key]
