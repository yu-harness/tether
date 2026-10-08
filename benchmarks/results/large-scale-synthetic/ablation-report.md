# Pico Large-Scale Experiment Report

## Executive Summary
- Experiment mode: synthetic
- Fixed benchmark tasks: 12
- Large-scale memory tasks: 12
- Context stress configurations: 12
- Security scenarios: 10

## Context Governance
- Synthetic stress prompt chars: 6262 vs 8208
- Average prompt compression ratio across context matrix: 25.11%
- Max prompt compression ratio across context matrix: 37.19%

## Memory Experiments
- Small memory experiment repeated reads: 0 vs 3
- Large memory experiment repeated reads: 0 vs 60
- Large memory experiment avg tool steps: 0.00 vs 1.00

## Security Experiments
- Security event counts: {"approval_denied": 3, "path_escape": 9, "read_only_block": 3}
- Tool error code counts: {"approval_denied": 6, "invalid_arguments": 21, "repeated_identical_call": 3}

## Provider Experiments
- none

## Resume-Safe Claims
- Long-context stress scenario: prompt length reduced from 8208 to 6262.
- Large-scale memory experiment: repeated reads reduced from 60 to 0.
- Platform facts: 12 benchmark tasks, 7 tool types, 3 run artifacts.

