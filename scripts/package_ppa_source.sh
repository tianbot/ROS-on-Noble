#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/package_ppa_source.sh [options]

Build a Launchpad PPA source upload for the bundled ROS-on-Noble package.

Options:
  --stage-dir DIR        Staging/output directory (default: /tmp/ros-ppa-source)
  --mirror-base URL      Base URL used for rosinstall mirror rewrite
                         (default: ROS_SOURCE_MIRROR_BASE or file://<repo>/mirror/rosinstall-sources)
  --use-existing-src DIR Copy an already imported ROS workspace src directory instead of running vcs import
  --include-orig MODE    dpkg-buildpackage orig mode: -sa or -sd (default: -sa)
  --sign                 Sign the source package (default)
  --no-sign              Build unsigned source package for validation
  --upload               Upload the generated source changes with dput
  --ppa TARGET           dput target (default: ppa:tianbot/ros2go)
  -h, --help             Show this help

Examples:
  scripts/package_ppa_source.sh --no-sign --use-existing-src /tmp/ws/ROS-on-Noble/src
  scripts/package_ppa_source.sh --upload --use-existing-src /tmp/ws/ROS-on-Noble/src
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stage_dir="/tmp/ros-ppa-source"
mirror_base="${ROS_SOURCE_MIRROR_BASE:-}"
existing_src=""
include_orig="-sa"
sign=1
upload=0
ppa_target="ppa:tianbot/ros2go"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stage-dir)
      stage_dir="${2:?missing --stage-dir value}"
      shift 2
      ;;
    --mirror-base)
      mirror_base="${2:?missing --mirror-base value}"
      shift 2
      ;;
    --use-existing-src)
      existing_src="${2:?missing --use-existing-src value}"
      shift 2
      ;;
    --include-orig)
      include_orig="${2:?missing --include-orig value}"
      shift 2
      ;;
    --sign)
      sign=1
      shift
      ;;
    --no-sign)
      sign=0
      shift
      ;;
    --upload)
      upload=1
      shift
      ;;
    --ppa)
      ppa_target="${2:?missing --ppa value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ "$include_orig" == "-sa" || "$include_orig" == "-sd" ]] || die "--include-orig must be -sa or -sd"
[[ -x "$repo_root/debian/rules" ]] || chmod +x "$repo_root/debian/rules"
command -v dpkg-parsechangelog >/dev/null || die "dpkg-parsechangelog is required"
command -v dpkg-buildpackage >/dev/null || die "dpkg-buildpackage is required"
command -v rsync >/dev/null || die "rsync is required"
command -v tar >/dev/null || die "tar is required"

if [[ "$upload" -eq 1 ]]; then
  command -v dput >/dev/null || die "dput is required for --upload"
  [[ "$sign" -eq 1 ]] || die "--upload requires signed source changes; remove --no-sign"
fi

source_name="$(dpkg-parsechangelog -l "$repo_root/debian/changelog" -SSource)"
full_version="$(dpkg-parsechangelog -l "$repo_root/debian/changelog" -SVersion)"
upstream_version="${full_version%%-*}"
work_dir="$stage_dir/${source_name}-${upstream_version}"
orig_tar="$stage_dir/${source_name}_${upstream_version}.orig.tar.xz"
changes_file="$stage_dir/${source_name}_${full_version}_source.changes"

if [[ -z "$mirror_base" ]]; then
  mirror_base="$(python3 - <<PY
from pathlib import Path
print((Path("$repo_root") / "mirror" / "rosinstall-sources").resolve().as_uri())
PY
)"
fi

echo "source: $source_name"
echo "version: $full_version"
echo "stage: $stage_dir"
echo "work: $work_dir"
echo "mirror base: $mirror_base"

rm -rf "$work_dir"
mkdir -p "$stage_dir"

rsync -a \
  --exclude .git \
  --exclude .omx \
  --exclude .venv \
  --exclude src \
  --exclude build_isolated \
  --exclude devel_isolated \
  --exclude install_isolated \
  --exclude 'debian/ros-noetic-desktop-full' \
  --exclude 'debian/.debhelper' \
  --exclude 'debian/files' \
  --exclude 'debian/*.substvars' \
  "$repo_root/" "$work_dir/"

cd "$work_dir"

if [[ -n "$existing_src" ]]; then
  [[ -d "$existing_src/catkin" ]] || die "--use-existing-src must point to a ROS workspace src directory containing catkin"
  mkdir -p src
  rsync -a \
    --exclude .git \
    --exclude .svn \
    --exclude .hg \
    --exclude build \
    --exclude devel \
    --exclude install \
    "$existing_src/" src/
else
  command -v vcs >/dev/null || die "vcs is required unless --use-existing-src is provided"
  python3 scripts/mirror_rosinstall_sources.py \
    --rewrite-only \
    --base-url "$mirror_base" \
    --output noetic-desktop.mirrored.rosinstall
  rm -rf src
  mkdir -p src
  vcs import --input noetic-desktop.mirrored.rosinstall ./src
fi

find src -name .git -type d -prune -exec rm -rf {} +
find src -name .svn -type d -prune -exec rm -rf {} +
find src -name .hg -type d -prune -exec rm -rf {} +
find . -name '._*' -delete
find . -name __pycache__ -type d -prune -exec rm -rf {} +
find . -name '*.pyc' -delete
rm -rf build_isolated devel_isolated install_isolated
rm -rf debian/ros-noetic-desktop-full debian/.debhelper debian/files debian/*.substvars

src_count="$(find src -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
[[ "$src_count" -gt 0 ]] || die "src is empty"
[[ -x src/catkin/bin/catkin_make_isolated ]] || die "src/catkin/bin/catkin_make_isolated is missing"

rm -f "$orig_tar" "$changes_file"
tar --sort=name --owner=0 --group=0 --numeric-owner \
  --exclude="${source_name}-${upstream_version}/debian" \
  -cJf "$orig_tar" \
  -C "$stage_dir" "${source_name}-${upstream_version}"

build_args=(-S "$include_orig")
if [[ "$sign" -eq 0 ]]; then
  build_args+=(-us -uc)
fi
dpkg-buildpackage "${build_args[@]}"

[[ -f "$changes_file" ]] || die "missing source changes: $changes_file"
echo "built: $changes_file"
sha256sum "$orig_tar" "$changes_file"

if [[ "$upload" -eq 1 ]]; then
  dput "$ppa_target" "$changes_file"
fi
