#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


URI_RE = re.compile(r"^(?P<prefix>\s*uri:\s*)(?P<url>https?://\S+)(?P<suffix>\s*)$")
LOCAL_NAME_RE = re.compile(r"^\s*local-name:\s*(?P<name>\S+)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mirror tarball URLs from a .rosinstall file and generate a rewritten input file."
    )
    parser.add_argument("--input", default="noetic-desktop.rosinstall", type=Path)
    parser.add_argument("--mirror-dir", default=Path("mirror/rosinstall-sources"), type=Path)
    parser.add_argument("--output", default=Path("noetic-desktop.mirrored.rosinstall"), type=Path)
    parser.add_argument(
        "--base-url",
        help="Public URL prefix for mirrored files. Defaults to file://<mirror-dir>.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report the files that would be downloaded and rewritten.",
    )
    parser.add_argument(
        "--rewrite-only",
        action="store_true",
        help="Generate the rewritten .rosinstall without downloading mirror files.",
    )
    parser.add_argument("--retries", default=3, type=int, help="Download attempts per URL.")
    parser.add_argument("--timeout", default=60, type=int, help="Per-request timeout in seconds.")
    return parser.parse_args()


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.+-]+", "-", value).strip("-") or "source"


def cache_name(url: str, local_name: str | None, used_names: set[str]) -> str:
    parsed = urlparse(url)
    basename = os.path.basename(parsed.path) or "source.tar.gz"
    prefix = safe_name(local_name) if local_name else "source"
    candidate = f"{prefix}-{safe_name(basename)}"
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    stem, suffix = os.path.splitext(candidate)
    if stem.endswith(".tar") and suffix in {".gz", ".xz", ".bz2"}:
        stem, tar_suffix = os.path.splitext(stem)
        suffix = tar_suffix + suffix
    index = 2
    while True:
        numbered = f"{stem}-{index}{suffix}"
        if numbered not in used_names:
            used_names.add(numbered)
            return numbered
        index += 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path, timeout: int) -> None:
    tmp = target.with_suffix(target.suffix + ".tmp")
    with urlopen(url, timeout=timeout) as response, tmp.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    tmp.replace(target)


def mirror_url(base_url: str, name: str) -> str:
    return f"{base_url.rstrip('/')}/{name}"


def main() -> int:
    args = parse_args()
    lines = args.input.read_text().splitlines()
    args.mirror_dir.mkdir(parents=True, exist_ok=True)

    base_url = args.base_url
    if base_url is None:
        base_url = args.mirror_dir.resolve().as_uri()

    manifest = []
    rewritten = []
    failures = []
    used_names: set[str] = set()
    current_local_name = None
    for line in lines:
        local_name_match = LOCAL_NAME_RE.match(line)
        if local_name_match:
            current_local_name = local_name_match.group("name")
            rewritten.append(line)
            continue

        match = URI_RE.match(line)
        if not match:
            rewritten.append(line)
            continue

        url = match.group("url")
        name = cache_name(url, current_local_name, used_names)
        target = args.mirror_dir / name
        if args.dry_run:
            status = "present" if target.exists() else "missing"
        elif args.rewrite_only:
            status = "rewrite-only"
        else:
            if not target.exists():
                print(f"download {url}", flush=True)
                for attempt in range(1, args.retries + 1):
                    try:
                        download(url, target, args.timeout)
                        break
                    except Exception as exc:  # noqa: BLE001 - report exact download failure.
                        if attempt == args.retries:
                            failures.append({"url": url, "error": repr(exc)})
                            print(f"failed {url}: {exc!r}", flush=True)
                        else:
                            time.sleep(attempt * 5)
                status = "present" if target.exists() else "failed"
            else:
                status = "present"

        sha256 = sha256_file(target) if target.exists() else None
        mirrored = mirror_url(base_url, name)
        rewritten.append(f"{match.group('prefix')}{mirrored}{match.group('suffix')}")
        manifest.append(
            {
                "source_url": url,
                "mirror_url": mirrored,
                "cache_name": name,
                "sha256": sha256,
                "status": status,
            }
        )

    manifest_path = args.mirror_dir / "manifest.json"
    if not args.dry_run:
        args.output.write_text("\n".join(rewritten) + "\n")
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    missing = sum(1 for item in manifest if item["status"] == "missing")
    failed = sum(1 for item in manifest if item["status"] == "failed")
    print(f"urls: {len(manifest)}")
    print(f"missing: {missing}")
    print(f"failed: {failed}")
    print(f"mirror dir: {args.mirror_dir}")
    print(f"output: {args.output}")
    print(f"manifest: {manifest_path}")
    if failures:
        failures_path = args.mirror_dir / "failures.json"
        failures_path.write_text(json.dumps(failures, indent=2, sort_keys=True) + "\n")
        print(f"failures: {failures_path}")
    return 1 if (args.dry_run and missing) or failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
