"""Download sources S1-S4 into static/documents/ and update the manifest.

Usage:
    python fetch.py              # all sources
    python fetch.py --only S1 S4 # selected sources

After a run that reports new or changed documents, rebuild the index:
    python build_index.py
"""

import argparse

from snu_central.config import load_config, load_sources, project_path
from snu_central.fetch.pipeline import run_fetch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", metavar="SOURCE", help="source IDs to fetch, e.g. S1 S4")
    args = parser.parse_args()

    cfg, sources = load_config(), load_sources()
    if args.only:
        unknown = set(args.only) - set(sources)
        if unknown:
            parser.error(f"unknown source(s): {', '.join(sorted(unknown))}; choose from {', '.join(sources)}")

    report = run_fetch(cfg, sources, args.only)

    print()
    for status in ("new", "changed", "unchanged", "failed", "removed"):
        items = report.by_status.get(status, [])
        print(f"{status:>10}: {len(items)}")
        if status in ("new", "changed", "removed"):
            for item in items:
                print(f"            {item}")
    if report.duplicates:
        print(f"\nDuplicates (not indexed): {len(report.duplicates)}")
        for d in report.duplicates:
            print(f"  {d}")
    if report.skipped:
        print(f"\nSkipped (not indexed): {len(report.skipped)}")
        for r in report.skipped:
            print(f"  {r}")
    if report.failures:
        print(f"\nFailures: {len(report.failures)}")
        for f in report.failures:
            print(f"  {f}")

    print(f"\nManifest: {project_path(cfg, 'manifest')}")
    if report.by_status.get("new") or report.by_status.get("changed") or report.by_status.get("removed"):
        print("Documents changed -> run: python build_index.py")


if __name__ == "__main__":
    main()
