# Build ROS Noetic on Ubuntu 24.04 Noble

This repository builds a bundled ROS Noetic desktop tree for Ubuntu 24.04
Noble. The generated Debian package installs ROS under `/opt/ros/noetic`.

This is a practical bundle package for Noble. The generated package keeps the
traditional `ros-noetic-desktop-full` package name.

## Scope

- Ubuntu 24.04 Noble
- amd64 builds first
- ROS Noetic desktop sources
- Classic Gazebo 11 from the Noble ROS PPA
- Bundled `ros-noetic-desktop-full` package with 307 discoverable ROS
  packages, counted with `catkin_pkg.find_packages("src")` after source import.

The imported source tree contains 324 `package.xml` files in total. The bundle
count above excludes package manifests embedded in upstream test fixtures, such
as `catkin/test/mock_resources`, because catkin does not treat those as build
workspace packages.

## Add the Noble ROS PPA

```shell
sudo add-apt-repository ppa:tianbot/ros2go
sudo apt update
```

## Install build tools

```shell
sudo apt install -y build-essential cmake curl debhelper devscripts equivs git python3-rosdep vcstool
```

## Prepare rosdep

The upstream Noetic rosdep data does not fully target Noble. Use the rosdistro
snapshot vendored in this repository. It is based on the Noble mappings from
the original rosdistro fork, but local builds no longer depend on Gitee being
available.

```shell
sudo python3 scripts/install_rosdep_snapshot.py
export ROSDISTRO_INDEX_URL="file://$(pwd)/vendor/rosdistro/index-noetic.yaml"
rosdep update
```

To persist the setting:

```shell
echo "export ROSDISTRO_INDEX_URL=file://$(pwd)/vendor/rosdistro/index-noetic.yaml" >> ~/.bashrc
```

## Fetch ROS sources

```shell
mkdir -p src
vcs import --input noetic-desktop.rosinstall ./src
```

For long-term rebuilds, mirror the tarballs first and import from the generated
mirror input:

```shell
python scripts/mirror_rosinstall_sources.py --base-url "$ROS_SOURCE_MIRROR_BASE"
vcs import --input noetic-desktop.mirrored.rosinstall ./src
```

## Install build dependencies

Some rosdep keys still do not resolve cleanly on Noble:

- `libgazebo11-dev`: Noble uses `libgazebo-dev`
- `gazebo11`: Noble uses `gazebo`
- `hddtemp`: removed from Ubuntu repositories

The PPA provides the Gazebo packages needed for the build, so skip the stale
rosdep keys:

```shell
rosdep install --from-paths ./src \
  --ignore-packages-from-source \
  --rosdistro noetic \
  -y \
  --skip-keys='libgazebo11-dev hddtemp gazebo11'
```

## Build and install locally

```shell
sudo mkdir -p /opt/ros/noetic
sudo chmod 777 /opt/ros/noetic

./src/catkin/bin/catkin_make_isolated \
  --install-space /opt/ros/noetic \
  --install \
  -DCMAKE_BUILD_TYPE=Release \
  -DCATKIN_ENABLE_TESTING=OFF \
  -DPYTHON_EXECUTABLE=/usr/bin/python3
```

## Build the Debian package

```shell
dpkg-buildpackage -b --root-command="sudo" -uc -us -j4
```

The output package is created in the parent directory.

## Maintain Source Packages

`ppa:tianbot/ros2go` is the published archive. Use the source maintenance
workflow in [`docs/source-maintenance.md`](docs/source-maintenance.md) to copy
the baseline PPA, import individual source packages, apply Tianbot patches, and
upload source changes.
