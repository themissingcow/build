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
	"--project",
	default = "gaffer",
	choices = [ "gaffer", "dependencies" ],
	help = "The project to build."
)

parser.add_argument(
	"--arnoldRoot",
	default = os.environ["ARNOLD_ROOT"],
	help = "The root of an installation of Arnold 5. "
	       "Note that if cross-compiling a Linux build "
	       "using Docker on a Mac, this must point to "
	       "a Linux build of Arnold."
)

parser.add_argument(
	"--delightRoot",
	default = os.environ["DELIGHT"],
	help = "The root of an installation of 3Delight 13. "
	       "Note that if cross-compiling a Linux build "
	       "using Docker on a Mac, this must point to "
	       "a Linux build of 3Delight."
)

parser.add_argument(
	"--version",
	help = "The version to build. Can either be a tag or SHA1 commit hash."
)

parser.add_argument(
	"--upload",
	type = distutils.util.strtobool,
	default = "0",
	help = "Uploads the resulting package to the GitHub release page. You must "
	       "have manually created the release and release notes already."
)

parser.add_argument(
	"--docker",
	type = distutils.util.strtobool,
	default = "linux" in sys.platform,
	help = "Performs the build using a Docker container. This provides a "
	       "known build platform so that builds are repeatable."
)

parser.add_argument(
	"--interactive",
	type = distutils.util.strtobool,
	default = False,
	help = "When using docker, starts an interactive shell rather than "
		   "performing the build. This is useful for debugging."
)

args = parser.parse_args()

if args.interactive :
	if not args.docker :
		parser.exit( 1, "--interactive requires --docker\n" )
	if args.version or args.upload :
		parser.exit( 1, "--interactive can not be used with other flags\n" )
else :
	if not args.version :
		parser.exit( "--version argument is required")

# Check that our environment contains everything we need to do a build.

for envVar in ( "GITHUB_RELEASE_TOKEN", ) :
	if envVar not in os.environ	:
		parser.exit( 1,  "{0} environment variable not set".format( envVar ) )

# Check that the paths to the renderers are sane.

libExtension = ".so" if "linux" in sys.platform or args.docker else ".dylib"

arnoldLib = args.arnoldRoot + "/bin/libai" + libExtension
if not os.path.exists( arnoldLib ) :
	parser.exit( 1, "{0} not found\n".format( arnoldLib ) )

delightLib = args.delightRoot + "/lib/lib3delight" + libExtension
if not os.path.exists( delightLib ) :
	parser.exit( 1, "{0} not found\n".format( delightLib ) )

# Build a little dictionary of variables we'll need over and over again
# in string formatting operations, and use it to figure out what
# package we will eventually be generating.

formatVariables = {
	"project" : args.project,
	"version" : args.version,
	"upload" : args.upload,
	"platform" : "osx" if sys.platform == "darwin" else "linux",
	"arnoldRoot" : args.arnoldRoot,
	"delight" : args.delightRoot,
	"releaseToken" : os.environ["GITHUB_RELEASE_TOKEN"],
}

if args.project == "gaffer" :
	formatVariables["uploadFile"] = "{project}-{version}-{platform}.tar.gz".format( **formatVariables )
else :
	formatVariables["uploadFile"] = "gafferDependencies-{version}-{platform}.tar.gz".format( **formatVariables )

# Restart ourselves inside a Docker container so that we use a repeatable
# build environment.

if args.docker and not os.path.exists( "/.dockerenv" ) :

	imageCommand = "docker build --target {project}-builder -t gafferhq-build .".format( **formatVariables )
	sys.stderr.write( imageCommand + "\n" )
	subprocess.check_call( imageCommand, shell = True )

	containerMounts = "-v {arnoldRoot}:/arnold:ro,Z -v {delight}:/delight:ro,Z".format( **formatVariables )
	containerEnv = "GITHUB_RELEASE_TOKEN={releaseToken} ARNOLD_ROOT=/arnold DELIGHT=/delight".format( **formatVariables )
	containerName = "gafferhq-build-{id}".format( id = uuid.uuid1() )

	if args.interactive :
		containerBashCommand = "{env} bash".format( env = containerEnv )
	else :
		containerBashCommand = "{env} ./build.py --project {project} --version {version} --upload {upload}".format( env = containerEnv, **formatVariables )

	containerCommand = "docker run {mounts} --name {name} -i -t gafferhq-build -c '{command}'".format(
		name = containerName,
		mounts = containerMounts,
		command = containerBashCommand
	)

	sys.stderr.write( containerCommand + "\n" )
	subprocess.check_call( containerCommand, shell = True )

	if not args.interactive :
		# Copy out the generated package.
		copyCommand = "docker cp {container}:{uploadFile} ./".format(
			container = containerName,
			**formatVariables
		)
		sys.stderr.write( copyCommand + "\n" )
		subprocess.check_call( copyCommand, shell = True )

	sys.exit( 0 )

