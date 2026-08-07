from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .errors import QlibxError
from .journal import ActionJournal
from .materialization import (
    materialize_from_config,
    preflight_materialization_config,
    validate_materialized_path,
)
from .profiles import get_profile, list_profiles
from .registration import inspect_registration_bundle, register_bundle
from .research import run_eligibility_audit, run_study


def _print_json(value: object, *, stream: object = sys.stdout) -> None:
    def default(item: object) -> object:
        scalar = getattr(item, "item", None)
        if callable(scalar):
            return scalar()
        if isinstance(item, Path):
            return str(item)
        raise TypeError(
            f"Object of type {type(item).__name__} is not JSON serializable"
        )

    print(
        json.dumps(
            value, ensure_ascii=False, indent=2, sort_keys=True, default=default
        ),
        file=stream,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qlibx", description="Agent-facing alpha research interfaces"
    )
    parser.add_argument(
        "--project-root", default=".", help="Project root (default: current directory)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    profile = subparsers.add_parser("profile", help="Inspect Qlib target profiles")
    profile_subparsers = profile.add_subparsers(dest="profile_command", required=True)
    profile_subparsers.add_parser("list", help="List installed target profiles")
    profile_show = profile_subparsers.add_parser("show", help="Show one target profile")
    profile_show.add_argument("profile_id")

    data = subparsers.add_parser("data", help="Materialize and validate data")
    data_subparsers = data.add_subparsers(dest="data_command", required=True)
    preflight = data_subparsers.add_parser(
        "preflight", help="Validate mappings without reading full datasets"
    )
    preflight.add_argument(
        "--config", required=True, help="Project-relative JSON materialization config"
    )
    materialize = data_subparsers.add_parser(
        "materialize", help="Materialize a Qlib-compatible research dataset"
    )
    materialize.add_argument(
        "--config", required=True, help="Project-relative JSON materialization config"
    )
    validate = data_subparsers.add_parser(
        "validate", help="Validate a materialized Qlib dataset"
    )
    validate.add_argument(
        "--target",
        required=True,
        help="Project-relative materialized dataset directory",
    )

    inspect = data_subparsers.add_parser(
        "inspect", help="Inspect and resolve a dataset-registration bundle"
    )
    inspect.add_argument(
        "--config", required=True, help="Project-relative JSON registration bundle"
    )
    register = data_subparsers.add_parser(
        "register", help="Register confirmed dataset mappings and snapshots"
    )
    register.add_argument(
        "--config", required=True, help="Project-relative JSON registration bundle"
    )

    research = subparsers.add_parser(
        "research", help="Audit and execute research studies"
    )
    research_subparsers = research.add_subparsers(
        dest="research_command", required=True
    )
    audit = research_subparsers.add_parser(
        "audit", help="Run the preregistered eligibility and data-quality audit"
    )
    audit.add_argument("--config", required=True, help="Project-relative study config")
    run = research_subparsers.add_parser(
        "run", help="Execute or reproduce a frozen research study"
    )
    run.add_argument("--config", required=True, help="Project-relative study config")

    journal = subparsers.add_parser("journal", help="Query append-only action events")
    journal_subparsers = journal.add_subparsers(dest="journal_command", required=True)
    query = journal_subparsers.add_parser("query", help="Query action-journal events")
    query.add_argument("--operation-id")
    query.add_argument("--action")
    query.add_argument("--phase")
    query.add_argument("--actor-id")
    query.add_argument("--limit", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_root = Path(args.project_root).resolve()
    try:
        if args.command == "profile":
            journal = ActionJournal(project_root)
            action = (
                "profile.list" if args.profile_command == "list" else "profile.show"
            )
            parameters = (
                {}
                if args.profile_command == "list"
                else {"profile_id": args.profile_id}
            )
            with journal.operation(
                action, read_only=True, inputs={"parameters": parameters}
            ) as operation:
                if args.profile_command == "list":
                    result = [
                        {
                            "profile_id": profile.profile_id,
                            "description": profile.description,
                        }
                        for profile in list_profiles()
                    ]
                else:
                    result = get_profile(args.profile_id).to_dict()
                operation.succeed(outputs={"result_summary": result})
                _print_json(result)
                return 0
        if args.command == "data" and args.data_command == "preflight":
            config_path = (project_root / args.config).resolve()
            _print_json(
                preflight_materialization_config(config_path, project_root=project_root)
            )
            return 0
        if args.command == "data" and args.data_command == "materialize":
            config_path = (project_root / args.config).resolve()
            manifest = materialize_from_config(config_path, project_root=project_root)
            _print_json(
                {
                    "status": "succeeded",
                    "materialization_id": manifest["materialization_id"],
                    "output_dir": manifest["output_dir"],
                    "calendar": manifest["calendar"],
                    "universes": manifest["universes"],
                    "features": manifest["features"],
                    "validation": manifest.get("validation"),
                }
            )
            return 0
        if args.command == "data" and args.data_command == "validate":
            target = (project_root / args.target).resolve()
            _print_json(validate_materialized_path(target, project_root=project_root))
            return 0
        if args.command == "data" and args.data_command == "inspect":
            config_path = (project_root / args.config).resolve()
            _print_json(
                inspect_registration_bundle(config_path, project_root=project_root)
            )
            return 0
        if args.command == "data" and args.data_command == "register":
            config_path = (project_root / args.config).resolve()
            _print_json(register_bundle(config_path, project_root=project_root))
            return 0
        if args.command == "research" and args.research_command == "audit":
            config_path = (project_root / args.config).resolve()
            _print_json(run_eligibility_audit(config_path, project_root=project_root))
            return 0
        if args.command == "research" and args.research_command == "run":
            config_path = (project_root / args.config).resolve()
            _print_json(run_study(config_path, project_root=project_root))
            return 0
        if args.command == "journal" and args.journal_command == "query":
            events = ActionJournal(project_root).query(
                operation_id=args.operation_id,
                action=args.action,
                phase=args.phase,
                actor_id=args.actor_id,
                limit=args.limit,
            )
            _print_json(events)
            return 0
        raise AssertionError("Unhandled command")
    except QlibxError as exc:
        _print_json(
            {
                "status": "failed",
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "details": exc.details,
                },
            },
            stream=sys.stderr,
        )
        return 2
