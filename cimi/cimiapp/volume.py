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


from nova.openstack.common import log as logging
from webob import Request, Response
import json
import copy

from cimibase import Controller, Consts
from cimibase import CimiXMLSerializer
from cimibase import make_response_data
from cimibase import get_request_data
from cimiutils import concat, get_err_response
from cimiutils import match_up, sub_path, access_resource
from nova.api.openstack.wsgi import XMLDictSerializer, JSONDictSerializer

LOG = logging.getLogger(__name__)


class VolumeCtrler(Controller):
    """
    Handles machine request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(VolumeCtrler, self).__init__(conf, app, req, tenant_id,
                                            *args)
        self.os_path = '/%s/servers' % (tenant_id)
        self.entity_uri = 'Volume'
        self.metadata = {'attributes': {'memory': ['quantity', 'units'],
                                        'property': 'key',
                                        'volumes': 'href',
                                        'networkInterfaces': 'href',
                                        'Entry': 'resourceURI',
                                        'operation': ['rel', 'href']},
                         'plurals': {'entries': 'Entry'},
                         'sequence': {'Machine':
                                      ['id', 'name', 'description',
                                       'created', 'updated', 'property',
                                       'state', 'cpu', 'memory', 'disks',
                                       'networkInterfaces',
                                       'operations']}}
        self.actions = {concat(self.uri_prefix, 'action/restart'): 'reboot',
                        concat(self.uri_prefix, 'action/stop'): 'delete'}

    def _create_op(self, name, id):
        entry = {}
        entry['rel'] = name
        entry['href'] = concat(self.tenant_id, '/machine/', id)
        return entry

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET Container (List Objects) request
        """

        env = self._fresh_env(req)
        env['PATH_INFO'] = concat(self.os_path,
                                  '/', '/'.join(parts))
        new_req = Request(env)
        res = new_req.get_response(self.app)

        if res.status_int == 200:
            data = json.loads(res.body).get('server')

            body = {}
            body['id'] = concat(self.tenant_id, '/machine/',
                                parts[0])
            match_up(body, data, 'name', 'name')
            match_up(body, data, 'created', 'created')
            match_up(body, data, 'updated', 'updated')
            match_up(body, data, 'state', 'status')
            body['networkInterfaces'] = {'href': concat(self.tenant_id,
                    '/networkInterfacesCollection/', parts[0])}

            # Send a request to get the details on flavor
            env = self._fresh_env(req)
            env['PATH_INFO'] = '/%s/flavors/%s' % (self.tenant_id, 
                                                   data['flavor']['id'])
            new_req = Request(env)
            res = new_req.get_response(self.app)
            if res.status_int == 200:
                flavor = json.loads(res.body).get('flavor')
                match_up(body, flavor, 'cpu', 'vcpus')
                ram = {}
                match_up(ram, flavor, 'quantity', 'ram')
                ram['units'] = 'MB'
                body['memory'] = ram
                disks = []
                disks.append({'capacity': int(flavor.get('disk')) * 1000})
                body['disks'] = disks

            # deal with machine operations
            operations = []
            name = concat(self.uri_prefix, 'action/stop')
            operations.append(self._create_op(name, parts[0]))
            name = concat(self.uri_prefix, 'action/restart')
            operations.append(self._create_op(name, parts[0]))
            body['operations'] = operations

            if self.res_content_type == 'application/xml':
                response_data = {'Machine': body}
            else:
                body['resourceURI'] = concat(self.uri_prefix, self.entity_uri)
                response_data = body

            new_content = make_response_data(response_data,
                                             self.res_content_type,
                                             self.metadata,
                                             self.uri_prefix)
            resp = Response()
            self._fixup_cimi_header(resp)
            resp.headers['Content-Type'] = self.res_content_type
            resp.status = 200
            resp.body = new_content
            return resp
        else:
            return res

    def _delete(self, req, request_data, *parts):
        """
        Handle the stop machine request
        """
        env = self._fresh_env(req)
        env['PATH_INFO'] = concat(self.os_path, '/', parts[0])
        env['REQUEST_METHOD'] = 'DELETE'
        new_req = Request(env)
        res = new_req.get_response(self.app)
        return res

    def _reboot(self, req, request_data, *parts):
        """
        Handle the machine reboot request
        """
        data = {}
        force = request_data.get('force', False)
        if isinstance(force, str):
            force = 'HARD' if force.lower() == 'true' else 'SOFT'
        else:
            force = 'HARD' if force else 'SOFT'
        data['reboot'] = {'type': force}
        env = self._fresh_env(req)
        env['PATH_INFO'] = concat(self.os_path, '/', parts[0], '/action')
        env['CONTENT_TYPE'] = 'application/json'
        new_req = Request(env)
        new_req.body = json.dumps(data)
        res = new_req.get_response(self.app)

        return res

    def POST(self, req, *parts):
        """
        Handle Machine operations
        """
        try:
            request_data = get_request_data(req.body, self.req_content_type)
        except Exception as error:
            return get_err_response('MalformedBody')

        request_data = request_data.get('body', {})
        if request_data.get('Action'):
            request_data = request_data.get('Action')
        action = request_data.get('action', 'notexist')
        method = self.actions.get(action)
        if method:
            resp = getattr(self, '_' + method)(req, request_data, *parts)
        else:
            resp = get_err_response('NotImplemented')

        return resp


