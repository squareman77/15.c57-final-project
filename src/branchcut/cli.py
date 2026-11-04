"""Command line: ``python run.py <command>`` (or ``branchcut <command>`` once installed)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEMPLATES = {"cuts": "_template_cuts.py", "branching": "_template_branching.py"}


def _solver():
    from branchcut.solver import GurobiSolver
    return GurobiSolver()


def cmd_list(args) -> int:
    from branchcut.pipeline.registry import discover
    from branchcut.scenarios import SOURCES
    print(discover(args.approaches).describe())
    print("scenario families:", ", ".join(SOURCES))
    configs = sorted(Path("configs").glob("*.toml"))
    print("configs:", ", ".join(str(p) for p in configs) or "none")
    return 0


def cmd_validate(args) -> int:
    from branchcut.pipeline.registry import discover
    from branchcut.pipeline.validation import validate
    registry = discover(args.approaches)
    names = args.names or registry.approaches
    if not names:
        print(f"no approaches found in {args.approaches}/")
        return 1
    reports = validate(names, registry, _solver())
    for report in reports:
        print(f"{report}\n")
    failed = [r.name for r in reports if not r.passed]
    print(f"FAILED: {', '.join(failed)}" if failed else f"all {len(reports)} approaches passed")
    return 1 if failed else 0


def cmd_bench(args) -> int:
    from branchcut.pipeline.benchmark import ValidationFailed, plan, run_benchmark
    from branchcut.pipeline.config import load_config
    from branchcut.pipeline.registry import discover
    config = load_config(args.config)
    registry = discover(args.approaches)
    if args.dry_run:
        instances, strategies = plan(config, registry, args.data, args.only)
        print(f"{config.name}: {len(instances)} instances x {len(strategies)} strategies x "
              f"{len(config.branching)} branching x {len(config.seeds)} seeds")
        for inst in instances:
            print(f"  {inst.family:<18} {inst.name:<36} {inst.path}")
        for label, s in strategies.items():
            print(f"  strategy {label:<20} cuts={s.cuts} {dict(s.cut_options) or ''} {dict(s.solver_params) or ''}")
        return 0
    try:
        run_dir = run_benchmark(config, registry, _solver(), results_dir=args.results, data_dir=args.data,
                                resume=args.resume, only=args.only, skip_validation=args.skip_validation)
    except ValidationFailed as exc:
        print(f"\n{exc}; fix the approach or rerun with --skip-validation")
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted; finished runs are saved. Continue with --resume <results dir>.")
        return 130
    print("\n" + (run_dir / "summary.md").read_text(encoding="utf-8"))
    return 0


def cmd_report(args) -> int:
    from branchcut.pipeline.report import summarize
    run_dir = Path(args.run_dir)
    if not (run_dir / "runs.jsonl").exists():          # experiment dir: take the latest run
        runs = sorted(p for p in run_dir.iterdir() if (p / "runs.jsonl").exists()) if run_dir.is_dir() else []
        if not runs:
            print(f"no runs.jsonl under {run_dir}")
            return 1
        run_dir = runs[-1]
    print(summarize(run_dir))
    return 0


def cmd_fetch(args) -> int:
    from branchcut.scenarios import miplib
    names = list(args.names)
    if args.benchmark_list:
        names += miplib.benchmark_names(args.benchmark_list)[:args.limit]
    if not names:
        print("give instance names or --benchmark-list")
        return 1
    miplib.fetch(names, Path(args.data) / "miplib", overwrite=args.overwrite)
    return 0


def cmd_new(args) -> int:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.name):
        print("name must be lower_snake_case")
        return 1
    target = Path(args.approaches) / f"{args.name}.py"
    if target.exists():
        print(f"{target} already exists")
        return 1
    template = (Path(args.approaches) / TEMPLATES[args.kind]).read_text(encoding="utf-8")
    camel = "".join(part.title() for part in args.name.split("_"))
    placeholder = "MyCuts" if args.kind == "cuts" else "MyBranching"
    text = template.replace(placeholder, camel).replace(f'"{_snake(placeholder)}"', f'"{args.name}"')
    target.write_text(text, encoding="utf-8")
    print(f"created {target}; validate it with: python run.py validate {args.name}")
    return 0


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="branchcut", description="Cut and branching-rule benchmarking on Gurobi.")
    parser.add_argument("--approaches", default="approaches", help="directory of approach files")
    parser.add_argument("--data", default="data", help="instance directory")
    parser.add_argument("--results", default="results", help="results directory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show cut generators, branching rules, families and configs")
    p = sub.add_parser("validate", help="run the correctness checks on approaches")
    p.add_argument("names", nargs="*", help="approach names (default: all in approaches/)")
    p = sub.add_parser("bench", help="run an experiment config")
    p.add_argument("config")
    p.add_argument("--resume", help="continue an interrupted run in this results directory")
    p.add_argument("--only", nargs="+", help="run only these strategy labels")
    p.add_argument("--skip-validation", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="show the matrix without solving")
    p = sub.add_parser("report", help="summarize a results directory (or the latest run of an experiment)")
    p.add_argument("run_dir")
    p = sub.add_parser("fetch-miplib", help="download MIPLIB 2017 instances into data/miplib")
    p.add_argument("names", nargs="*")
    p.add_argument("--benchmark-list", help="take names from a .test list, e.g. data/benchmark-v2.test")
    p.add_argument("--limit", type=int, help="with --benchmark-list: first N names only")
    p.add_argument("--overwrite", action="store_true")
    p = sub.add_parser("new-approach", help="create approaches/<name>.py from a template")
    p.add_argument("name")
    p.add_argument("--kind", choices=sorted(TEMPLATES), default="cuts")

    args = parser.parse_args(argv)
    handler = {"list": cmd_list, "validate": cmd_validate, "bench": cmd_bench, "report": cmd_report,
               "fetch-miplib": cmd_fetch, "new-approach": cmd_new}[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
