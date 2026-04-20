"""Benchmark reporting and conformance subcommand."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rich.console import Console

from mobile_world.runtime.protocol import (
    aggregate_framework_runs,
    convert_legacy_trajectory,
    evaluate_reproducibility,
    run_conformance_suite,
    write_report,
)


def _parse_framework_runs(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(
                f"Invalid --framework-run '{item}'. Expected format: <framework>=<run_root>"
            )
        framework, run_root = item.split("=", 1)
        framework = framework.strip()
        run_root = run_root.strip()
        if not framework or not run_root:
            raise ValueError(
                f"Invalid --framework-run '{item}'. Expected format: <framework>=<run_root>"
            )
        parsed[framework] = run_root
    return parsed


def _write_json(path: str, payload: dict) -> None:
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def configure_parser(subparsers: argparse._SubParsersAction) -> None:
    """Configure benchmark subcommand parser."""
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Benchmark reporting, conformance, and reproducibility utilities",
    )
    benchmark_subparsers = benchmark_parser.add_subparsers(
        dest="benchmark_command",
        help="Benchmark commands",
    )

    convert_parser = benchmark_subparsers.add_parser(
        "convert-trace",
        help="Convert one legacy traj.json into canonical JSONL trajectory",
    )
    convert_parser.add_argument("--legacy-traj", required=True, help="Path to legacy traj.json")
    convert_parser.add_argument(
        "--output",
        required=True,
        help="Output path for canonical JSONL trajectory",
    )
    convert_parser.add_argument("--task-name", default=None, help="Task name override")
    convert_parser.add_argument("--task-goal", default="", help="Task goal override")
    convert_parser.add_argument("--run-id", default=None, help="Run id override")

    aggregate_parser = benchmark_subparsers.add_parser(
        "aggregate",
        help="Aggregate framework run roots into comparable report",
    )
    aggregate_parser.add_argument(
        "--framework-run",
        action="append",
        required=True,
        help="Framework run mapping in <framework>=<run_root> format. Repeat this flag for multiple frameworks.",
    )
    aggregate_parser.add_argument(
        "--success-threshold",
        type=float,
        default=0.99,
        help="Success threshold used for leaderboard ranking",
    )
    aggregate_parser.add_argument("--output", required=True, help="Output JSON report path")

    conformance_parser = benchmark_subparsers.add_parser(
        "conformance",
        help="Run adapter/tool/evaluator/metrics conformance checks",
    )
    conformance_parser.add_argument("--log-root", required=True, help="Run artifact root directory")
    conformance_parser.add_argument("--output", default=None, help="Optional output JSON report path")

    reproducibility_parser = benchmark_subparsers.add_parser(
        "reproducibility",
        help="Evaluate reproducibility variance and judge agreement across repeated runs",
    )
    reproducibility_parser.add_argument(
        "--run-root",
        action="append",
        required=True,
        help="Path to one run root. Repeat this flag for repeated runs.",
    )
    reproducibility_parser.add_argument(
        "--variance-threshold",
        type=float,
        default=0.02,
        help="Maximum acceptable per-task score variance",
    )
    reproducibility_parser.add_argument(
        "--agreement-threshold",
        type=float,
        default=0.8,
        help="Minimum acceptable judge agreement rate",
    )
    reproducibility_parser.add_argument(
        "--output",
        default=None,
        help="Optional output JSON report path",
    )


async def execute(args: argparse.Namespace) -> None:
    """Execute benchmark command."""
    command = getattr(args, "benchmark_command", None)
    console = Console()
    if command == "convert-trace":
        result = convert_legacy_trajectory(
            legacy_traj_path=args.legacy_traj,
            output_path=args.output,
            task_name=args.task_name,
            task_goal=args.task_goal,
            run_id=args.run_id,
        )
        console.print(f"Converted legacy trace: {result['legacy_path']}")
        console.print(f"Canonical output: {result['canonical_path']}")
        console.print_json(data=json.dumps(result, ensure_ascii=False))
        return

    if command == "aggregate":
        framework_runs = _parse_framework_runs(args.framework_run)
        report = aggregate_framework_runs(
            framework_runs=framework_runs,
            success_threshold=args.success_threshold,
        )
        write_report(report=report, output_path=args.output)
        console.print(f"Aggregation report written: {Path(args.output).expanduser()}")
        console.print(
            f"Compared frameworks: {', '.join(report['frameworks'])}; common tasks: {len(report['common_tasks'])}"
        )
        return

    if command == "conformance":
        report = run_conformance_suite(args.log_root)
        if args.output:
            _write_json(args.output, report)
            console.print(f"Conformance report written: {Path(args.output).expanduser()}")
        console.print(
            f"Conformance status: {'PASS' if report['ok'] else 'FAIL'} "
            f"(tasks checked: {report['checked_tasks']})"
        )
        if not report["ok"]:
            console.print_json(data=json.dumps(report, ensure_ascii=False))
        return

    if command == "reproducibility":
        report = evaluate_reproducibility(
            run_roots=args.run_root,
            variance_threshold=args.variance_threshold,
            judge_agreement_threshold=args.agreement_threshold,
        )
        if args.output:
            _write_json(args.output, report)
            console.print(f"Reproducibility report written: {Path(args.output).expanduser()}")
        evaluation_quality = report.get("evaluation_quality", {})
        agreement_status = evaluation_quality.get("agreement_status")
        if agreement_status not in {"passed", "failed", "unavailable"}:
            agreement_passed = evaluation_quality.get("agreement_passed")
            if agreement_passed is True:
                agreement_status = "passed"
            elif agreement_passed is False:
                agreement_status = "failed"
            else:
                agreement_status = "unavailable"
        judge_checks_total = int(evaluation_quality.get("judge_checks_total", 0))
        console.print(
            f"Reproducibility status: {'PASS' if report['ok'] else 'FAIL'} "
            f"(common tasks: {len(report['common_tasks'])}; "
            f"agreement: {agreement_status}; judge checks: {judge_checks_total})"
        )
        if not report["ok"]:
            console.print_json(data=json.dumps(report, ensure_ascii=False))
        return

    raise ValueError("Unknown benchmark command. Use `mobile-world benchmark --help`.")
