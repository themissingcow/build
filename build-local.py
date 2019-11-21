#!/usr/bin/env python
##########################################################################
#
#  Copyright (c) 2018, Image Engine Design Inc. All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#      * Redistributions of source code must retain the above
#        copyright notice, this list of conditions and the following
#        disclaimer.
#
#      * Redistributions in binary form must reproduce the above
#        copyright notice, this list of conditions and the following
#        disclaimer in the documentation and/or other materials provided with
#        the distribution.
#
#      * Neither the name of John Haddon nor the names of
#        any other contributors to this software may be used to endorse or
#        promote products derived from this software without specific prior
#        written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
#  IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
#  THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
#  PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
#  CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
#  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
#  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
#  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
##########################################################################

import os
import sys
import distutils.util
import uuid
import json
import shutil
import argparse
import subprocess
import multiprocessing

parser = argparse.ArgumentParser()

parser.add_argument(
	"--build-env-version",
	dest = "buildEnvVersion",
	default = "1.0.0",
	help = "The container image tag to use for docker builds."
)

parser.add_argument(
	"--build-env-image",
	dest = "buildEnvImage",
	default = "gafferhq/build",
	help = "The container image to use for docker builds."
)

parser.add_argument(
	"--arnoldRoot",
	default = os.environ.get( "ARNOLD_ROOT", "" ),
	help = "The root of an installation of Arnold 5. "
	       "Note that if cross-compiling a Linux build "
	       "using Docker on a Mac, this must point to "
	       "a Linux build of Arnold."
)

parser.add_argument(
	"--delightRoot",
	default = os.environ.get( "DELIGHT", "" ),
	help = "The root of an installation of 3Delight 13. "
	       "Note that if cross-compiling a Linux build "
	       "using Docker on a Mac, this must point to "
	       "a Linux build of 3Delight."
)

parser.add_argument(
	"--source",
	default = os.getcwd(),
	help = "The root of the gaffer source tree"
)

parser.add_argument(
	"--buildDir",
	default = os.path.join( os.getcwd(), 'build' ),
	help = "The build directory, this should contain the Gaffer dependencies"
)

parser.add_argument(
	"--buildCacheDir",
	default = "",
	help = "A directory to use as the scons cache"
)

parser.add_argument(
	"--sconsCmd",
	default = "docs",
	help = "The scons command to call"
)

parser.add_argument(
	"--docker",
	type = distutils.util.strtobool,
	default = "linux" in sys.platform,
	help = "Performs the build using a Docker container. This provides a "
	       "known build platform so that builds are repeatable."
)

args = parser.parse_args()

# Check that the paths to the renderers are sane.

platform = "linux" if "linux" in sys.platform or args.docker else "osx"
libExtension = ".so" if platform == "linux" else ".dylib"

if args.arnoldRoot :
	arnoldLib = args.arnoldRoot + "/bin/libai" + libExtension
	if not os.path.exists( arnoldLib ) :
		parser.exit( 1, "{0} not found\n".format( arnoldLib ) )

if args.delightRoot :
	delightLib = args.delightRoot + "/lib/lib3delight" + libExtension
	if not os.path.exists( delightLib ) :
		parser.exit( 1, "{0} not found\n".format( delightLib ) )

# Build a little dictionary of variables we'll need over and over again
# in string formatting operations, and use it to figure out what
# package we will eventually be generating.

formatVariables = {
	"platform" : platform,
	"arnoldRoot" : args.arnoldRoot,
	"delight" : args.delightRoot,
	"buildDir" : args.buildDir,
	"buildCacheDir" : args.buildCacheDir,
	"source" : args.source
}

# Restart ourselves inside a Docker container so that we use a repeatable
# build environment.
if args.docker and not os.path.exists( "/.dockerenv" ) :

	image = "%s:%s" % ( args.buildEnvImage, args.buildEnvVersion )
	containerName = "gafferhq-build-{id}".format( id = uuid.uuid1() )

	containerEnv = []
	containerMounts = []

	containerMounts.append( "-v %s:/scripts:Z" % os.path.dirname( __file__ ) )
	containerMounts.append( "-v %s:/source:Z" % args.source )
	containerMounts.append( "-v %s:/build:Z" % args.buildDir )
	if args.buildCacheDir :
		containerMounts.append( "-v %s:/buildCache:Z" % args.buildCacheDir )

	if args.arnoldRoot :
		containerMounts.append( "-v %s:/arnold:ro,Z" % args.arnoldRoot )
		containerEnv.append( "ARNOLD_ROOT=/arnold" )

	if args.delightRoot :
		containerMounts.append( " -v %s:/delight:ro,Z" % args.delightRoot )
		containerEnv.append( "DELIGHT=/delight" )

	containerEnv = " ".join( containerEnv )
	containerMounts = " ".join( containerMounts )

	containerCommand = "env {env} bash -c '/scripts/build-local.py --sconsCmd={cmd} --buildDir=/build --buildCacheDir=/buildCache --source=/source'".format( env = containerEnv, cmd = args.sconsCmd, **formatVariables )

	dockerCommand = "docker run -it {mounts} --name {name} {image} {command}".format(
		source = args.source,
		buildDir = args.buildDir,
		mounts = containerMounts,
		name = containerName,
		image = image,
		command = containerCommand
	)
	sys.stderr.write( dockerCommand + "\n" )
	subprocess.check_call( dockerCommand, shell = True )

	sys.exit( 0 )

# Here we're actually doing the build, this will run either locally or inside
# the container bootstrapped above

if os.path.exists( "/.dockerenv" ) :

	# Start an X server so we can generate screenshots when the
	# documentation builds.
	os.system( "Xvfb :99 -screen 0 1280x1024x24 &" )
	os.environ["DISPLAY"] = ":99"
	os.system( "metacity&" )

os.chdir( args.source )

# Perform the build.

# We run SCons indirectly via `python` so that it uses our
# preferred python from the environment. SCons itself
# unfortunately hardcodes `/usr/bin/python`, which might not
# have the modules we need to build the docs.
buildCommand = "python `which scons` {cmd} ENV_VARS_TO_IMPORT=PATH DELIGHT_ROOT={delight} ARNOLD_ROOT={arnoldRoot} BUILD_DIR={buildDir} BUILD_CACHEDIR={buildCacheDir} OPTIONS='' -j {cpus}".format(
	cmd=args.sconsCmd,
	cpus=multiprocessing.cpu_count(),
	**formatVariables
)

sys.stderr.write( buildCommand + "\n" )
subprocess.check_call( buildCommand, shell=True )

