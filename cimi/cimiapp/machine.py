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
from cimiutils import remove_member, map_machine_state
from nova.api.openstack.wsgi import XMLDictSerializer, JSONDictSerializer

LOG = logging.getLogger(__name__)


class MachineCtrler(Controller):
    """
    Handles machine request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(MachineCtrler, self).__init__(conf, app, req, tenant_id,
                                            *args)
        self.os_path = '/%s/servers' % (tenant_id)
        self.entity_uri = 'Machine'
        self.metadata = Consts.MACHINE_METADATA
        self.actions = Consts.MACHINE_ACTIONS

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
            body['id'] = concat(self.tenant_id, '/Machine/',
                                parts[0])
            match_up(body, data, 'name', 'name')
            match_up(body, data, 'created', 'created')
            match_up(body, data, 'updated', 'updated')
            body['state'] = map_machine_state(data['status'])

            body['networkInterfaces'] = {'href': '/'.join([self.tenant_id,
                'NetworkInterfacesCollection', parts[0]])}

            body['volumes'] = {'href': '/'.join([self.tenant_id,
                'MachineVolumeCollection', parts[0]])}
            body['disks'] = {'href': '/'.join([self.tenant_id,
                'MachineDiskCollection', parts[0]])}


            # Send a request to get the details on flavor
            env = self._fresh_env(req)
            env['PATH_INFO'] = '/%s/flavors/%s' % (self.tenant_id,
                                                   data['flavor']['id'])
            new_req = Request(env)
            res = new_req.get_response(self.app)
            if res.status_int == 200:
                flavor = json.loads(res.body).get('flavor')
                match_up(body, flavor, 'cpu', 'vcpus')
                body['memory'] = int(flavor.get('ram')) * 1000

            # deal with machine operations
            operations = []
            action_url = '/'.join([self.tenant_id, 'Machine', parts[0]])

            action_name = '/'.join([self.uri_prefix, 'action/start'])
            operations.append(self._create_op(action_name, action_url))

            action_name = '/'.join([self.uri_prefix, 'action/stop'])
            operations.append(self._create_op(action_name, action_url))

            action_name = '/'.join([self.uri_prefix, 'action/restart'])
            operations.append(self._create_op(action_name, action_url))

            action_name = '/'.join([self.uri_prefix, 'action/pause'])
            operations.append(self._create_op(action_name, action_url))

            action_name = '/'.join([self.uri_prefix, 'action/suspend'])
            operations.append(self._create_op(action_name, action_url))

            action_name = 'delete'
            operations.append(self._create_op(action_name, action_url))

            body['operations'] = operations

            if self.res_content_type == 'application/xml':
                response_data = {'Machine': body}
                remove_member(response_data, 'resourceURI')
            else:
                body['resourceURI'] = '/'.join([self.uri_prefix,
                                               self.entity_uri])
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

    def _run_method(self, req, request_data, method, *parts):
        """
        Handle the machine reboot request
        """
        data = {}
        if method == 'reboot':
            force = request_data.get('force', False)
            if isinstance(force, str):
                force = 'HARD' if force.lower() == 'true' else 'SOFT'
            else:
                force = 'HARD' if force else 'SOFT'
            data['reboot'] = {'type': force}
        else:
            data[method] = None

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
        resp = None
        if action in Consts.MACHINE_ACTIONS:
            # Need to get the current machine state
            env = self._fresh_env(req)
            env['SCRIPT_NAME'] = '/v2'
            env['CONTENT_LENGTH'] = 0

            action = action.split('/')[-1]
            access_path = '/'.join(['/v2', self.tenant_id, 'servers',
                                    parts[0]])
            status, headers, body, status_code = access_resource(env, 'GET',
                access_path, True, None, None)
            if status:
                body = json.loads(body)
                key = ''.join([body['server']['status'].lower(), '_', action])
                method = Consts.MACHINE_ACTION_MAPS.get(key)
                if method:
                    resp = self._run_method(req, request_data, method, *parts)
            else:
                resp = get_err_response('NotFound')

        if resp:
            return resp
        else:
            return get_err_response('NotImplemented')

    def DELETE(self, req, *parts):
        """
        Handle Machine delete
        """
        env = self._fresh_env(req)
        env['PATH_INFO'] = concat(self.os_path, '/', parts[0])
        env['REQUEST_METHOD'] = 'DELETE'
        new_req = Request(env)
        res = new_req.get_response(self.app)
        return res


class MachineColCtrler(Controller):
    """
    Handles machine collection request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(MachineColCtrler, self).__init__(conf, app, req, tenant_id,
                                                     *args)
        self.os_path = '/%s/servers/detail' % (tenant_id)
        self.entity_uri = 'MachineCollection'
        self.metadata = Consts.MACHINE_COL_METADATA

        self.machine_metadata = Consts.MACHINE_METADATA

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET machine request
        """

        new_req = self._fresh_request(req)

        res = new_req.get_response(self.app)
        if res.status_int == 200:
            content = json.loads(res.body)
            body = {}
            body['id'] = concat(self.tenant_id,
                                '/', self.entity_uri)
            body['resourceURI'] = '/'.join([self.uri_prefix,
                                            self.entity_uri])

            env = self._fresh_env(req)
            env['PATH_INFO'] = '/%s/flavors/detail' % (self.tenant_id)
            new_req = Request(env)
            res = new_req.get_response(self.app)
            if res.status_int == 200:
                flavors = json.loads(res.body).get('flavors')
            else:
                flavors = []

            keyed_flavors = {}
            for flavor in flavors:
                keyed_flavors[flavor['id']] = flavor

            body['machines'] = []
            machines = content.get('servers', [])
            for machine in machines:
                entry = {}
                if self.res_content_type != 'application/xml':
                    entry['resourceURI'] = '/'.join([self.uri_prefix,
                                                 'Machine'])
                entry['id'] = concat(self.tenant_id, '/',
                                     'machine/',
                                     machine['id'])
                entry['name'] = machine['name']
                #entry['property'] = machine['metadata']
                entry['created'] = machine['created']
                entry['updated'] = machine['updated']
                entry['state'] = map_machine_state(machine['status'])
                flavor = keyed_flavors[machine['flavor']['id']]
                entry['cpu'] = flavor['vcpus']
                entry['memory'] = int(flavor['ram']) * 1000

                entry['volumes'] = {'href': '/'.join([self.tenant_id,
                    'MachineVolumeCollection', machine['id']])}
                entry['networkInterfaces'] = {'href': '/'.join([self.tenant_id,
                    'NetworkInterfacesCollection', machine['id']])}
                entry['disks'] = {'href': '/'.join([self.tenant_id,
                    'MachineDiskCollection', machine['id']])}

                body['machines'].append(entry)

            body['count'] = len(body['machines'])
            # deal with machine operations
            operations = []
            operations.append(self._create_op('add',
                                              '/'.join([self.tenant_id,
                                                       'machineCollection'])))
            body['operations'] = operations

            if self.res_content_type == 'application/xml':
                body['resourceURI'] = '/'.join([self.uri_prefix,
                                                'MachineCollection'])
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
            return res

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
            data = request_data.get('body').get('MachineCreate')
            if not data:
                data = request_data.get('body')
            if data:
                new_body = {}
                match_up(new_body, data, 'name', 'name')

                if (data.get('machineTemplate') is None or
                    data.get('machineTemplate').get('machineImage') is None or
                    data.get('machineTemplate').get('machineConfig') is None):
                    return get_err_response('BadRequest')

                match_up(new_body, data, 'imageRef',
                         'machineTemplate/machineImage/href')

                match_up(new_body, data, 'flavorRef',
                         'machineTemplate/machineConfig/href')

                if (new_body.get('flavorRef') is None or
                    new_body.get('imageRef') is None):
                    return get_err_response('BadRequest')

                new_body['imageRef'] = new_body.get('imageRef').split('/')[-1]
                new_body['flavorRef'] = \
                    new_body.get('flavorRef').split('/')[-1]

                adminPass = data.get('credentials', {}).get('password')
                if adminPass:
                    new_body['adminPass'] = adminPass

                self.os_path = '/%s/servers' % (self.tenant_id)
                new_req = self._fresh_request(req)

                new_req.body = json.dumps({'server': new_body})
                resp = new_req.get_response(self.app)
                if resp.status_int == 201:
                    # resource created successfully, we redirect the request
                    # to query machine
                    resp_data = json.loads(resp.body)
                    id = resp_data.get('server').get('id')
                    env = self._fresh_env(req)
                    env['PATH_INFO'] = concat(self.request_prefix,
                                              '/', self.tenant_id,
                                              '/servers/', id)
                    env['REQUEST_METHOD'] = 'GET'
                    new_req = Request(env)
                    resp = new_req.get_response(self.app)
                    resp.status = 201
                elif resp.status_int == 202:
                    resp_body_data = json.loads(resp.body).get('server')
                    id = resp_body_data.get('id')
                    resp_data = {}
                    match_up(resp_data, data, 'name', 'name')
                    resp_data['id'] = concat(self.tenant_id, '/Machine/', id)
                    resp_data['credentials'] = {'userName': 'root',
                        'password': resp_body_data.get('adminPass')}
                    if self.res_content_type == 'application/xml':
                        response_data = {'Machine': resp_data}
                        remove_member(response_data, 'resourceURI')
                    else:
                        response_data = resp_data

                    new_content = make_response_data(response_data,
                                             self.res_content_type,
                                             self.machine_metadata,
                                             self.uri_prefix)
                    resp = Response()
                    self._fixup_cimi_header(resp)
                    resp.headers['Content-Type'] = self.res_content_type
                    resp.status = 202
                    resp.body = new_content
                return resp
            else:
                return get_err_response('BadRequest')
        else:
            return get_err_response('BadRequest')