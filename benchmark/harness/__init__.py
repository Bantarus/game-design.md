"""Phase 5 help-benchmark trial harness.

This package implements the trial-running infrastructure for the help-benchmark
described in `docs/v0.2-phase5-pre-registration.md` (locked at commit `27a4381`).

Architecture (subject to the pinned protocol):

    `tasks.py`        — load + freeze task definitions from `benchmark/tasks/*.yaml`.
    `conditions.py`   — build A / B / C condition payloads for a (task × game) cell.
    `instrument.py`   — abstract `Instrument` interface (sends a prompt, returns
                        a response + token counts); concrete classes for the
                        pinned Qwen bundle and the Claude transfer probe. Stubbed
                        until the runtime infra is wired up.
    `judge.py`        — abstract `Judge` interface (sends an output + rubric,
                        returns a score); concrete classes for the pinned
                        auxiliary LLM judge. Stubbed until the runtime infra is
                        wired up.
    `checklist.py`    — applies a task's objective intent checklist against
                        a subject's output, returning per-criterion boolean
                        verdicts.
    `calibration.py`  — runs the instrument calibration smoke run (structural
                        validity / seed-sensitivity / rubric reachability) and
                        the blinding-leak calibration.
    `run_trial.py`    — main entry point: parametrizes (subject, condition,
                        task, game), records tokens/tool-steps/outputs.

What's in this package vs. what's NOT:

    IN this package:
      - Code that is fully runnable today (task loading, condition payload
        building, checklist machinery — modulo the LLM-grader fallback).
      - Stubs for the LLM-dependent pieces (Instrument, Judge), with a
        MockInstrument and MockJudge that let the end-to-end path
        exercise without external infra.
      - The runtime contract (how trials are recorded, what the harness
        emits as an artifact).

    NOT in this package (deliberate):
      - The actual Qwen GGUF, llama.cpp build, sampling-params choice.
      - The actual auxiliary LLM judge model (Gemini / GPT-4o / etc.) and
        API client setup.
      - The trial-zero command line that fires N=20 runs per cell across
        660 outputs.

    These are listed in `benchmark/README.md` under "What's needed before
    trial zero." Each requires an explicit configuration commit before the
    harness can be used for real trials; the pre-reg requires the instrument
    bundle to be pinned at the harness-build commit SHA.

Pre-trial-zero status: the harness is a scaffold. Trial zero requires
(a) the runtime stubs replaced with real Instrument / Judge implementations,
(b) the calibration runs completed and recorded, and (c) the user's explicit
go-signal to fire trial zero. The pre-reg's chain ends at `27a4381` and any
subsequent changes to this harness BEFORE trial zero remain in the redirect
window; AFTER trial zero, the harness SHA is frozen alongside the pre-reg.
"""
