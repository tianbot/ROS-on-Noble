#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlretrieve

from launchpadlib.launchpad import Launchpad


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import one source package from a Launchpad PPA into sources/<package>/<version>."
    )
    parser.add_argument("package", help="Exact source package name, e.g. ros-noetic-rosbag")
    parser.add_argument("--version", help="Exact source package version. Defaults to newest published.")
    parser.add_argument("--owner", default="ros-for-jammy")
    parser.add_argument("--ppa", default="noble")
    parser.add_argument("--series", default="noble")
    parser.add_argument("--output", default="sources")
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Extract only; do not initialize a Git repository in the source tree.",
    )
    return parser.parse_args()


def safe_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]+", "_", value)


def run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> int:
    args = parse_args()
    if not shutil.which("dpkg-source"):
        print("dpkg-source is required; run this on Ubuntu/Debian with dpkg-dev installed.", file=sys.stderr)
        return 2

    lp = Launchpad.login_anonymously("tianbot-source-import", "production", version="devel")
    series = lp.distributions["ubuntu"].getSeries(name_or_version=args.series)
    archive = lp.people[args.owner].getPPAByName(name=args.ppa)

    matches = [
        pub
        for pub in archive.getPublishedSources(status="Published", distro_series=series)
        if pub.source_package_name == args.package
        and (args.version is None or pub.source_package_version == args.version)
    ]
    if not matches:
        print(f"No published source found for {args.package}", file=sys.stderr)
        return 1

    pub = sorted(matches, key=lambda item: item.date_published, reverse=True)[0]
    version = pub.source_package_version
    root = Path(args.output) / safe_component(args.package) / safe_component(version)
    download_dir = root / "download"
    tree_dir = root / "tree"
    download_dir.mkdir(parents=True, exist_ok=True)

    urls = pub.sourceFileUrls()
    if not urls:
        print(f"No source files listed for {args.package} {version}", file=sys.stderr)
        return 1

    print(f"importing {args.package} {version}")
    print(f"from {archive.reference} {archive.web_link}")

    dsc_path = None
    for url in urls:
        filename = os.path.basename(urlparse(url).path)
        target = download_dir / filename
        if not target.exists():
            print(f"download {filename}")
            urlretrieve(url, target)
        if filename.endswith(".dsc"):
            dsc_path = target

    if dsc_path is None:
        print("No .dsc file found in source file list.", file=sys.stderr)
        return 1

    if tree_dir.exists():
        shutil.rmtree(tree_dir)
    tree_dir.mkdir(parents=True)
    run(["dpkg-source", "-x", str(dsc_path), str(tree_dir)])

    if not args.no_git:
        run(["git", "init"], cwd=tree_dir)
        run(["git", "add", "."], cwd=tree_dir)
        run(["git", "commit", "-m", f"Import {args.package} {version} from {archive.reference}"], cwd=tree_dir)
        run(["git", "tag", f"import/{safe_component(version)}"], cwd=tree_dir)

    print(f"source tree: {tree_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
