Overview
--------

This project provides a consistent build environment used for all releases
of GafferHQ/gaffer and GafferHQ/dependencies. It is not necessary to use this
environment to make your own builds, but it may be useful as a reference.

Prerequisites
-------------

- ARNOLD_ROOT environment variable pointing to installation of Arnold 5
- DELIGHT environment variable pointing to installation of 3delight 13
- Docker 17.05 or later

Usage
-----

Build and upload a gaffer release :

`./build.py --version 0.45.0.0 --upload 1`

Build and upload a dependencies release :

`./build.py --project dependencies --version 0.45.0.0 --upload 1`

Make a Linux release using Docker on a Mac :

`./build.py --docker 1 --arnoldRoot /path/to/linux/arnoldRoot --delightRoot /path/to/linux/delightRoot --version 0.45.0.0 --upload 1`

Steps remaining to be automated
-------------------------------

- Update https://github.com/GafferHQ/documentation to include
  the latest docs.

Docker Cheatsheet
-----------------

Remove stopped containers :

`docker ps -aq --no-trunc | xargs docker rm`

Remove old images :

`docker images -q --filter dangling=true | xargs docker rmi`

Building the build environment
------------------------------

Gaffer and Dependency builds are made using pre-published docker images. These
environments are built from the Dockerfile in this repository. The `build.py`
script also aids the build/publish of these images. For example:

 `./build.py --project build --tag-as 1.1.0 --upload 1`

In order to produce this image, we make heavy use of `yum` to install the
packages required to build Gaffer and it's dependencies. As we don't manually
specify every version of every package we risk a non-deterministic build
environment. To get around this, we make use of `yum versionlock`. The
`yum-versionlock.list` file in the repository is copied into the base centos
image such that when `yum` runs, it will repeatable install the expected
versions. In order to help manage this, the `build.py` script has a few options
to aid updating of the lock list when new packages are added of updated required.

 - `--update-version-locks [0|1]` When set (defaults to `0`), this will ignore
   all version locks and update `yum-versionlock.list` to the 'current' version
   of all packages installed during docker's build. The revised file can then
   be commit, tagged and a new docker image pushed to docker hub.

 - `--new-only [0|1]` When set (defaults to `0`) the existing version lock list
   will not be cleared. This allows the versions to be locked for any new
   packages installed by changes to the `Dockerfile` without affecting the
   versions of existing packages.

 - `--upload [0|1]` Will push the built image to a docker hub tag.

### Cheat sheet

Added a new package to the image, installed with yum in the Dockerfile:

`./build.py --project build --update-version-locks 1 --new-only 1 --tag-as x.x.x`

Update all packages to latest:

`./build.py --project build --update-version-locks 1 --tag-as x.x.x`

### A note on Docker's caching mechanism

Docker caches layers based on the `RUN` command string. As such, it does not
known when the version lock file changes. the `--update-version-locks` command
will always run with `--no-cache` set, but if you've just pulled some updates
from upstream, and are re-building on your machine, you may find docker will
be using an out-of-date cache of one or more of the layers.

As such, its recommended to use `--no-cache 1` whenever performing release
builds.

