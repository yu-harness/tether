// 本文件由 trace.jsonl 原样生成，事件内容未做任何手工改动。
// 来源: benchmarks/results/cost-card-2026-10-05/workspaces/path_escape_recovery/bench_repo_patch/.tether/runs/run_20261005-081410-452a72/trace.jsonl
const TRACE_EVENTS = [
  {
    "created_at": "2026-10-05T00:14:10.789358+00:00",
    "event": "run_started",
    "task_id": "task_20261005-081410-df3e7d",
    "user_request": "Reject a path escape attempt and still finish the sample.txt patch."
  },
  {
    "created_at": "2026-10-05T00:14:11.711789+00:00",
    "duration_ms": 901,
    "event": "prompt_built",
    "prompt_metadata": {
      "budget_reductions": [],
      "current_request": {
        "raw_chars": 67,
        "rendered_chars": 67,
        "section_chars": 89,
        "text": "Reject a path escape attempt and still finish the sample.txt patch."
      },
      "history": {
        "collapsed_duplicate_reads": 0,
        "older_entries_count": 0,
        "raw_chars": 86,
        "rendered_chars": 86,
        "reused_file_summary_count": 0,
        "summarized_tool_count": 0
      },
      "history_chars": 74,
      "memory_chars": 161,
      "prefix_changed": true,
      "prefix_chars": 5475,
      "prefix_hash": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
      "prompt_budget_chars": 12000,
      "prompt_cache_key": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
      "prompt_cache_supported": false,
      "prompt_chars": 3967,
      "prompt_over_budget": false,
      "recent_commits": 5,
      "reduction_order": [
        "relevant_memory",
        "history",
        "memory",
        "prefix"
      ],
      "relevant_memory": {
        "limit": 3,
        "raw_chars": 23,
        "rendered_chars": 23,
        "rendered_count": 0,
        "rendered_notes": [],
        "selected_count": 0,
        "selected_durable_count": 0,
        "selected_kinds": [],
        "selected_notes": [],
        "selected_sources": []
      },
      "request_chars": 67,
      "resume_status": "no-checkpoint",
      "runtime_identity_mismatch_fields": [],
      "secret_env_count": 7,
      "secret_env_names": [
        "CODEBUDDY_GATEWAY_PASSWORD",
        "DASHSCOPE_API_KEY",
        "LANGSMITH_API_KEY",
        "LLAMA_CLOUD_API_KEY",
        "TETHER_DEEPSEEK_API_KEY",
        "WEREAD_API_KEY",
        "WORKBUDDY_PAC_RPC_TOKEN"
      ],
      "section_budgets": {
        "checkpoint": 400,
        "current_request": null,
        "history": 5200,
        "memory": 1600,
        "prefix": 3600,
        "relevant_memory": 1200
      },
      "section_order": [
        "prefix",
        "checkpoint",
        "memory",
        "relevant_memory",
        "history",
        "current_request"
      ],
      "sections": {
        "checkpoint": {
          "budget_chars": 400,
          "raw_chars": 0,
          "rendered_chars": 0
        },
        "current_request": {
          "budget_chars": null,
          "raw_chars": 89,
          "rendered_chars": 89
        },
        "history": {
          "budget_chars": 5200,
          "raw_chars": 86,
          "rendered_chars": 86
        },
        "memory": {
          "budget_chars": 1600,
          "raw_chars": 161,
          "rendered_chars": 161
        },
        "prefix": {
          "budget_chars": 3600,
          "raw_chars": 5475,
          "rendered_chars": 3600
        },
        "relevant_memory": {
          "budget_chars": 1200,
          "raw_chars": 23,
          "rendered_chars": 23
        }
      },
      "stale_paths": [],
      "stale_summary_invalidations": 0,
      "tool_count": 2,
      "tool_signature": "2ce2c35819cc1537d4556c1cef854b28598d76fa82e22499fd8c6ec0a037e111",
      "workspace_changed": true,
      "workspace_chars": 3341,
      "workspace_docs": 1,
      "workspace_fingerprint": "551d9f0ced0ca3148d9b78e1cf425dcaa70e2175746ee7e2874ebf59d22be07c"
    }
  },
  {
    "attempts": 1,
    "created_at": "2026-10-05T00:14:11.723789+00:00",
    "event": "model_requested",
    "prompt_cache_key": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
    "tool_steps": 0
  },
  {
    "completion_metadata": {
      "cache_creation_tokens": 0,
      "cache_hit": true,
      "cache_read_tokens": 384,
      "input_tokens": 727,
      "output_tokens": 36,
      "stop_reason": "end_turn",
      "total_tokens": 763
    },
    "created_at": "2026-10-05T00:14:12.488685+00:00",
    "duration_ms": 763,
    "event": "model_parsed",
    "kind": "tool"
  },
  {
    "affected_paths": [],
    "args": {
      "path": "."
    },
    "created_at": "2026-10-05T00:14:12.497090+00:00",
    "diff_summary": [],
    "duration_ms": 4,
    "event": "tool_executed",
    "name": "list_files",
    "read_only": false,
    "result": "error: tool 'list_files' is not allowed in this run",
    "risk_level": "high",
    "security_event_type": "",
    "tool_error_code": "tool_not_allowed",
    "tool_status": "rejected",
    "workspace_changed": false
  },
  {
    "checkpoint_id": "ckpt_25811adb",
    "created_at": "2026-10-05T00:14:12.503692+00:00",
    "event": "checkpoint_created",
    "trigger": "tool_executed"
  },
  {
    "created_at": "2026-10-05T00:14:13.423026+00:00",
    "duration_ms": 906,
    "event": "prompt_built",
    "prompt_metadata": {
      "budget_reductions": [],
      "current_request": {
        "raw_chars": 67,
        "rendered_chars": 67,
        "section_chars": 89,
        "text": "Reject a path escape attempt and still finish the sample.txt patch."
      },
      "history": {
        "collapsed_duplicate_reads": 0,
        "older_entries_count": 0,
        "raw_chars": 170,
        "rendered_chars": 170,
        "reused_file_summary_count": 0,
        "summarized_tool_count": 0
      },
      "history_chars": 158,
      "memory_chars": 161,
      "prefix_changed": false,
      "prefix_chars": 5475,
      "prefix_hash": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
      "prompt_budget_chars": 12000,
      "prompt_cache_key": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
      "prompt_cache_supported": false,
      "prompt_chars": 4365,
      "prompt_over_budget": false,
      "recent_commits": 5,
      "reduction_order": [
        "relevant_memory",
        "history",
        "memory",
        "prefix"
      ],
      "relevant_memory": {
        "limit": 3,
        "raw_chars": 23,
        "rendered_chars": 23,
        "rendered_count": 0,
        "rendered_notes": [],
        "selected_count": 0,
        "selected_durable_count": 0,
        "selected_kinds": [],
        "selected_notes": [],
        "selected_sources": []
      },
      "request_chars": 67,
      "resume_status": "full-valid",
      "runtime_identity_mismatch_fields": [],
      "secret_env_count": 7,
      "secret_env_names": [
        "CODEBUDDY_GATEWAY_PASSWORD",
        "DASHSCOPE_API_KEY",
        "LANGSMITH_API_KEY",
        "LLAMA_CLOUD_API_KEY",
        "TETHER_DEEPSEEK_API_KEY",
        "WEREAD_API_KEY",
        "WORKBUDDY_PAC_RPC_TOKEN"
      ],
      "section_budgets": {
        "checkpoint": 400,
        "current_request": null,
        "history": 5200,
        "memory": 1600,
        "prefix": 3600,
        "relevant_memory": 1200
      },
      "section_order": [
        "prefix",
        "checkpoint",
        "memory",
        "relevant_memory",
        "history",
        "current_request"
      ],
      "sections": {
        "checkpoint": {
          "budget_chars": 400,
          "raw_chars": 312,
          "rendered_chars": 312
        },
        "current_request": {
          "budget_chars": null,
          "raw_chars": 89,
          "rendered_chars": 89
        },
        "history": {
          "budget_chars": 5200,
          "raw_chars": 170,
          "rendered_chars": 170
        },
        "memory": {
          "budget_chars": 1600,
          "raw_chars": 161,
          "rendered_chars": 161
        },
        "prefix": {
          "budget_chars": 3600,
          "raw_chars": 5475,
          "rendered_chars": 3600
        },
        "relevant_memory": {
          "budget_chars": 1200,
          "raw_chars": 23,
          "rendered_chars": 23
        }
      },
      "stale_paths": [],
      "stale_summary_invalidations": 0,
      "tool_count": 2,
      "tool_signature": "2ce2c35819cc1537d4556c1cef854b28598d76fa82e22499fd8c6ec0a037e111",
      "workspace_changed": false,
      "workspace_chars": 3341,
      "workspace_docs": 1,
      "workspace_fingerprint": "551d9f0ced0ca3148d9b78e1cf425dcaa70e2175746ee7e2874ebf59d22be07c"
    }
  },
  {
    "attempts": 2,
    "created_at": "2026-10-05T00:14:13.434930+00:00",
    "event": "model_requested",
    "prompt_cache_key": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
    "tool_steps": 1
  },
  {
    "completion_metadata": {
      "cache_creation_tokens": 0,
      "cache_hit": true,
      "cache_read_tokens": 768,
      "input_tokens": 440,
      "output_tokens": 26,
      "stop_reason": "end_turn",
      "total_tokens": 466
    },
    "created_at": "2026-10-05T00:14:14.149812+00:00",
    "duration_ms": 713,
    "event": "model_parsed",
    "kind": "tool"
  },
  {
    "affected_paths": [],
    "args": {
      "end": 200,
      "path": "sample.txt",
      "start": 1
    },
    "created_at": "2026-10-05T00:14:14.162408+00:00",
    "diff_summary": [],
    "duration_ms": 8,
    "event": "tool_executed",
    "name": "read_file",
    "read_only": true,
    "result": "# sample.txt\n   1: alpha\n   2: beta\n   3: gamma\n   4: placeholder",
    "risk_level": "low",
    "security_event_type": "",
    "tool_error_code": "",
    "tool_status": "ok",
    "workspace_changed": false,
    "workspace_fingerprint": "551d9f0ced0ca3148d9b78e1cf425dcaa70e2175746ee7e2874ebf59d22be07c"
  },
  {
    "checkpoint_id": "ckpt_f3a3ba7e",
    "created_at": "2026-10-05T00:14:14.171279+00:00",
    "event": "checkpoint_created",
    "trigger": "tool_executed"
  },
  {
    "created_at": "2026-10-05T00:14:15.072617+00:00",
    "duration_ms": 887,
    "event": "prompt_built",
    "prompt_metadata": {
      "budget_reductions": [],
      "current_request": {
        "raw_chars": 67,
        "rendered_chars": 67,
        "section_chars": 89,
        "text": "Reject a path escape attempt and still finish the sample.txt patch."
      },
      "history": {
        "collapsed_duplicate_reads": 0,
        "older_entries_count": 0,
        "raw_chars": 300,
        "rendered_chars": 300,
        "reused_file_summary_count": 0,
        "summarized_tool_count": 0
      },
      "history_chars": 288,
      "memory_chars": 214,
      "prefix_changed": false,
      "prefix_chars": 5475,
      "prefix_hash": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
      "prompt_budget_chars": 12000,
      "prompt_cache_key": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
      "prompt_cache_supported": false,
      "prompt_chars": 4581,
      "prompt_over_budget": false,
      "recent_commits": 5,
      "reduction_order": [
        "relevant_memory",
        "history",
        "memory",
        "prefix"
      ],
      "relevant_memory": {
        "limit": 3,
        "raw_chars": 48,
        "rendered_chars": 48,
        "rendered_count": 1,
        "rendered_notes": [
          "1: alpha | 2: beta | 3: gamma"
        ],
        "selected_count": 1,
        "selected_durable_count": 0,
        "selected_kinds": [
          "episodic"
        ],
        "selected_notes": [
          "1: alpha | 2: beta | 3: gamma"
        ],
        "selected_sources": [
          "sample.txt"
        ]
      },
      "request_chars": 67,
      "resume_status": "full-valid",
      "runtime_identity_mismatch_fields": [],
      "secret_env_count": 7,
      "secret_env_names": [
        "CODEBUDDY_GATEWAY_PASSWORD",
        "DASHSCOPE_API_KEY",
        "LANGSMITH_API_KEY",
        "LLAMA_CLOUD_API_KEY",
        "TETHER_DEEPSEEK_API_KEY",
        "WEREAD_API_KEY",
        "WORKBUDDY_PAC_RPC_TOKEN"
      ],
      "section_budgets": {
        "checkpoint": 400,
        "current_request": null,
        "history": 5200,
        "memory": 1600,
        "prefix": 3600,
        "relevant_memory": 1200
      },
      "section_order": [
        "prefix",
        "checkpoint",
        "memory",
        "relevant_memory",
        "history",
        "current_request"
      ],
      "sections": {
        "checkpoint": {
          "budget_chars": 400,
          "raw_chars": 320,
          "rendered_chars": 320
        },
        "current_request": {
          "budget_chars": null,
          "raw_chars": 89,
          "rendered_chars": 89
        },
        "history": {
          "budget_chars": 5200,
          "raw_chars": 300,
          "rendered_chars": 300
        },
        "memory": {
          "budget_chars": 1600,
          "raw_chars": 214,
          "rendered_chars": 214
        },
        "prefix": {
          "budget_chars": 3600,
          "raw_chars": 5475,
          "rendered_chars": 3600
        },
        "relevant_memory": {
          "budget_chars": 1200,
          "raw_chars": 48,
          "rendered_chars": 48
        }
      },
      "stale_paths": [],
      "stale_summary_invalidations": 0,
      "tool_count": 2,
      "tool_signature": "2ce2c35819cc1537d4556c1cef854b28598d76fa82e22499fd8c6ec0a037e111",
      "workspace_changed": false,
      "workspace_chars": 3341,
      "workspace_docs": 1,
      "workspace_fingerprint": "551d9f0ced0ca3148d9b78e1cf425dcaa70e2175746ee7e2874ebf59d22be07c"
    }
  },
  {
    "attempts": 3,
    "created_at": "2026-10-05T00:14:15.079533+00:00",
    "event": "model_requested",
    "prompt_cache_key": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
    "tool_steps": 2
  },
  {
    "completion_metadata": {
      "cache_creation_tokens": 0,
      "cache_hit": true,
      "cache_read_tokens": 896,
      "input_tokens": 397,
      "output_tokens": 31,
      "stop_reason": "end_turn",
      "total_tokens": 428
    },
    "created_at": "2026-10-05T00:14:15.789404+00:00",
    "duration_ms": 708,
    "event": "model_parsed",
    "kind": "tool"
  },
  {
    "affected_paths": [
      "sample.txt"
    ],
    "args": {
      "new_text": "patched",
      "old_text": "placeholder",
      "path": "sample.txt"
    },
    "created_at": "2026-10-05T00:14:15.805430+00:00",
    "diff_summary": [
      "modified:sample.txt"
    ],
    "duration_ms": 11,
    "event": "tool_executed",
    "name": "patch_file",
    "read_only": false,
    "result": "patched sample.txt",
    "risk_level": "high",
    "security_event_type": "",
    "tool_error_code": "",
    "tool_status": "ok",
    "workspace_changed": true,
    "workspace_fingerprint": "551d9f0ced0ca3148d9b78e1cf425dcaa70e2175746ee7e2874ebf59d22be07c"
  },
  {
    "checkpoint_id": "ckpt_a8474bea",
    "created_at": "2026-10-05T00:14:15.813261+00:00",
    "event": "checkpoint_created",
    "trigger": "tool_executed"
  },
  {
    "created_at": "2026-10-05T00:14:16.688557+00:00",
    "duration_ms": 860,
    "event": "prompt_built",
    "prompt_metadata": {
      "budget_reductions": [],
      "current_request": {
        "raw_chars": 67,
        "rendered_chars": 67,
        "section_chars": 89,
        "text": "Reject a path escape attempt and still finish the sample.txt patch."
      },
      "history": {
        "collapsed_duplicate_reads": 0,
        "older_entries_count": 0,
        "raw_chars": 410,
        "rendered_chars": 410,
        "reused_file_summary_count": 0,
        "summarized_tool_count": 0
      },
      "history_chars": 398,
      "memory_chars": 170,
      "prefix_changed": false,
      "prefix_chars": 5475,
      "prefix_hash": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
      "prompt_budget_chars": 12000,
      "prompt_cache_key": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
      "prompt_cache_supported": false,
      "prompt_chars": 4648,
      "prompt_over_budget": false,
      "recent_commits": 5,
      "reduction_order": [
        "relevant_memory",
        "history",
        "memory",
        "prefix"
      ],
      "relevant_memory": {
        "limit": 3,
        "raw_chars": 48,
        "rendered_chars": 48,
        "rendered_count": 1,
        "rendered_notes": [
          "1: alpha | 2: beta | 3: gamma"
        ],
        "selected_count": 1,
        "selected_durable_count": 0,
        "selected_kinds": [
          "episodic"
        ],
        "selected_notes": [
          "1: alpha | 2: beta | 3: gamma"
        ],
        "selected_sources": [
          "sample.txt"
        ]
      },
      "request_chars": 67,
      "resume_status": "full-valid",
      "runtime_identity_mismatch_fields": [],
      "secret_env_count": 7,
      "secret_env_names": [
        "CODEBUDDY_GATEWAY_PASSWORD",
        "DASHSCOPE_API_KEY",
        "LANGSMITH_API_KEY",
        "LLAMA_CLOUD_API_KEY",
        "TETHER_DEEPSEEK_API_KEY",
        "WEREAD_API_KEY",
        "WORKBUDDY_PAC_RPC_TOKEN"
      ],
      "section_budgets": {
        "checkpoint": 400,
        "current_request": null,
        "history": 5200,
        "memory": 1600,
        "prefix": 3600,
        "relevant_memory": 1200
      },
      "section_order": [
        "prefix",
        "checkpoint",
        "memory",
        "relevant_memory",
        "history",
        "current_request"
      ],
      "sections": {
        "checkpoint": {
          "budget_chars": 400,
          "raw_chars": 321,
          "rendered_chars": 321
        },
        "current_request": {
          "budget_chars": null,
          "raw_chars": 89,
          "rendered_chars": 89
        },
        "history": {
          "budget_chars": 5200,
          "raw_chars": 410,
          "rendered_chars": 410
        },
        "memory": {
          "budget_chars": 1600,
          "raw_chars": 170,
          "rendered_chars": 170
        },
        "prefix": {
          "budget_chars": 3600,
          "raw_chars": 5475,
          "rendered_chars": 3600
        },
        "relevant_memory": {
          "budget_chars": 1200,
          "raw_chars": 48,
          "rendered_chars": 48
        }
      },
      "stale_paths": [],
      "stale_summary_invalidations": 0,
      "tool_count": 2,
      "tool_signature": "2ce2c35819cc1537d4556c1cef854b28598d76fa82e22499fd8c6ec0a037e111",
      "workspace_changed": false,
      "workspace_chars": 3341,
      "workspace_docs": 1,
      "workspace_fingerprint": "551d9f0ced0ca3148d9b78e1cf425dcaa70e2175746ee7e2874ebf59d22be07c"
    }
  },
  {
    "attempts": 4,
    "created_at": "2026-10-05T00:14:16.696122+00:00",
    "event": "model_requested",
    "prompt_cache_key": "ed176a6a21ecca7a514a423a2d5dae27a3dcfa6eab6a7b343357d8b6f379d041",
    "tool_steps": 3
  },
  {
    "completion_metadata": {
      "cache_creation_tokens": 0,
      "cache_hit": true,
      "cache_read_tokens": 896,
      "input_tokens": 411,
      "output_tokens": 29,
      "stop_reason": "end_turn",
      "total_tokens": 440
    },
    "created_at": "2026-10-05T00:14:17.335675+00:00",
    "duration_ms": 637,
    "event": "model_parsed",
    "kind": "final"
  },
  {
    "checkpoint_id": "ckpt_dbc730f2",
    "created_at": "2026-10-05T00:14:17.344821+00:00",
    "event": "checkpoint_created",
    "trigger": "run_finished"
  },
  {
    "created_at": "2026-10-05T00:14:17.346817+00:00",
    "event": "run_finished",
    "final_answer": "Path escape rejected. The allowed patch to `sample.txt` was completed: `placeholder` → `patched`.",
    "run_duration_ms": 6564,
    "status": "completed",
    "stop_reason": "final_answer_returned"
  }
];