if os.path.exists( "/.dockerenv" ) and args.project == "gaffer" :

	# Start an X server so we can generate screenshots when the
	# documentation builds.
	os.system( "Xvfb :99 -screen 0 1280x1024x24 &" )
	os.environ["DISPLAY"] = ":99"

# Download source code

sourceURL = "https://github.com/GafferHQ/{project}/archive/{version}.tar.gz".format( **formatVariables )
sys.stderr.write( "Downloading source \"%s\"\n" % sourceURL )

sourceDirName = "{project}-{version}-source".format( **formatVariables )
tarFileName = "{0}.tar.gz".format( sourceDirName )
downloadCommand = "curl -L {0} > {1}".format( sourceURL, tarFileName )
sys.stderr.write( downloadCommand + "\n" )
subprocess.check_call( downloadCommand, shell = True )

sys.stderr.write( "Decompressing source to \"%s\"\n" % sourceDirName )

shutil.rmtree( sourceDirName, ignore_errors = True )
os.makedirs( sourceDirName )
subprocess.check_call( "tar xf %s -C %s --strip-components=1" % ( tarFileName, sourceDirName ), shell = True )
os.chdir( sourceDirName )

# Download precompiled dependencies. We do this using the
# same script that is used to download the dependencies for
# testing on Travis, so that release builds are always made
# against the same dependencies we have tested against.

if args.project == "gaffer" :
	subprocess.check_call( "./config/travis/installDependencies.sh", shell = True )

# Perform the build.

if args.project == "gaffer" :

	# We run SCons indirectly via `python` so that it uses our
	# preferred python from the environment. SCons itself
	# unfortunately hardcodes `/usr/bin/python`, which might not
	# have the modules we need to build the docs.
	buildCommand = "python `which scons` package PACKAGE_FILE={uploadFile} ENV_VARS_TO_IMPORT=PATH RMAN_ROOT={delight} ARNOLD_ROOT={arnoldRoot} OPTIONS='' -j {cpus}".format(
		cpus=multiprocessing.cpu_count(), **formatVariables
	)

else :

	buildCommand = "env RMAN_ROOT={delight} ARNOLD_ROOT={arnoldRoot} BUILD_DIR=/gafferDependenciesBuild ./build/buildAll.sh ".format( **formatVariables )

sys.stderr.write( buildCommand + "\n" )
subprocess.check_call( buildCommand, shell=True )

# Upload the build

if args.upload :

	auth = '-H "Authorization: token {releaseToken}"'.format( **formatVariables )
	release = subprocess.check_output(
		"curl -s {auth} https://api.github.com/repos/GafferHQ/{project}/releases/tags/{version}".format(
			auth = auth, **formatVariables
		),
		shell = True
	)
	release = json.loads( release )

	uploadCommand = (
		'curl {auth}'
		' -H "Content-Type: application/zip"'
		' --data-binary @{uploadFile} "{uploadURL}"'
		' -o /tmp/curlResult.txt' # Must specify output file in order to get progress output
	).format(
		auth = auth,
		uploadURL = "https://uploads.github.com/repos/GafferHQ/{project}/releases/{id}/assets?name={uploadName}".format(
			id = release["id"],
			uploadName = os.path.basename( formatVariables["uploadFile"] ),
			**formatVariables
		),
		**formatVariables
	)

	sys.stderr.write( "Uploading package\n" )
	sys.stderr.write( uploadCommand + "\n" )

	subprocess.check_call( uploadCommand, shell = True )
