#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_PATHS = (
    "README.md",
    "noetic-desktop.rosinstall",
    ".github/workflows/main.yml",
    "debian/control",
    "debian/rules",
    "docs/source-maintenance.md",
)

URL_RE = re.compile(r"https?://[^\s'\"<>\\)]+")
NETWORK_COMMAND_RE = re.compile(
    r"\b(?:curl|wget|git\s+clone|pip(?:3)?\s+install|npm\s+install|go\s+get)\b"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit external source and network references used by the ROS-on-Noble maintenance tree."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_PATHS,
        help="Files to scan. Defaults to the known maintenance/build entry points.",
    )
    return parser.parse_args()


def classify_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    if "gitee.com" in host:
        return "high: gitee dependency"
    if "/archive/refs/heads/" in path or "/archive/" in path and path.endswith(".tar.gz") and "/release/" not in path:
        return "medium: archive tarball outside ROS release tags"
    if "github.com" in host:
        return "medium: github archive"
    if "launchpad.net" in host:
        return "low: launchpad source archive"
    return "review"


def main() -> int:
    args = parse_args()
    urls: list[tuple[str, int, str, str]] = []
    commands: list[tuple[str, int, str]] = []

    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
            for match in URL_RE.finditer(line):
                url = match.group(0).rstrip(".,")
                urls.append((str(path), lineno, url, classify_url(url)))
            if NETWORK_COMMAND_RE.search(line):
                commands.append((str(path), lineno, line.strip()))

    by_host = collections.Counter(urlparse(url).netloc.lower() for _, _, url, _ in urls)
    by_class = collections.Counter(kind for *_, kind in urls)

    print("External URL summary")
    print("====================")
    print(f"URLs: {len(urls)}")
    for host, count in by_host.most_common():
        print(f"{count:4} {host}")
    print()

    print("Risk classes")
    print("============")
    for kind, count in by_class.most_common():
        print(f"{count:4} {kind}")
    print()

    if commands:
        print("Network-capable commands")
        print("========================")
        for path, lineno, line in commands:
            print(f"{path}:{lineno}: {line}")
        print()

    print("High and medium URL references")
    print("==============================")
    for path, lineno, url, kind in urls:
        if kind.startswith(("high:", "medium:")):
            print(f"{path}:{lineno}: {kind}: {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
