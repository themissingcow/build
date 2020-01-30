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
	default = "1.1.0",
	help = "The container image tag to use for docker builds."
)

parser.add_argument(
	"--build-env-image",
	dest = "buildEnvImage",
	default = "gafferhq/build",
	help = "The container image to use for docker builds."
)

parser.add_argument(
	"--organisation",
	default = "GafferHQ",
	help = "The GitHub organisation containing the project to build."
)

parser.add_argument(
	"--project",
	default = "gaffer",
	choices = [ "gaffer", "dependencies" ],
	help = "The project to build."
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
	"--renderManRoot",
	default = os.environ.get( "RMANTREE", "" ),
	help = "The root of an installation of RenderMan 22.6 or later. "
	       "Note that if cross-compiling a Linux build "
	       "using Docker on a Mac, this must point to "
	       "a Linux build of RenderMan."
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

if args.upload :

	if "GITHUB_RELEASE_TOKEN" not in os.environ	:
		parser.exit( 1,  "GITHUB_RELEASE_TOKEN environment variable not set\n" )

	if not args.arnoldRoot :
		parser.exit( 1,  "Release builds must include Arnold (set $ARNOLD_ROOT or --arnoldRoot)\n" )
	if not args.delightRoot :
		parser.exit( 1,  "Release builds must include 3Delight (set $DELIGHT_ROOT or --delightRoot)\n" )


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

if args.renderManRoot :
	renderManLib = args.renderManRoot + "/lib/libprman" + libExtension
	if not os.path.exists( renderManLib ) :
		parser.exit( 1, "{0} not found\n".format( renderManLib ) )

# Build a little dictionary of variables we'll need over and over again
# in string formatting operations, and use it to figure out what
# package we will eventually be generating.

formatVariables = {
	"organisation" : args.organisation,
	"project" : args.project,
	"version" : args.version,
	"upload" : args.upload,
	"platform" : platform,
	"arnoldRoot" : args.arnoldRoot,
	"delight" : args.delightRoot,
	"renderManRoot" : args.renderManRoot,
	"releaseToken" : "",
	"auth" : "",
}

githubToken = os.environ.get( "GITHUB_RELEASE_TOKEN", "" )
if githubToken :
	formatVariables[ "releaseToken" ] = githubToken
	formatVariables[ "auth" ] = '-H "Authorization: token %s"' % githubToken

if args.project == "gaffer" :
	formatVariables["uploadFile"] = "{project}-{version}-{platform}.tar.gz".format( **formatVariables )
else :
	formatVariables["uploadFile"] = "gafferDependencies-{version}-{platform}.tar.gz".format( **formatVariables )

# If we're going to be doing an upload, then check that the release exists. Better
# to find out now than at the end of a lengthy build.

def releaseId() :

	release = subprocess.check_output(
		"curl -s {auth} https://api.github.com/repos/{organisation}/{project}/releases/tags/{version}".format(
			**formatVariables
		),
		shell = True
	)
	release = json.loads( release )
	return release.get( "id" )

if args.upload and releaseId() is None :
	parser.exit( 1, "Release {version} not found\n".format( **formatVariables ) )

# Restart ourselves inside a Docker container so that we use a repeatable
# build environment.
if args.docker and not os.path.exists( "/.dockerenv" ) :

	image = "%s:%s" % ( args.buildEnvImage, args.buildEnvVersion )
	containerName = "gafferhq-build-{id}".format( id = uuid.uuid1() )

	# We don't keep build.py in the images (otherwise we'd have to maintain
	# backwards compatibility when changing this script), so copy it in

	containerPrepCommand = " && ".join( (
		"docker create --name {name} {image}",
		"docker cp build.py {name}:/build.py",
		# This saves our changes to that container, so we can pick it up
		# in run later. We can't use exec as when you 'start' the image
		# it immediately exits as there is nothing to do. Docker is process
		# centric not 'machine' centric. You can either add in nasty sleep
		# commands into the image, but this seems to be the more 'docker'
		# way to do it.
		"docker commit {name} {image}-run",
		"docker rm {name}"
	) ).format(
		name = containerName,
		image = image
	)
	sys.stderr.write( containerPrepCommand + "\n" )
	subprocess.check_call( containerPrepCommand, shell = True )

	containerEnv = []
	if githubToken :
		containerEnv.append( "GITHUB_RELEASE_TOKEN=%s" % githubToken )

	containerMounts = []
	if args.arnoldRoot :
		containerMounts.append( "-v %s:/arnold:ro,Z" % args.arnoldRoot )
		containerEnv.append( "ARNOLD_ROOT=/arnold" )
	if args.delightRoot :
		containerMounts.append( " -v %s:/delight:ro,Z" % args.delightRoot )
		containerEnv.append( "DELIGHT=/delight" )
	if args.renderManRoot :
		containerMounts.append( "-v %s:/renderMan:ro,Z" % args.renderManRoot )
		containerEnv.append( "RMANTREE=/renderMan" )

	containerEnv = " ".join( containerEnv )
	containerMounts = " ".join( containerMounts )

	if args.interactive :
		containerCommand = "env {env} bash".format( env = containerEnv )
	else :
		containerCommand = "env {env} bash -c '/build.py --project {project} --version {version} --upload {upload}'".format( env = containerEnv, **formatVariables )

	dockerCommand = "docker run -it {mounts} --name {name} {image}-run {command}".format(
		mounts = containerMounts,
		name = containerName,
		image = image,
		command = containerCommand
	)
	sys.stderr.write( dockerCommand + "\n" )
	subprocess.check_call( dockerCommand, shell = True )

	if not args.interactive :
		# Copy out the generated package.
		copyCommand = "docker cp {container}:/{project}-{version}-source/{uploadFile} ./".format(
			container = containerName,
			**formatVariables
		)
		sys.stderr.write( copyCommand + "\n" )
		subprocess.check_call( copyCommand, shell = True )

	sys.exit( 0 )

# Here we're actually doing the build, this will run either locally or inside
# the container bootstrapped above

if os.path.exists( "/.dockerenv" ) and args.project == "gaffer" :

	# Start an X server so we can generate screenshots when the
	# documentation builds.
	os.system( "Xvfb :99 -screen 0 1280x1024x24 &" )
	os.environ["DISPLAY"] = ":99"
	os.system( "metacity&" )

# Download source code

sourceURL = "https://github.com/{organisation}/{project}/archive/{version}.tar.gz".format( **formatVariables )
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
	# The scripts moved in #3242
	depsInstallScript = "./config/installDependencies.sh"
	if not os.path.exists( os.path.join( os.getcwd(), depsInstallScript ) ) :
		depsInstallScript = "./config/travis/installDependencies.sh"
	subprocess.check_call( depsInstallScript, shell = True )

# Perform the build.

if args.project == "gaffer" :

	# We run SCons indirectly via `python` so that it uses our
	# preferred python from the environment. SCons itself
	# unfortunately hardcodes `/usr/bin/python`, which might not
	# have the modules we need to build the docs.
	buildCommand = "python `which scons` package PACKAGE_FILE={uploadFile} ENV_VARS_TO_IMPORT=PATH DELIGHT_ROOT={delight} ARNOLD_ROOT={arnoldRoot} RENDERMAN_ROOT={renderManRoot} OPTIONS='' -j {cpus}".format(
		cpus=multiprocessing.cpu_count(), **formatVariables
	)

else :

	buildCommand = "env RMAN_ROOT={delight} ARNOLD_ROOT={arnoldRoot} BUILD_DIR={cwd}/gafferDependenciesBuild ./build/buildAll.sh ".format(
		cwd = os.getcwd(),
		**formatVariables
	)

sys.stderr.write( buildCommand + "\n" )
subprocess.check_call( buildCommand, shell=True )

# Upload the build

if args.upload :

	uploadCommand = (
		'curl {auth}'
		' -H "Content-Type: application/zip"'
		' --data-binary @{uploadFile} "{uploadURL}"'
		' -o /tmp/curlResult.txt' # Must specify output file in order to get progress output
	).format(
		uploadURL = "https://uploads.github.com/repos/{organisation}/{project}/releases/{id}/assets?name={uploadName}".format(
			id = releaseId(),
			uploadName = os.path.basename( formatVariables["uploadFile"] ),
			**formatVariables
		),
		**formatVariables
	)

	sys.stderr.write( "Uploading package\n" )
	sys.stderr.write( uploadCommand + "\n" )

	subprocess.check_call( uploadCommand, shell = True )
