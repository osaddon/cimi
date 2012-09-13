# Copyright (c) 2010-2011 IBM.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
#from test import get_config

import ConfigParser
import httplib
import time
import json
import base64
import os


def get_config(section_name=None, defaults=None):
    """
    Attempt to get a test config dictionary.

    :param section_name: the section to read (all sections if not defined)
    :param defaults: an optional dictionary namespace of defaults
    """
    path = os.path.dirname(os.path.realpath(__file__))
    config_file = os.environ.get('CIMI_TEST_CONFIG_FILE',
                                 os.sep.join([path, 'test.conf']))
    config = {}
    if defaults is not None:
        config.update(defaults)

    cp = ConfigParser.RawConfigParser()
    cp.read(config_file)
    config.update(cp.defaults())

    return config


def get_auth(auth_host, auth_port, auth_url, user_name, user_key, tenant_name):
    """Authenticate"""
    conn = httplib.HTTPConnection(auth_host, auth_port)

    headers = {'Accept': 'application/json',
               'Content-Type': 'application/json'}
    body = {}
    body['auth'] = {
        "passwordCredentials": {
            "username": user_name,
            "password": user_key,
        },
        "tenantName": tenant_name
    }
    conn.request('POST', auth_url,
                 json.dumps(body, indent=2), headers)

    res = conn.getresponse()
    if res.status != 200:
        raise Exception('The authentication has failed')

    data = res.read()
    body = json.loads(data)
    token = body.get('access').get('token').get('id')
    tenant_id = body.get('access').get('token').get('tenant').get('id')
    return token, tenant_id
