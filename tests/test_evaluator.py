import json
import sys
from pathlib import Path
from collections import Counter

import pytest

from pico.evaluation.evaluator import (
    BenchmarkEvaluator,
    _current_locale,
    compute_run_trajectory_metrics,
    load_benchmark,
    run_harness_regression_v2,
    run_fixed_benchmark,
    summarize_rows,
)

_BENCHMARK_SOURCE = Path("benchmarks/coding_tasks.json")
_BENCHMARK_LOCAL = Path("benchmarks/coding_tasks.local.json")


def _materialize_benchmark():
    # benchmark 的 verifier 写的是 python3：Windows 上通常只有 python.exe，
    # 直接用会让每个任务停在 verifier_failed。与 scripts/ 下的两个入口一样，
    # 生成一份把 python3 换成本次解释器的本地副本。
    data = json.loads(_BENCHMARK_SOURCE.read_text(encoding="utf-8"))
    for task in data["tasks"]:
        verifier = str(task["verifier"])
        if "python3" in verifier:
            task["verifier"] = verifier.replace("python3", f'"{sys.executable}"')
    _BENCHMARK_LOCAL.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return _BENCHMARK_LOCAL


BENCHMARK_PATH = _materialize_benchmark()


def test_load_benchmark_validates_fixed_schema():
    benchmark = load_benchmark(Path("benchmarks/coding_tasks.json"))

    assert benchmark["schema_version"] == 1
    assert len(benchmark["tasks"]) == 18
    assert Counter(task["category"] for task in benchmark["tasks"]) == {
        "documentation": 2,
        "text-edit": 2,
        "tool-boundary": 3,
        "recovery": 3,
        "durable-contract": 2,
        "platform-regression": 6,
    }
    for task in benchmark["tasks"]:
        assert {"id", "prompt", "fixture_repo", "allowed_tools", "step_budget", "expected_artifact", "verifier", "category"} <= set(task)
        assert isinstance(task["allowed_tools"], list)
        assert task["step_budget"] > 0


def test_load_benchmark_rejects_missing_required_task_fields(tmp_path):
    benchmark_path = tmp_path / "bad-benchmark.json"
    benchmark_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tasks": [
                    {
                        "id": "broken",
                        "prompt": "Missing required task keys.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required"):
        load_benchmark(benchmark_path)


def test_run_fixed_benchmark_uses_fresh_fixture_copy_and_fresh_run_directory(tmp_path):
    artifact_path = tmp_path / "benchmark-v1.json"
    evaluator = BenchmarkEvaluator(
        benchmark_path=BENCHMARK_PATH,
        artifact_path=artifact_path,
        workspace_root=tmp_path / "workspaces",
    )

    original_fixture = Path("tests/fixtures/bench_repo_patch/sample.txt").read_text(encoding="utf-8")
    artifact = evaluator.run()

    row = next(item for item in artifact["rows"] if item["id"] == "sample_beta_locked")
    copied_fixture = (tmp_path / "workspaces" / row["fixture_copy_relpath"]).resolve()
    run_dir = (tmp_path / "workspaces" / row["run_dir_relpath"]).resolve()

    assert artifact_path.exists()
    assert copied_fixture.exists()
    assert run_dir.exists()
    assert not row["fixture_copy_relpath"].startswith("/")
    assert not row["run_dir_relpath"].startswith("/")
    assert row["initial_history_empty"] is True
    assert row["initial_memory_empty"] is True
    assert row["initial_task_summary_empty"] is True
    assert Path("tests/fixtures/bench_repo_patch/sample.txt").read_text(encoding="utf-8") == original_fixture
    assert "beta-locked" in (copied_fixture / "sample.txt").read_text(encoding="utf-8")


