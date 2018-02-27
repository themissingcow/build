# We start with an ancient OS, so our builds are very
# permissive in terms of their glibc requirements
# when deployed elsewhere. First we define an image
# with the minimum requirements to build the
# GafferHQ/dependencies project.

FROM centos:6 as dependencies-builder

# Make GCC 6.3.1 the default compiler, as per VFXPlatform 2018

RUN yum install -y centos-release-scl
RUN yum install -y devtoolset-6

# Install CMake, SCons, and other miscellaneous build tools.

RUN yum install -y epel-release
RUN yum install -y cmake3
RUN ln -s /usr/bin/cmake3 /usr/bin/cmake

RUN yum install -y scons
RUN yum install -y patch
RUN yum install -y doxygen

# Install boost dependencies (needed by boost::iostreams)

RUN yum install -y bzip2-devel

# Install JPEG dependencies

RUN yum install -y nasm

# Install PNG dependencies

RUN yum install -y zlib-devel

# Install GLEW dependencies

RUN yum install -y libX11-devel
RUN yum install -y mesa-libGL-devel
RUN yum install -y mesa-libGLU-devel
RUN yum install -y libXmu-devel
RUN yum install -y libXi-devel

# Install OSL dependencies

RUN yum install -y flex
RUN yum install -y bison

# Install Qt dependencies

RUN yum install -y xkeyboard-config.noarch
RUN yum install -y fontconfig-devel.x86_64

# Install what we need to run our build script.

RUN yum install -y python-argparse

# Copy over build script and set an entry point that
# will use the compiler we want.

COPY build.py ./

ENTRYPOINT [ "scl", "enable", "devtoolset-6", "--", "bash" ]

# Now we define a second image, derived from the
# one above. This adds on the extra stuff needed
# to build Gaffer itself.

FROM dependencies-builder as gaffer-builder

# Install packages needed to generate the
# Gaffer documentation. Note that we are
# limited to Sphinx 1.4 because recommonmark
# is incompatible with later versions.

RUN yum install -y xorg-x11-server-Xvfb
RUN yum install -y python27-python-pip.noarch
RUN scl enable python27 -- bash -c 'pip install sphinx==1.4 sphinx_rtd_theme recommonmark'

RUN yum install -y inkscape

# Make sure everything runs in a bash shell with the
# right dev toolset.

ENTRYPOINT [ "scl", "enable", "devtoolset-6", "python27", "--", "bash" ]
