# We start with CentOS 7, because it is commonly used in
# production, and meets the glibc requirements of VFXPlatform 2018
# (2.17 or lower).

FROM centos:7.6.1810

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
	pip install --egg scons==3.0.5 && \
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
		sphinx==1.8.0 \
		sphinx_rtd_theme==0.4.3 \
		recommonmark==0.4.0 \
		docutils==0.12 && \
#
	yum install -y inkscape

# Copy over build script and set an entry point that
# will use the compiler we want.

COPY build.py ./

# Make GCC 6.3.1 the default compiler, as per VFXPlatform 2018
#
# We can't use ENTRYPOINT as it's not allowed on Azure. The ENV/BASH_ENV vars
# are sourced whenever a non-interactive sh/bash session is started.
# PROMPT_COMMAND is evaluated before a prompt is displayed in interactive
# sessions. Using all of these ensures that our scl_enable script
# is always run, regardless of which shell is being used. The scl_enable script
# simply unsets these (as its work will be done) and sources the appropriate
# scl environment. Thanks to:
# https://austindewey.com/2019/03/26/enabling-software-collections-binaries-on-a-docker-image/

RUN printf "unset BASH_ENV PROMPT_COMMAND ENV\nsource scl_source enable devtoolset-6\n" > /usr/bin/scl_enable

ENV BASH_ENV="/usr/bin/scl_enable" \
	ENV="/usr/bin/scl_enable" \
	PROMPT_COMMAND=". /usr/bin/scl_enable"

