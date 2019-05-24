# We start with CentOS 7, because it is commonly used in
# production, and meets the glibc requirements of VFXPlatform 2018
# (2.17 or lower).

FROM centos:7

# Make GCC 6.3.1 the default compiler, as per VFXPlatform 2018

# We have to install scl as a separate yum command for some reason
# otherwise we get `scl not found` errors...
RUN yum install -y centos-release-scl && \
	yum install -y devtoolset-6 && \
#
#	Install CMake, SCons, and other miscellaneous build tools.
#	We install SCons via `pip install --egg` rather than by
#	`yum install` because this prevents a Cortex build failure
#	caused by SCons picking up the wrong Python version and being
#	unable to find its own modules.
#
	yum install -y epel-release && \
#
	yum install -y cmake3 && \
	ln -s /usr/bin/cmake3 /usr/bin/cmake && \
#
	yum install -y python2-pip.noarch && \
	pip install --egg scons && \
#
	yum install -y \
		patch \
		doxygen && \
#
#	Install boost dependencies (needed by boost::iostreams)
#
	yum install -y bzip2-devel && \
#
#	Install JPEG dependencies
#
	yum install -y nasm && \
#
#	Install PNG dependencies && \
#
	yum install -y zlib-devel && \
#
#	Install GLEW dependencies
#
	yum install -y \
		libX11-devel \
		mesa-libGL-devel \
		mesa-libGLU-devel \
		libXmu-devel \
		libXi-devel && \
#
#	Install OSL dependencies
#
	yum install -y \
		flex \
		bison && \
#
#	Install Qt dependencies
#
	yum install -y \
		xkeyboard-config.noarch \
		fontconfig-devel.x86_64
#
# Install packages needed to generate the
# Gaffer documentation.

RUN yum install -y \
		xorg-x11-server-Xvfb \
		mesa-dri-drivers.x86_64 \
		metacity \
		gnome-themes-standard
#
RUN pip install \
		sphinx==1.8 \
		sphinx_rtd_theme \
		recommonmark \
		docutils==0.12 && \
#
	yum install -y inkscape

# Copy over build script and set an entry point that
# will use the compiler we want.

COPY build.py ./

ENTRYPOINT [ "scl", "enable", "devtoolset-6", "--", "bash" ]
