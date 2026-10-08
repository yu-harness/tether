import json
import os
from unittest.mock import patch

from tether.evaluation.metrics import (
    _provider_profile,
    aggregate_benchmark_artifact,
    aggregate_run_artifacts,
    run_context_ablation_v2,
    run_memory_ablation_v2,
    run_recovery_ablation_v2,
    write_benchmark_core_report,
)


def test_aggregate_run_artifacts_summarizes_trajectory_metrics(tmp_path):
    runs_root = tmp_path / "runs"
    run_a = runs_root / "run_a"
    run_a.mkdir(parents=True)
    (run_a / "report.json").write_text(
        json.dumps({"tool_steps": 1, "attempts": 3, "stop_reason": "final_answer_returned"}),
        encoding="utf-8",
    )
    events = [
        {"event": "run_started", "created_at": "2026-04-15T08:00:00+00:00"},
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "retry"},
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "tool"},
        {"event": "tool_executed", "name": "read_file", "tool_status": "ok", "duration_ms": 3},
        {"event": "model_requested"},
        {"event": "model_parsed", "kind": "final"},
        {"event": "run_finished", "run_duration_ms": 10},
    ]
    (run_a / "trace.jsonl").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )

    result = aggregate_run_artifacts(runs_root)

    trajectory = result["trajectory"]
    assert trajectory["avg_retry_count"] == 1.0
    assert trajectory["avg_loop_depth"] == 3.0
    assert trajectory["total_invalid_tool_calls"] == 0
    assert trajectory["avg_tool_selection_accuracy"] == 0.5
    assert trajectory["tool_selection_accuracy_runs"] == 1
    # runs_root 聚合拿不到每个 run 的 max_steps，比例必须缺席而不是伪造
    assert trajectory["avg_loop_depth_ratio"] is None


def test_aggregate_benchmark_artifact_carries_trajectory_summary(tmp_path):
    artifact_path = tmp_path / "benchmark.json"
    artifact_path.write_text(
        json.dumps(
            {
                "summary": {
                    "total_tasks": 1,
                    "passed": 1,
                    "failed": 0,
                    "pass_rate": 1.0,
                    "within_budget": 1,
                    "verifier_passes": 1,
                    "failure_category_counts": {},
                    "trajectory": {
                        "avg_tool_selection_accuracy": 1.0,
                        "tool_selection_accuracy_runs": 1,
                        "avg_retry_count": 0.0,
                        "avg_loop_depth": 2.0,
                        "avg_loop_depth_ratio": 0.5,
                        "avg_invalid_tool_calls": 0.0,
                        "total_invalid_tool_calls": 0,
                    },
                },
                "rows": [{"id": "t1", "category": "documentation", "tool_steps": 1, "attempts": 2}],
            }
        ),
        encoding="utf-8",
    )

    result = aggregate_benchmark_artifact(artifact_path)

    assert result["trajectory"]["avg_tool_selection_accuracy"] == 1.0
    assert result["trajectory"]["total_invalid_tool_calls"] == 0


def test_run_context_ablation_v2_writes_expected_artifact(tmp_path):
    artifact_path = tmp_path / "artifacts" / "context-ablation-v2.json"

    artifact = run_context_ablation_v2(
        artifact_path=artifact_path,
        repetitions=1,
    )

    assert artifact_path.exists()
    assert artifact["artifact_type"] == "context-ablation-v2"
    assert artifact["config_count"] == 12
    assert len(artifact["configs"]) == 12
    assert "current_request_preserved_rate" in artifact["summary"]


def test_provider_profile_loads_project_env_before_reading_deepseek_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "TETHER_DEEPSEEK_API_KEY=sk-project-deepseek",
                "TETHER_DEEPSEEK_MODEL=deepseek-v4-pro",
                "TETHER_DEEPSEEK_API_BASE=https://api.deepseek.com/anthropic",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch.dict(
        os.environ,
        {
            "DEEPSEEK_API_KEY": "sk-legacy-deepseek",
            "DEEPSEEK_MODEL": "legacy-deepseek-model",
            "DEEPSEEK_API_BASE": "https://legacy.deepseek.example/anthropic",
        },
        clear=True,
    ):
        profile = _provider_profile("deepseek")

    assert profile["status"] == "ready"
    assert profile["api_key"] == "sk-project-deepseek"
    assert profile["model"] == "deepseek-v4-pro"
    assert profile["base_url"] == "https://api.deepseek.com/anthropic"


def test_provider_profile_uses_right_codes_shared_key_for_gpt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch.dict(os.environ, {"TETHER_RIGHT_CODES_API_KEY": "sk-right-codes"}, clear=True):
        profile = _provider_profile("gpt")

    assert profile["status"] == "ready"
    assert profile["api_key"] == "sk-right-codes"
    assert profile["model"] == "gpt-5.4"


def test_run_memory_ablation_v2_writes_expected_artifact(tmp_path):
    artifact_path = tmp_path / "artifacts" / "memory-ablation-v2.json"

    artifact = run_memory_ablation_v2(
        artifact_path=artifact_path,
        repetitions=1,
    )

    assert artifact_path.exists()
    assert artifact["artifact_type"] == "memory-ablation-v2"
    assert artifact["task_count"] == 12
    assert set(artifact["variants"]) == {"memory_on", "memory_off", "memory_irrelevant"}
    assert "memory_hit_rate" in artifact["variants"]["memory_on"]


def test_run_recovery_ablation_v2_writes_expected_artifact(tmp_path):
    artifact_path = tmp_path / "artifacts" / "recovery-ablation-v2.json"

    artifact = run_recovery_ablation_v2(
        artifact_path=artifact_path,
        repetitions=1,
    )

    assert artifact_path.exists()
    assert artifact["artifact_type"] == "recovery-ablation-v2"
    assert artifact["task_count"] == 10
    assert set(artifact["variants"]) == {"resume_enabled", "resume_disabled"}
    assert set(artifact["variants"]["resume_enabled"]["summary"]) >= {
        "resume_success_rate",
        "stale_reanchor_rate",
        "workspace_drift_detection_rate",
        "resume_false_accept_rate",
    }


def test_write_benchmark_core_report_marks_resume_safe_metrics(tmp_path):
    run_context_ablation_v2(tmp_path / "artifacts" / "context-ablation-v2.json", repetitions=1)
    run_memory_ablation_v2(tmp_path / "artifacts" / "memory-ablation-v2.json", repetitions=1)
    run_recovery_ablation_v2(tmp_path / "artifacts" / "recovery-ablation-v2.json", repetitions=1)
    harness_artifact_path = tmp_path / "artifacts" / "harness-regression-v2.json"
    harness_artifact_path.write_text(
        '{"summary":{"total_tasks":12,"pass_rate":1.0,"within_budget_rate":1.0,"verifier_pass_rate":1.0},"failure_category_counts":{}}',
        encoding="utf-8",
    )

    report_path = tmp_path / "docs" / "metrics" / "tether-benchmark-core-report.md"
    report_text = write_benchmark_core_report(
        report_path=report_path,
        harness_artifact_path=harness_artifact_path,
        context_artifact_path=tmp_path / "artifacts" / "context-ablation-v2.json",
        memory_artifact_path=tmp_path / "artifacts" / "memory-ablation-v2.json",
        recovery_artifact_path=tmp_path / "artifacts" / "recovery-ablation-v2.json",
    )

    assert report_path.exists()
    assert "可以安全写进简历的指标" in report_text
    assert "只适合放文档/面试展开的指标" in report_text
    assert "resume_success_rate" in report_text
    assert "memory_hit_rate" in report_text