def test_run_fixed_benchmark_reports_metadata_and_success_definition(tmp_path):
    artifact_path = tmp_path / "benchmark-v1.json"
    artifact = run_fixed_benchmark(
        benchmark_path=BENCHMARK_PATH,
        artifact_path=artifact_path,
        workspace_root=tmp_path / "workspaces",
    )

    assert artifact_path.exists()
    persisted = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert persisted == artifact

    assert artifact["schema_version"] == 1
    summary = dict(artifact["summary"])
    trajectory_summary = summary.pop("trajectory")
    assert summary == {
        "total_tasks": 18,
        "passed": 18,
        "failed": 0,
        "pass_rate": 1.0,
        "within_budget": 18,
        "verifier_passes": 18,
        "within_budget_rate": 1.0,
        "verifier_pass_rate": 1.0,
        "failure_category_counts": {},
    }
    # 固定 benchmark 是确定性的：8 个 run 发起过工具调用（5 个全对、2 个 0.5、1 个 0.75），
    # 10 个 run 一轮直接给 final（accuracy 为 None、聚合跳过）；retry 全程为 0。
    assert trajectory_summary["avg_tool_selection_accuracy"] == pytest.approx(6.75 / 8)
    assert trajectory_summary["tool_selection_accuracy_runs"] == 8
    assert trajectory_summary["avg_retry_count"] == 0.0
    assert trajectory_summary["avg_loop_depth"] == pytest.approx(31 / 18)
    assert trajectory_summary["avg_loop_depth_ratio"] == pytest.approx((6.2 + 7 / 6) / 18)
    assert trajectory_summary["avg_invalid_tool_calls"] == pytest.approx(3 / 18)
    assert trajectory_summary["total_invalid_tool_calls"] == 3
    assert artifact["failure_category_counts"] == {}

    reproducibility = artifact["reproducibility"]
    assert reproducibility["model_name"] == "FakeModelClient"
    assert reproducibility["model_version"] == "scripted-deterministic"
    assert reproducibility["fixture_snapshot_id"].startswith("sha256:")
    assert reproducibility["decoding"] == {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_new_tokens": 64,
    }
    assert reproducibility["timezone"] == "Asia/Shanghai"
    # locale 记录的是运行机器的当前值，不同机器（尤其 Windows 与 Linux）不一样，
    # 断言与代码里同一个取值函数对齐，不硬编码具体 locale。
    assert reproducibility["locale"] == _current_locale()

    for row in artifact["rows"]:
        assert not row["fixture_copy_relpath"].startswith("/")
        assert not row["run_dir_relpath"].startswith("/")
        assert not row["task_state_relpath"].startswith("/")
        assert not row["report_relpath"].startswith("/")
        assert row["status"] == "pass"
        assert row["passed"] is True
        assert row["within_budget"] is True
        assert row["verifier_passed"] is True
        assert row["expected_artifact_exists"] is True
        assert row["non_failure_stop_reason"] is True
        assert row["stop_reason"] == "final_answer_returned"


def test_run_fixed_benchmark_covers_recovery_and_durable_contract_rows(tmp_path):
    artifact = run_fixed_benchmark(
        benchmark_path=BENCHMARK_PATH,
        artifact_path=tmp_path / "benchmark-v1.json",
        workspace_root=tmp_path / "workspaces",
    )

    context_row = next(item for item in artifact["rows"] if item["id"] == "context_reduction_checkpoint")
    durable_row = next(item for item in artifact["rows"] if item["id"] == "durable_promotion_reject")

    trace_path = (tmp_path / "workspaces" / context_row["run_dir_relpath"] / "trace.jsonl").resolve()
    trace_events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]

    assert any(
        event.get("event") == "checkpoint_created" and event.get("trigger") == "context_reduction"
        for event in trace_events
    )
    assert durable_row["report"]["durable_rejections"] == [
        "dependency-facts:secret_shaped",
        "key-decisions:transient_task_state",
    ]


def test_run_harness_regression_v2_writes_named_artifact(tmp_path):
    artifact_path = tmp_path / "artifacts" / "harness-regression-v2.json"

    artifact = run_harness_regression_v2(
        benchmark_path=BENCHMARK_PATH,
        artifact_path=artifact_path,
        workspace_root=tmp_path / "workspaces",
    )

    assert artifact_path.exists()
    assert artifact["summary"]["total_tasks"] == 18
    assert artifact["summary"]["pass_rate"] == 1.0
    assert artifact["summary"]["within_budget_rate"] == 1.0
    assert artifact["summary"]["verifier_pass_rate"] == 1.0


def test_run_task_anchors_paths_to_fixture_copy_even_inside_repo_workspace():
    evaluator = BenchmarkEvaluator(
        benchmark_path=BENCHMARK_PATH,
        artifact_path=Path("docs/review-pack/benchmark-v1.json"),
        workspace_root=Path("."),
    )

    task = next(item for item in evaluator.load()["tasks"] if item["id"] == "readme_intro_locked")
    row = evaluator.run_task(task)

    assert row["status"] == "pass"
    fixture_copy = Path(row["fixture_copy_relpath"])
    readme_path = fixture_copy / "README.md"
    assert "This fixture is a locked benchmark workspace." in readme_path.read_text(encoding="utf-8")


def test_compute_run_trajectory_metrics_counts_kinds_and_tool_statuses():
    events = [
        {"event": "run_started"},
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "tool"},
        {"event": "tool_executed", "name": "read_file", "tool_status": "ok"},
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "retry"},
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "tool"},
        {"event": "tool_executed", "name": "run_shell", "tool_status": "error", "tool_error_code": "tool_failed"},
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "final"},
        {"event": "run_finished"},
    ]

    metrics = compute_run_trajectory_metrics(events, max_steps=4)

    assert metrics["tool_calls"] == 2
    assert metrics["invalid_tool_calls"] == 1
    assert metrics["retry_count"] == 1
    assert metrics["loop_depth"] == 4
    assert metrics["loop_depth_ratio"] == pytest.approx(1.0)
    # 分母 = 进入执行的 2 次调用 + 1 次解析失败的 retry = 3 次工具调用尝试
    assert metrics["tool_selection_accuracy"] == pytest.approx(1 / 3)


