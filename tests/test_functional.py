#
#    Copyright (c) 2013+ Evgeny Safronov <division494@gmail.com>
#    Copyright (c) 2011-2013 Other contributors as noted in the AUTHORS file.
#
#    This file is part of Cocaine.
#
#    Cocaine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Cocaine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import json
import os
import shutil
import logging
import subprocess
import tarfile
import unittest
import sys
import time
import contextlib

__author__ = 'Evgeny Safronov <division494@gmail.com>'


log = logging.getLogger(__name__)
h = logging.StreamHandler(stream=sys.stdout)
log.addHandler(h)
log.setLevel(logging.INFO)
log.propagate = False

ROOT_PATH = '/Users/esafronov/testing'
PLUGINS_PATH = os.path.join(ROOT_PATH, 'usr/lib/cocaine')
RUNTIME_PATH = os.path.join(ROOT_PATH, 'var/run/cocaine')
SPOOL_PATH = os.path.join(ROOT_PATH, 'var/spool/cocaine')

COCAINE_RUNTIME_PATH = '/Users/esafronov/sandbox/cocaine-core-build/cocaine-runtime'
COCAINE_TOOL = '/Users/esafronov/sandbox/cocaine-framework-python/scripts/cocaine-tool'

config = {
    "version": 2,
    "paths": {
        "plugins": PLUGINS_PATH,
        "runtime": RUNTIME_PATH,
        "spool": SPOOL_PATH
    },
    "locator": {
        "port": 10053
    },
    "services": {
        "logging": {
            "type": "logging"
        },
        "storage": {
            "type": "storage"
        },
        "node": {
            "type": "node",
            "args": {
                "announce": ["tcp://*:5001"],
                "announce-interval": 1,
                "runlist": "default"
            }
        }
    },
    "storages": {
        "core": {
            "type": "files",
            "args": {
                "path": os.path.join(ROOT_PATH, 'var/lib/cocaine')
            }
        }
    },
    "logging": {
        "core": {
            "formatter": {
                "type": "string",
                "format": "[%(time)s] [%(level)s] %(source)s: %(message)s"
            },
            "handler": {
                "type": "files",
                "path": "/dev/stdout",
                "verbosity": "info"
            }
        }
    },
    # Old style logging config
    "loggers": {
        "core": {
            "type": "files",
            "args": {
                "path": "/dev/stdout",
                "verbosity": "info"
            }
        }
    }
}


