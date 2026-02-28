"""
run.py — Entry point for pulpo-hypo framework

Usage:
    python run.py abc_reversal              # Run hypothesis abc_reversal
    python run.py abc_reversal --signals-only       # Show signals, skip backtest
    python run.py abc_reversal --refresh-data       # Force re-download data
    python run.py --list                    # List all available hypotheses
"""

import sys
import importlib
import importlib.util
import argparse
from pathlib import Path


HYPOTHESES_DIR = Path(__file__).parent / "hypotheses"


def discover_hypotheses() -> dict[str, Path]:
    """Find all hypothesis folders."""
    hypos = {}
    if not HYPOTHESES_DIR.exists():
        return hypos
    for folder in sorted(HYPOTHESES_DIR.iterdir()):
        if folder.is_dir() and (folder / "hypothesis.py").exists():
            # Key: the folder name
            hypos[folder.name] = folder
    return hypos


def list_hypotheses():
    hypos = discover_hypotheses()
    seen = set()
    print("\nAvailable hypotheses:\n")
    for key, path in hypos.items():
        if path in seen:
            continue
        seen.add(path)
        config_path = path / "config.json"
        name = path.name
        desc = ""
        if config_path.exists():
            import json
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            name = cfg.get("name", path.name)
            desc = cfg.get("description", "")
        print(f"  {path.name:20s}  {name}")
        if desc:
            print(f"        {desc}")
    print()


def load_hypothesis(folder: Path):
    """Dynamically import and instantiate the Hypothesis class."""
    spec = importlib.util.spec_from_file_location(
        "hypothesis", folder / "hypothesis.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Hypothesis(hypothesis_dir=folder)


def main():
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="pulpo-hypo — Trading Hypothesis Framework"
    )
    parser.add_argument(
        "hypothesis",
        nargs="?",
        help="Hypothesis ID to run (e.g. abc_reversal)"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available hypotheses"
    )
    parser.add_argument(
        "--signals-only",
        action="store_true",
        help="Only show signals, skip backtesting and reporting"
    )
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="Force re-download of data even if cache exists"
    )

    args = parser.parse_args()

    if args.list or not args.hypothesis:
        list_hypotheses()
        if not args.hypothesis:
            parser.print_help()
        return

    hypos = discover_hypotheses()
    key = args.hypothesis.lower()

    if key not in hypos:
        print(f"\n❌ Hypothesis '{args.hypothesis}' not found.\n")
        list_hypotheses()
        sys.exit(1)

    folder = hypos[key]
    print(f"\nLoading: {folder.name}")

    hypo = load_hypothesis(folder)
    hypo.run(
        refresh_data=args.refresh_data,
        signals_only=args.signals_only,
    )


if __name__ == "__main__":
    main()
