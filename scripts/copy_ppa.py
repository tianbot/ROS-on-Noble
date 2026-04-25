#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time

from launchpadlib.launchpad import Launchpad


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy published source packages and binaries between Launchpad PPAs."
    )
    parser.add_argument("--source-owner", default="ros-for-jammy")
    parser.add_argument("--source-ppa", default="noble")
    parser.add_argument("--target-owner", default="tianbot")
    parser.add_argument("--target-ppa", default="ros2go")
    parser.add_argument("--series", default="noble")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List packages without submitting copy requests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lp = Launchpad.login_with("tianbot-ppa-copy", "production", version="devel")
    series = lp.distributions["ubuntu"].getSeries(name_or_version=args.series)
    source = lp.people[args.source_owner].getPPAByName(name=args.source_ppa)
    target = lp.people[args.target_owner].getPPAByName(name=args.target_ppa)

    target_existing = set()
    for status in ("Pending", "Published"):
        for pub in target.getPublishedSources(status=status, distro_series=series):
            target_existing.add((pub.source_package_name, pub.source_package_version))

    seen = set()
    to_copy = []
    for pub in source.getPublishedSources(status="Published", distro_series=series):
        key = (pub.source_package_name, pub.source_package_version)
        if key in seen:
            continue
        seen.add(key)
        if key not in target_existing:
            to_copy.append(pub)

    print(f"source: {source.reference} {source.web_link}")
    print(f"target: {target.reference} {target.web_link}")
    print(f"series: {args.series}")
    print(f"to copy: {len(to_copy)}")

    failures = []
    for index, pub in enumerate(to_copy, start=1):
        name = pub.source_package_name
        version = pub.source_package_version
        print(f"[{index}/{len(to_copy)}] {name} {version}", flush=True)
        if args.dry_run:
            continue
        try:
            target.copyPackage(
                source_name=name,
                version=version,
                from_archive=source,
                from_series=args.series,
                from_pocket="Release",
                to_series=args.series,
                to_pocket="Release",
                include_binaries=True,
            )
        except Exception as exc:
            message = str(exc)
            failures.append((name, version, message))
            print(f"  ERROR: {message}", flush=True)
            time.sleep(1)

    if failures:
        print("\nFailures:", file=sys.stderr)
        for name, version, message in failures:
            print(f"- {name} {version}: {message}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("dry run complete")
    else:
        print("copy requests submitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
