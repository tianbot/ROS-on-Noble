# Source Maintenance

This repository treats `ppa:tianbot/ros2go` as the published archive and keeps
source maintenance explicit. Do not edit packages directly in the PPA.

## Baseline

The current baseline is copied from:

```shell
ppa:ros-for-jammy/noble
```

The target archive is:

```shell
ppa:tianbot/ros2go
```

Copied packages keep their upstream versions. Tianbot-maintained changes should
use a version suffix such as `+tianbot1`, then `+tianbot2`.

## Copy The Baseline

Preview:

```shell
python scripts/copy_ppa.py --dry-run
```

Copy published source packages plus existing binaries:

```shell
python scripts/copy_ppa.py
```

The copy tool skips packages already present in the target PPA in either
`Pending` or `Published` state.

## Import One Source Package

Use this when a package needs a Tianbot patch:

```shell
python scripts/import_source.py ros-noetic-rosbag
```

The source is extracted under:

```text
sources/<source-package>/<version>/tree
```

The extracted tree is initialized as a Git repository and tagged with the import
version.

## Audit External Source Risk

The copied PPA source files are the rebuild baseline. Treat ad hoc upstream
URLs, rosdistro forks, and archive tarballs as inputs that must be mirrored or
replaced before they become long-term maintenance dependencies.

Run the external-source audit after changing build instructions, rosinstall
inputs, or source-import tooling:

```shell
python scripts/audit_external_sources.py
```

Current expected risk areas:

- GitHub archive tarballs in `noetic-desktop.rosinstall`.
- Personal fork tarballs and branch archive tarballs that are less stable than
  ROS release repositories.
- The vendored rosdistro snapshot under `vendor/rosdistro` must be refreshed
  deliberately when Noble rosdep mappings change.
- `vendor/rosdistro/index-noetic.yaml` intentionally exposes only Noetic to
  `rosdep update`; do not point local builds at the full rosdistro index unless
  every active distribution referenced by that index is vendored too.
- The generated rosdep source list omits the legacy Fuerte `gbpdistro` entry
  because Noetic builds do not need it and current `rosdep update` tries to
  fetch stale platform data for it.
For patched packages, prefer importing the Launchpad source package and keeping
the `.dsc`, `.orig.tar.*`, and Debian delta together. Do not make a Tianbot
source upload depend on fetching code from Gitee, GitHub branch archives, or
other mutable external URLs during the package build.

## Mirror Bundle Tarballs

The bundle build still uses `noetic-desktop.rosinstall`, which points at many
GitHub archive tarballs. Mirror those tarballs before relying on CI for
long-term rebuilds:

```shell
python scripts/mirror_rosinstall_sources.py \
  --mirror-dir mirror/rosinstall-sources \
  --base-url https://github.com/tianbot/ROS-on-Noble/releases/download/source-cache
```

The command downloads each tarball, writes
`mirror/rosinstall-sources/manifest.json`, and generates
`noetic-desktop.mirrored.rosinstall`. Keep the generated mirror directory in
Tianbot-controlled storage, not in Git.

The current public mirror is the GitHub release
`https://github.com/tianbot/ROS-on-Noble/releases/tag/source-cache`. The
GitHub repository variable `ROS_SOURCE_MIRROR_BASE` should point at
`https://github.com/tianbot/ROS-on-Noble/releases/download/source-cache`. CI
rewrites `noetic-desktop.rosinstall` to that mirror base before `vcs import`.
The committed manifest `vendor/rosinstall-sources.manifest.json` records the
original URL, mirror URL, cache filename, and SHA-256 for each mirrored tarball.
Mirror asset filenames are derived from the rosinstall `local-name` plus the
original tarball basename, for example
`actionlib-actionlib-1.14.0-1.tar.gz`.

For a rewrite-only preview against an already-published mirror:

```shell
python scripts/mirror_rosinstall_sources.py \
  --rewrite-only \
  --base-url "$ROS_SOURCE_MIRROR_BASE"
```

## Build A PPA Source Upload

Launchpad PPAs do not accept locally built `.deb` files. Upload a source
package and let Launchpad build the binary package.

For this bundle package, the source upload vendors the imported ROS workspace
inside the upstream `.orig.tar.xz`. This keeps the Launchpad build offline with
respect to ROS source fetching while preserving the existing
`debian/rules` build path.

Fast path on a builder that already has a verified imported workspace:

```shell
scripts/package_ppa_source.sh \
  --no-sign \
  --use-existing-src /tmp/ws/ROS-on-Noble/src
```

Fresh source import from the mirrored tarball cache:

```shell
scripts/package_ppa_source.sh --no-sign
```

The first upload of a new upstream version must include the full orig tarball:

```shell
scripts/package_ppa_source.sh \
  --upload \
  --include-orig -sa \
  --use-existing-src /tmp/ws/ROS-on-Noble/src
```

For later Debian revisions that reuse the already accepted orig tarball:

```shell
scripts/package_ppa_source.sh \
  --upload \
  --include-orig -sd \
  --use-existing-src /tmp/ws/ROS-on-Noble/src
```

The upload host must have a GPG secret key associated with an account that can
upload to `ppa:tianbot/ros2go`; unsigned source changes are useful only for
validation.

## Patch And Upload

Inside the extracted source tree:

```shell
dch -v '<upstream-version>+tianbot1' 'Describe the Tianbot change.'
debuild -S -sa
dput ppa:tianbot/ros2go ../*.changes
```

For follow-up patches, increment the Tianbot suffix.

## Policy

- Copy unchanged packages from the baseline PPA.
- Patch only the packages that need Tianbot changes.
- Keep every patched package in Git with import tags and changelog entries.
- Prefer source uploads to the PPA; do not rely on local binary-only `.deb`
  files as the source of truth.
- Keep imported source tarballs mirrored. A rebuild should be possible from
  Launchpad source files plus Tianbot Git history, without live access to Gitee
  or personal fork archive URLs.
- Keep `ppa:tianbot/ros2go` user-facing. Use a separate testing PPA if a change
  needs soak time before publishing.