def test_compute_run_trajectory_metrics_treats_rejected_as_invalid_and_partial_success_as_valid():
    events = [
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "tool"},
        {"event": "tool_executed", "name": "patch_file", "tool_status": "rejected", "tool_error_code": "invalid_arguments"},
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "tool"},
        {"event": "tool_executed", "name": "run_shell", "tool_status": "partial_success", "tool_error_code": "tool_partial_success"},
    ]

    metrics = compute_run_trajectory_metrics(events, max_steps=6)

    assert metrics["tool_calls"] == 2
    assert metrics["invalid_tool_calls"] == 1
    assert metrics["retry_count"] == 0
    assert metrics["loop_depth_ratio"] == pytest.approx(2 / 6)
    assert metrics["tool_selection_accuracy"] == pytest.approx(0.5)


def test_compute_run_trajectory_metrics_marks_accuracy_none_without_tool_attempts():
    events = [
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "final"},
        {"event": "run_finished"},
    ]

    metrics = compute_run_trajectory_metrics(events)

    assert metrics["tool_calls"] == 0
    assert metrics["retry_count"] == 0
    assert metrics["loop_depth"] == 1
    assert metrics["tool_selection_accuracy"] is None
    # max_steps 未知时比例必须缺席，不能伪造
    assert metrics["loop_depth_ratio"] is None


def test_run_fixed_benchmark_emits_per_step_trajectory_metrics(tmp_path):
    artifact = run_fixed_benchmark(
        benchmark_path=BENCHMARK_PATH,
        artifact_path=tmp_path / "benchmark-v1.json",
        workspace_root=tmp_path / "workspaces",
    )
    rows = {row["id"]: row for row in artifact["rows"]}

    clean = rows["sample_beta_locked"]["trajectory"]
    assert clean == {
        "tool_calls": 1,
        "invalid_tool_calls": 0,
        "retry_count": 0,
        "loop_depth": 2,
        "loop_depth_ratio": 0.5,
        "tool_selection_accuracy": 1.0,
    }

    recovered = rows["invalid_patch_recovery"]["trajectory"]
    assert recovered["tool_calls"] == 2
    assert recovered["invalid_tool_calls"] == 1
    assert recovered["retry_count"] == 0
    assert recovered["loop_depth"] == 3
    assert recovered["loop_depth_ratio"] == pytest.approx(3 / 5)
    assert recovered["tool_selection_accuracy"] == pytest.approx(0.5)

    repeated = rows["repeated_read_recovery"]["trajectory"]
    assert repeated["tool_calls"] == 4
    assert repeated["invalid_tool_calls"] == 1
    assert repeated["loop_depth"] == 5
    assert repeated["tool_selection_accuracy"] == pytest.approx(0.75)

    # 一轮直接给 final 的 run 没有发起任何工具动作，accuracy 为 None 而不是 0 或 1
    final_only = rows["durable_promotion_accept"]["trajectory"]
    assert final_only["tool_calls"] == 0
    assert final_only["tool_selection_accuracy"] is None
    assert final_only["loop_depth"] == 1

    trajectory_summary = artifact["summary"]["trajectory"]
    assert trajectory_summary["avg_retry_count"] == 0.0
    assert trajectory_summary["total_invalid_tool_calls"] == 3


def test_summarize_rows_counts_failure_categories():
    summary = summarize_rows(
        [
            {
                "status": "pass",
                "within_budget": True,
                "verifier_passed": True,
                "expected_artifact_exists": True,
                "non_failure_stop_reason": True,
            },
            {
                "status": "fail",
                "within_budget": False,
                "verifier_passed": False,
                "expected_artifact_exists": False,
                "non_failure_stop_reason": False,
                "failure_category": "verifier_failed",
            },
            {
                "status": "fail",
                "within_budget": False,
                "verifier_passed": True,
                "expected_artifact_exists": True,
                "non_failure_stop_reason": False,
                "failure_category": "budget_exceeded",
            },
        ]
    )

    assert summary["total_tasks"] == 3
    assert summary["passed"] == 1
    assert summary["failed"] == 2
    assert summary["pass_rate"] == pytest.approx(1 / 3)
    assert summary["within_budget"] == 1
    assert summary["verifier_passes"] == 2
    assert summary["failure_category_counts"] == {
        "budget_exceeded": 1,
        "verifier_failed": 1,
    }
