#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


ROSDEP_FILES = (
    ("rosdep/osx-homebrew.yaml", " osx"),
    ("rosdep/base.yaml", ""),
    ("rosdep/python.yaml", ""),
    ("rosdep/ruby.yaml", ""),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install a rosdep source list that reads the vendored rosdistro snapshot."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root containing vendor/rosdistro.",
    )
    parser.add_argument(
        "--target",
        default=Path("/etc/ros/rosdep/sources.list.d/20-default.list"),
        type=Path,
        help="Output rosdep source list path.",
    )
    return parser.parse_args()


def file_url(path: Path) -> str:
    return path.resolve().as_uri()


def main() -> int:
    args = parse_args()
    snapshot = args.repo_root.resolve() / "vendor" / "rosdistro"
    index = snapshot / "index-noetic.yaml"

    required = [index]
    required.extend(snapshot / relpath for relpath, _ in ROSDEP_FILES)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("missing vendored rosdistro files:\n" + "\n".join(missing))

    lines = ["# Generated from vendor/rosdistro by scripts/install_rosdep_snapshot.py"]
    for relpath, suffix in ROSDEP_FILES:
        lines.append(f"yaml {file_url(snapshot / relpath)}{suffix}")
    lines.append("")

    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text("\n".join(lines))
    print(f"wrote {args.target}")
    print(f"ROSDISTRO_INDEX_URL={file_url(index)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
