# Copyright (c) 2012 IBM
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# This is the module which defines some useful functions for cimi
# implementation. This module should not reference any methods defined
# in cimi implementation modules. This is to avoid any circular reference

from webob import Request, Response
from nova.openstack.common import log as logging
from eventlet.green.httplib import HTTPConnection, HTTPSConnection

CIMI_CONTENT_TYPES = ['application/json', 'application/xml']
LOG = logging.getLogger(__name__)


def get_err_response(code):
    """
    Given an HTTP response code, create a properly formatted error response

    :param code: error code
    :returns: webob.response object
    """

    error_table = {
        'AccessDenied':
            (403, 'Access denied'),
        'BadRequest':
            (400, 'Bad request'),
        'MalformedBody':
            (400, 'Request body can not be parsed, malformed request body'),
        'NotImplemented':
            (501, 'Not implemented'),
        'TestRequest':
            (200, 'Test request'),
        'Conflict':
            (409, 'The requested name already exists as a different type')}

    resp = Response()
    resp.status = error_table[code][0]
    resp.body = error_table[code][1]
    return resp


def concat(*args):
    return ''.join(args)


def best_match(content_type):
    """
    Use webob request accept member to determine what is the best match
    for a given content type. This can be used for determining both request
    and response content type
    """

    req = Request.blank('/')
    req.accept = content_type
    return req.accept.best_match(CIMI_CONTENT_TYPES) or 'application/json'


def get_href(data, member):
    if data:
        if data.get(member):
            return data.get(member).get('href')

    return None


def get_last_part(path):
    if path:
        parts = path.rstrip('/ ').split('/')
        return parts[-1]
    return ''


def sub_path(path, map):
    for k, v in map.items():
        path = path.replace(k, v, 1)
    return path


def match_up(data_to, data_from, key_to, key_from):
    def get_member(data, key_path, get_parent):
        value = None
        mem_key = None
        if key_path:
            keys = key_path.strip('/').split('/')
            key_lens = len(keys)
            if get_parent:
                key_lens -= 1
                mem_key = keys[-1]
            value = data
            for idx in range(key_lens):
                if value:
                    value = value.get(keys[idx])
                else:
                    break
        return value, mem_key
    data, key = get_member(data_to, key_to, True)
    if key:
        data[key] = get_member(data_from, key_from, False)[0]

def map_status(map, key):
    if map.get(key) == 'ACTIVE' :
        map[key] = 'STARTED'
    elif map.get(key) == 'BUILDING':
        map[key] = 'CREATING'
    else:
        map[key] = 'ERROR'    

def access_resource(env, method, path, get_body=False, query_string=None):
    """
    Use this method to send a http request
    If the resource exists, then it should return True with headers.
    If the resource does not exist, then it should return False with None
    headers
    If the get_body is set to True, the response body will also be returned
    """

    # Create a new Request
    req = Request(env)
    if req.scheme.lower() == 'https':
        connection = HTTPSConnection
        ssl = True
    else:
        connection = HTTPConnection
        ssl = False

    headers = {}
    headers['Accept'] = 'application/json'
    for header, value in req.headers.items():
        headers[header] = value

    method = 'GET' if not method else method
    path = req.path if not path else path

    conn = connection(req.server_name, req.server_port)

    conn.request(method, path, '', headers)
    res = conn.getresponse()

    if res.status == 404:
        conn.close()
        return False, {}, None
    elif res.status == 200 or res.status == 204:
        values = {}
        header_list = res.getheaders()
        for header in header_list:
            values[header[0]] = header[1]
        if get_body:
            length = res.getheader('content-length')
            if length:
                body = res.read(int(length))
            else:
                body = res.read()
        else:
            body = ""
        conn.close()
        return True, values, body
    else:
        values = {}
        header_list = res.getheaders()
        for header in header_list:
            values[header[0]] = header[1]
        conn.close()
        return True, values, None

