#!/usr/bin/env python
"""
Everything needed to publish Python modules to a DevPi server.

Recommended reading: http://doc.devpi.net/latest/quickstart-releaseprocess.html
"""
import os
import sys
import urllib.parse

from glob import glob

import drone
import subprocess

# devpi uses a 'clientdir' arg to determine where to store state. We make
# this overridable below to facilitate the integration test process.
DEFAULT_CLIENTDIR = '/tmp/devpi-clientdir'


def die_on_error(f):
    """
    Since this plugin wraps the devpi client's CLI, we do a lot of the same
    error handling. We don't capture stdout/stderr, so they get emitted.
    This decorator just finishes the job and kills the build (by exiting).
    """
    def wrapped(*args, **kwargs):
        result = f(*args, **kwargs)
        if result.returncode == 1:
            sys.exit(1)
    return wrapped


@die_on_error
def select_server(server, clientdir=DEFAULT_CLIENTDIR):
    """
    Before the devpi CLI can do much of anything, it has to be pointed at the
    root of a devpi server.

    :param str server: Absolute URI to the root of a devpi server (not an
        index within the devpi server).
    :param str clientdir: Path to a directory for the devpi CLI to store state.
    :rtype: subprocess.CompletedProcess
    """
    return subprocess.run(['devpi', 'use', '--clientdir', clientdir, server])


@die_on_error
def login(username, password, clientdir=DEFAULT_CLIENTDIR):
    """
    Uploading packages to a devpi server usually requires an authenticated
    account with write permissions.

    :param str username: The devpi username we'll be uploading as.
    :param str password: The devpi user's password.
    :param str clientdir: Path to a directory for the devpi CLI to store state.
    :rtype: subprocess.CompletedProcess
    """
    return subprocess.run([
        'devpi', 'login', '--clientdir', clientdir,
        username, '--password', password])


@die_on_error
def select_index(index, clientdir=DEFAULT_CLIENTDIR):
    """
    Before we can upload a package to an index, we must select it since there's
    no one-shot select + upload command.

    :param str index: The index to upload to. For example, ``root/devpitest``.
        This gets appended to whatever ``server`` value gets passed into
        :py:func:`select_server`.
    :param str clientdir: Path to a directory for the devpi CLI to store state.
    :rtype: subprocess.CompletedProcess
    """
    return subprocess.run(['devpi', 'use', '--clientdir', clientdir, index])


@die_on_error
def create_index(index, clientdir=DEFAULT_CLIENTDIR):
    """
    Creates an index on the devpi server.

    :param str index: The index to create. For example, ``root/devpitest``.
        This gets appended to whatever ``server`` value gets passed into
        :py:func:`select_server`.
    :param str clientdir: Path to a directory for the devpi CLI to store state.
    :rtype: subprocess.CompletedProcess
    """
    return subprocess.run([
        'devpi', 'index', '--clientdir', clientdir, '-c', index])


@die_on_error
def upload_package(path, clientdir=DEFAULT_CLIENTDIR, files=None):
    """
    Upload the package residing at ``path`` to the currently selected devpi
    server + index.

    :param str path: An absolute or relative path to the directory containing
        the package you'd like to upload.
    :param str clientdir: Path to a directory for the devpi CLI to store state.
    :rtype: subprocess.CompletedProcess
    """
    cmd = ['devpi', 'upload', '--clientdir',
           clientdir, '--from-dir', '--no-vcs']
    if files:
        cmd.extend(expand_files(path, files))
    cmd = subprocess.Popen(cmd, cwd=path)
    cmd.wait()
    return cmd


def expand_files(path, patterns):
    """
    Expand files patterns into filenames
    """
    files = []
    if isinstance(patterns, str):
        patterns = [patterns]
    for pattern in patterns:
        pattern = os.path.join(path, pattern)
        for filename in glob(pattern):
            files.append(filename)
    return files


def check_vargs(vargs):
    """
    Check over the args passed in to make sure that we have everything we
    need to get the upload done. Exit with code 1 if the input is bad.

    :param dict vargs: Contents of the 'vargs' JSON array in the
        the plugin input.
    """
    server_uri = vargs.get('server', '')
    parsed = urllib.parse.urlsplit(server_uri)
    if not all([parsed.scheme, parsed.netloc]):
        print(
            "You must specify the full, absolute URI to your devpi server "
            "(including protocol).")
        sys.exit(1)
    index = vargs.get('index')
    if not index:
        print("You must specify an index on your devpi server to upload to.")
        sys.exit(1)
    username = vargs.get('username')
    if not username:
        print("You must specify a username to upload packages as.")
        sys.exit(1)
    password = vargs.get('password')
    if password is None:
        print("You must specify a password.")
        sys.exit(1)


def main():
    payload = drone.plugin.get_input()
    vargs = payload['vargs']
    check_vargs(vargs)

    select_server(vargs['server'])
    login(vargs['username'], vargs['password'])
    select_index(vargs['index'])
    upload_package(payload['workspace']['path'], files=vargs.get('files'))

if __name__ == "__main__":
    main()
