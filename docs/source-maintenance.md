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
- Keep `ppa:tianbot/ros2go` user-facing. Use a separate testing PPA if a change
  needs soak time before publishing.
