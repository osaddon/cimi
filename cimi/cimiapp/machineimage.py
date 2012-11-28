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
from cimiutils import concat, match_up, image_map_status, remove_member

LOG = logging.getLogger(__name__)


class MachineImageCtrler(Controller):
    """
    Handles machine image request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(MachineImageCtrler, self).__init__(conf, app, req, tenant_id,
                                                 *args)
        self.os_path = '/%s/images' % (tenant_id)
        self.image_id = args[0] if len(args) > 0 else ''
        self.entity_uri = 'MachineImage'
        self.metadata = Consts.MACHINEIMAGE_METADATA

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET Container (List Objects) request
        """

        env = self._fresh_env(req)
        env['PATH_INFO'] = '/'.join([self.os_path, self.image_id])

        new_req = Request(env)
        res = new_req.get_response(self.app)
        if res.status_int == 200:
            image = json.loads(res.body).get('image')
            if image:
                body = {}
                body['id'] = '/'.join([self.tenant_id, self.entity_uri,
                                       self.image_id])
                match_up(body, image, 'name', 'name')
                match_up(body, image, 'created', 'created')
                match_up(body, image, 'updated', 'updated')
                match_up(body, image, 'state', 'status')
                image_map_status(body, 'state')
                body['imageLocation'] = body['id']

            if self.res_content_type == 'application/xml':
                response_data = {self.entity_uri: body}
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

        return res


class MachineImageColCtrler(Controller):
    """
    Handles machine image collection request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(MachineImageColCtrler, self).__init__(conf, app, req, tenant_id,
                                                    *args)
        self.os_path = '/%s/images' % (tenant_id)
        self.entity_uri = 'MachineImageCollection'
        self.metadata = Consts.MACHINEIMAGE_COL_METADATA

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
            body['id'] = '/'.join([self.tenant_id, self.entity_uri])
            body['machineImages'] = []
            images = content.get('images', [])
            for image in images:
                entry = {}
                entry['resourceURI'] = '/'.join([self.uri_prefix,
                                                 'MachineImage'])
                entry['id'] = '/'.join([self.tenant_id,
                                     'MachineImage',
                                     image['id']])

                body['machineImages'].append(entry)

            body['count'] = len(body['machineImages'])
            if self.res_content_type == 'application/xml':
                remove_member(body, 'resourceURI')
                body['resourceURI'] = '/'.join([self.uri_prefix,
                                                self.entity_uri])
                response_data = {'Collection': body}
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
