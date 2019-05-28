#!/usr/bin/env python
##########################################################################
#
#  Copyright (c) 2019, Cinesite VFX Ltd. All rights reserved.
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
import argparse
import subprocess

parser = argparse.ArgumentParser(

	description =
	    "Builds the gafferhq container for linux builds. \n"
	    "Incorporates a version-locking mechanism to allow stable builds that "
	    "include yum-installed packages.",

	epilog =
	    "The yum version locking mechanism works as follows:\n"
	    " 1. The source checkout contains a yum-versionlock formatted list of\n"
	    "    package versions.\n"
	    " 2. The Dockerfile copies this in at the beginning of a build. \n"
	    " 3. Any yum installs during the build will then respect these versions.\n"
	    " 4. At the end of the build, if requested, we update the file with the\n"
	    "    versions of any new (or optionally - all) packages.\n"
	    " 5. The updated version list can be committed to source control.\n\n"
	    " NOTE: pip installed packages should be locked by including explicit "
	    " version numbers in their install commands."
)

parser.add_argument(
	"--upload",
	action = 'store_true',
	help = "Pushes the build image to dockerhub. You must first have used "
	       "'docker login' to set your credentials"
)

parser.add_argument(
	"--tag",
	dest = "tag",
	default = "latest",
	help = "The tag to apply to the build docker image when building the 'build' project."
)

parser.add_argument(
	"--image",
	default = "gafferhq/build",
	help = "The dockerhub organisation and image name to use in the image tag."
)

parser.add_argument(
	"--no-cache",
	dest = "noCache",
	action = 'store_true',
	help = "Because docker caches layers based on the RUN command string it "
	       "will fail to include any changes to package version locks, etc... "
	       "Use this flag to ensure a clean build."
)

parser.add_argument(
	"--update-version-locks",
	dest = "updateVersions",
	action = 'store_true',
	help = "If set, will remove the package manager version locks prior to "
	       "building the docker image to allow updated packages to be retrieved."
)

parser.add_argument(
	"--new-only",
	dest = "newPackagesOnly",
	action = 'store_true',
	help = "If set along with --update-version-locks, only newly added packages "
	       "without an existing version lock will be updated in the lock list, "
	       "existing packages will keep their version."
)

parser.add_argument(
	"--version-lock-file",
	dest = "versionlockFile",
	default = "yum-versionlock.list",
	help = "The local file to use for the yum versionlock mechanism."
)

args = parser.parse_args()

# Rough order of operations:
#
#  1. Copy in versionlock list from source control or a blank one
#  2. Perform build
#  3. Copy out versionlock list if requested
#  4. Upload final image to dockerhub

imageTag = "{image}:{tag}".format( image = args.image, tag = args.tag )

# 1. Versionlock management

# As we can't have conditionals in the Dockerfile, we always copy in our
# lock file, so to 'unlock' we simply empty it out so it has no effect.
if args.updateVersions and not args.newPackagesOnly :
	sys.stderr.write( "Unlocking all package versions...\n" )
	if os.path.exists( args.versionlockFile ) :
		os.remove( args.versionlockFile )
	open( args.versionlockFile, 'w' ).close()

# 2. Build the image

buildCommand = "docker build {cache} -t {tag} .".format(
	cache = "--no-cache" if ( args.noCache or args.updateVersions ) else "",
	tag = imageTag
)
sys.stderr.write( buildCommand + "\n" )
subprocess.check_call( buildCommand, shell = True )

# 3. Extract updated versionlock file

if args.updateVersions :
	# Extract the updated version lock files from the container
	extractCommand = " && ".join((
		"docker create --name {name} {tag}",
		"docker cp {name}:{versionlockSrc} {versionlockDest}",
		"docker rm {name}",
		"sort {versionlockDest} -o {versionlockDest}"
	)).format(
		name = "gafferhq-build-{id}".format( id = uuid.uuid1() ),
		tag = imageTag,
		versionlockSrc = "/etc/yum/pluginconf.d/versionlock.list",
		versionlockDest = args.versionlockFile
	)
	sys.stderr.write( extractCommand + "\n" )
	subprocess.check_call( extractCommand, shell = True )

# 4. Upload

if args.upload :
	pushCommand = "docker push %s" % imageTag
	sys.stderr.write( pushCommand + "\n" )
	subprocess.check_call( pushCommand, shell = True )
