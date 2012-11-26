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
from cimibase import make_response_data
from cimiutils import concat, match_up

LOG = logging.getLogger(__name__)


class MachineConfigCtrler(Controller):
    """
    Handles machine image request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(MachineConfigCtrler, self).__init__(conf, app, req, tenant_id,
                                                  *args)
        self.os_path = '/%s/flavors' % (tenant_id)
        self.config_id = args[0] if len(args) > 0 else ''
        self.entity_uri = 'MachineConfiguration'
        self.metadata = Consts.MACHINECONFIG_METADATA


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
            flavor = json.loads(res.body).get('flavor')
            if flavor:
                body = {}
                body['resourceURI'] = '/'.join([self.uri_prefix,
                                                self.entity_uri])
                body['id'] = '/'.join([self.tenant_id, self.entity_uri,
                                       self.config_id])
                match_up(body, flavor, 'name', 'name')
                match_up(body, flavor, 'cpu', 'vcpus')
                match_up(body, flavor, 'memory', 'ram')
                body['disks'] = []
                body['disks'].append({'capacity':
                                      int(flavor.get('disk')) * 1000 })

            if self.res_content_type == 'application/xml':
                body.pop('resourceURI')
                response_data = {self.entity_uri: body}
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

        return res


class MachineConfigColCtrler(Controller):
    """
    Handles machine image collection request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(MachineConfigColCtrler, self).__init__(conf, app, req, tenant_id,
                                                     *args)
        self.os_path = '/%s/flavors' % (tenant_id)
        self.entity_uri = 'MachineConfigurationCollection'
        
        self.metadata = Consts.MACHINECONFIG_COL_METADATA

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET Container (List Objects) request
        """

        env = copy.copy(req.environ)

        env['SCRIPT_NAME'] = self.os_version
        env['PATH_INFO'] = self.os_path
        # we will always use json format to get Nova information
        env['HTTP_ACCEPT'] = 'application/json'

        # need to remove this header, otherwise, it will always take the
        # original request accept content type
        if env.has_key('nova.best_content_type'):
            env.pop('nova.best_content_type')
        new_req = Request(env)

        res = new_req.get_response(self.app)
        if res.status_int == 200:
            content = json.loads(res.body)
            body = {}
            body['resourceURI'] = '/'.join([self.uri_prefix, self.entity_uri])
            body['id'] = '/'.join([self.tenant_id, self.entity_uri])
            body['machineConfigurations'] = []
            flavors = content.get('flavors',[])
            for flavor in flavors:
                entry = {}
                entry['resourceURI'] = '/'.join([self.uri_prefix,
                                            'MachineConfiguration'])
                entry['id'] = '/'.join([self.tenant_id,
                                        'MachineConfiguration',
                                        flavor['id']])

                body['machineConfigurations'].append(entry)

            body['count'] = len(body['machineConfigurations'])

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
            return res
