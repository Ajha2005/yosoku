"""Run the whole pipeline after the collectors: label, evaluate, decide. Then open the dashboard.

    python collectors/merge.py
    python -m yosoku.run                  # labels/, reports/ (incl. ablation and the decision clock), predictions/predictions.json
    python -m yosoku.run --final          # once, at the end: also scores the 2025 test titles
    python -m yosoku.export_web           # then see web/ (the dashboard)
"""

import argparse
import subprocess
import sys

from yosoku.data import ROOT, add_folder_arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_folder_arguments(parser)
    parser.add_argument("--upcoming-dir", default="data/upcoming")
    parser.add_argument("--final", action="store_true", help="also score the 2025 test titles (do this once)")
    args = parser.parse_args()
    folders = ["--data-dir", args.data_dir, "--out-dir", args.out_dir]
    final = ["--final"] if args.final else []
    upcoming = ["--upcoming-dir", args.upcoming_dir]
    for module, extra in (("yosoku.labels", upcoming), ("yosoku.evaluate", final), ("yosoku.ablation", []),
                          ("yosoku.clock", []), ("yosoku.decision", [*final, *upcoming])):
        print(f"== {module}")
        subprocess.run([sys.executable, "-m", module, *folders, *extra], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