def call(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()
    stdout, stderr = p.communicate()
    return p.returncode, stdout, stderr


def trim(string):
    return string.replace(' ', '').replace('\n', '')


def make_manifest(dirname):
    manifest = {'slave': 'app'}
    path = os.path.join(dirname, 'manifest.json')
    with open(path, 'w') as fh:
        fh.write(json.dumps(manifest))
    return path


def make_app(dirname):
    path = os.path.join(dirname, 'app')
    with open(path, 'w') as fh:
        fh.write('')
    os.chmod(path, 0755)
    return path


def make_package(dirname, app_path):
    path = os.path.join(dirname, 'package.tar.gz')
    fh = tarfile.open(path, 'w|gz')
    fh.add(app_path)
    fh.close()
    return path

@contextlib.contextmanager
def prepare_app():
    APP_ROOT_PATH = os.path.join(ROOT_PATH, 'app')
    try:
        os.makedirs(APP_ROOT_PATH)
        manifest_path = make_manifest(APP_ROOT_PATH)
        app_path = make_app(APP_ROOT_PATH)
        package_path = make_package(APP_ROOT_PATH, app_path)
        yield app_path, manifest_path, package_path
    finally:
        shutil.rmtree(APP_ROOT_PATH, ignore_errors=True)


@contextlib.contextmanager
def upload_app(name):
    APP_ROOT_PATH = os.path.join(ROOT_PATH, 'app')
    try:
        os.makedirs(APP_ROOT_PATH)
        manifest_path = make_manifest(APP_ROOT_PATH)
        app_path = make_app(APP_ROOT_PATH)
        package_path = make_package(APP_ROOT_PATH, app_path)

        call([COCAINE_TOOL, 'app', 'upload',
              '--name', name,
              '--manifest', manifest_path,
              '--package', package_path])
        yield
    finally:
        shutil.rmtree(APP_ROOT_PATH, ignore_errors=True)


def upload_profile(name):
    profile = {
        'isolate': {
            'args': {
                'spool': SPOOL_PATH
            }
        }
    }
    call([COCAINE_TOOL, 'profile', 'upload', '--name', name, '--profile', json.dumps(profile)])


class ToolsTestCase(unittest.TestCase):
    pid = -1

    def setUp(self):
        log.info('Cleaning up %s ...', ROOT_PATH)
        shutil.rmtree(ROOT_PATH, ignore_errors=True)

        log.info('Preparing ...')
        log.info(' - creating "%s"', ROOT_PATH)
        paths = [ROOT_PATH, PLUGINS_PATH, RUNTIME_PATH, SPOOL_PATH]
        map(lambda path: os.makedirs(path), paths)
        config_path = os.path.join(ROOT_PATH, 'config.json')
        log.info(' - creating config at "%s"', config_path)
        with open(config_path, 'w') as fh:
            fh.write(json.dumps(config))

        log.info(' - starting cocaine-runtime ...')
        p = subprocess.Popen([COCAINE_RUNTIME_PATH, '-c', config_path], stdout=subprocess.PIPE)
        time.sleep(0.1)
        self.pid = p.pid

    def tearDown(self):
        log.info('Cleaning up ...')
        log.info(' - killing cocaine-runtime (%d pid) ...', self.pid)
        if self.pid != -1:
            os.kill(self.pid, 9)
        log.info(' - cleaning up "%s" ...', ROOT_PATH)
        shutil.rmtree(ROOT_PATH, ignore_errors=True)

    def test_app_upload_cycle(self):
        with prepare_app() as (app_path, manifest_path, package_path):
            code, out, err = call([COCAINE_TOOL, 'app', 'upload',
                                   '--name', 'test_app',
                                   '--manifest', manifest_path,
                                   '--package', package_path])
            self.assertEqual(0, code)
            self.assertEqual('', out)
            self.assertEqual('Uploading "test_app"... OK\n', err)

            code, out, err = call([COCAINE_TOOL, 'app', 'list'])
            self.assertEqual(0, code)
            self.assertEqual('["test_app"]', trim(out))
            self.assertEqual('', err)

            code, out, err = call([COCAINE_TOOL, 'app', 'remove',
                                   '--name', 'test_app'])
            self.assertEqual(0, code)
            self.assertEqual('', out)
            self.assertEqual('Removing "test_app"... OK\n', err)

    def test_profile(self):
        code, out, err = call([COCAINE_TOOL, 'profile', 'upload',
                               '--name', 'test_profile',
                               '--profile', '"{}"'])
        self.assertEqual(0, code)
        self.assertEqual('The profile "test_profile" has been successfully uploaded\n', out)
        self.assertEqual('', err)

        code, out, err = call([COCAINE_TOOL, 'profile', 'list'])
        self.assertEqual(0, code)
        self.assertEqual('["test_profile"]', trim(out))
        self.assertEqual('', err)

        code, out, err = call([COCAINE_TOOL, 'profile', 'remove',
                               '--name', 'test_profile'])
        self.assertEqual(0, code)
        self.assertEqual('The profile "test_profile" has been successfully removed\n', out)
        self.assertEqual('', err)

    def test_runlist(self):
        code, out, err = call([COCAINE_TOOL, 'runlist', 'upload',
                               '--name', 'test_runlist',
                               '--runlist', "{}"])
        self.assertEqual(0, code)
        self.assertEqual('The runlist "test_runlist" has been successfully uploaded\n', out)
        self.assertEqual('', err)

        code, out, err = call([COCAINE_TOOL, 'runlist', 'list'])
        self.assertEqual(0, code)
        self.assertEqual('["test_runlist"]', trim(out))
        self.assertEqual('', err)

        code, out, err = call([COCAINE_TOOL, 'runlist', 'remove',
                               '--name', 'test_runlist'])
        self.assertEqual(0, code)
        self.assertEqual('The runlist "test_runlist" has been successfully removed\n', out)
        self.assertEqual('', err)

    def test_app_start(self):
        with upload_app('test_app'):
            upload_profile('default')
            code, out, err = call([COCAINE_TOOL, 'app', 'start',
                                   '--name', 'test_app',
                                   '--profile', 'default'])
            self.assertEqual(0, code)
            self.assertEqual(trim('{"test_app": "the app has been started"}'), trim(out))
            self.assertEqual('', err)

    def test_app_start_fail_because_of_app(self):
        upload_profile('default')
        code, out, err = call([COCAINE_TOOL, 'app', 'start',
                               '--name', 'test_app',
                               '--profile', 'default'])
        self.assertEqual(1, code)
        self.assertEqual('', out)
        self.assertEqual(('Error occurred: '
                          'error in service "node" - '
                          'object \'test_app\' has not been found in \'manifests\': '
                          'object has not been found [2]\n'), err)

    def test_app_start_fail_because_of_profile(self):
        with upload_app('test_app'):
            code, out, err = call([COCAINE_TOOL, 'app', 'start',
                                   '--name', 'test_app',
                                   '--profile', 'default'])
            self.assertEqual(1, code)
            self.assertEqual('', out)
            self.assertEqual(('Error occurred: '
                              'error in service "node" - '
                              'object \'default\' has not been found in \'profiles\': '
                              'object has not been found [2]\n'), err)