class VolumeColCtrler(Controller):
    """
    Handles machine collection request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(VolumeColCtrler, self).__init__(conf, app, req, tenant_id,
                                                     *args)
        self.os_path = '/%s/volumes' % (tenant_id)
        self.entity_uri = 'VolumeCollection'
        self.metadata = Consts.VOLUME_COL_METADATA
        self.volume_metadata = Consts.VOLUME_METADATA

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET machine request
        """

        env = self._fresh_env(req)
        env['SERVER_PORT'] = self.conf.get('volume_endpoint_port')
        env['SCRIPT_NAME'] = '/v1'
        env['HTTP_HOST'] = '%s:%s'%(self.conf.get('volume_endpoint_host'),
                                    self.conf.get('volume_endpoint_port'))

        status, headers, body = access_resource(env, 'GET',
                                               '/v1/' + self.os_path,
                                               True, None)
        if status:
            content = json.loads(body)
            body = {}
            body['resourceURI'] = '/'.join([self.uri_prefix.rstrip('/'),
                                            self.entity_uri])
            body['id'] = '/'.join([self.tenant_id, self.entity_uri])
            body['volumes'] = []
            volumes = content.get('volumes', [])
            for volume in volumes:
                entry = {}
                entry['resourceURI'] = '/'.join([self.uri_prefix.rstrip('/'),
                                                 'Volume'])
                entry['id'] = '/'.join([self.tenant_id, 'Volume',
                                        volume['id']])

                body['volumes'].append(entry)

            body['count'] = len(body['volumes'])
            if self.res_content_type == 'application/xml':
                response_data = {'Collection': body}
            else:
                response_data = body

            new_content = make_response_data(response_data,
                                             self.res_content_type,
                                             self.metadata,
                                             self.uri_prefix)
            resp = Response()
            self._fixup_cimi_header(resp)
            resp.headers['Content-Type'] = self.res_content_type
            resp.status = 200
            resp.body = new_content

            return resp
        else:
            resp = Response()
            resp.status = 404
            return resp

    # Use GET to handle all container read related operations.
    def POST(self, req, *parts):
        """
        Handle POST machine request which will create a machine
        """

        try:
            request_data = get_request_data(req.body, self.req_content_type)
        except Exception as error:
            return get_err_response('MalformedBody')

        if request_data:
            data = request_data.get('body').get('VolumeCreate')
            if not data:
                data = request_data.get('body')
                if data:
                    action = data.get('resourceURI')
                    # this is to ensure that the json format contains
                    # the right indicator for volume create
                    if not action or action != ''.join([self.uri_prefix,
                                          'VolumeCreate']):
                        data = None
            if data:
                new_body = {}
                match_up(new_body, data, 'display_name', 'name')
                match_up(new_body, data, 'display_description', 'description')
                match_up(new_body, data, 'size',
                         'volumeTemplate/volumeConfig/capacity')

                LOG.info(new_body)
                env = self._fresh_env(req)
                env['SERVER_PORT'] = self.conf.get('volume_endpoint_port')
                env['SCRIPT_NAME'] = '/v1'
                env['HTTP_HOST'] = '%s:%s' % \
                    (self.conf.get('volume_endpoint_host'),
                     self.conf.get('volume_endpoint_port'))
                new_body_json = json.dumps({'volume': new_body})
                env['CONTENT_LENGTH'] = len(new_body_json)

                status, headers, body = access_resource(env, 'POST',
                                               '/v1' + self.os_path,
                                               True, None,
                                               new_body_json)

                if status:
                    # resource created successfully, we redirect the request
                    # to query machine
                    resp_data = json.loads(body)
                    data = resp_data.get('volume')
                    resp_data = {}
                    match_up(resp_data, data, 'name', 'display_name')
                    match_up(resp_data, data, 'description',
                             'display_description')
                    match_up(resp_data, data, 'capacity', 'size')
                    match_up(resp_data, data, 'created', 'created_at')
                    resp_data['id'] = ''.join([self.tenant_id,
                                               '/volume/',
                                               data.get('id')])
                    if self.res_content_type == 'application/xml':
                        response_data = {'Volume': resp_data}
                    else:
                        resp_data['resourceURI'] = ''.join([self.uri_prefix,
                                                            'Volume'])
                        response_data = resp_data

                    new_content = make_response_data(response_data,
                                             self.res_content_type,
                                             self.volume_metadata,
                                             self.uri_prefix)
                    resp = Response()
                    self._fixup_cimi_header(resp)
                    resp.headers['Content-Type'] = self.res_content_type
                    resp.status = 201
                    resp.body = new_content
                    return resp
                else:
                    return get_err_response('BadRequest')
            else:
                return get_err_response('BadRequest')
        else:
            return get_err_response('BadRequest')