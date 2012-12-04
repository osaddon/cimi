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
from cimiutils import match_up, sub_path
from cimiutils import remove_member
from nova.api.openstack.wsgi import XMLDictSerializer, JSONDictSerializer

LOG = logging.getLogger(__name__)


class MachineVolumeCtrler(Controller):
    """
    Handles machineVolume request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(MachineVolumeCtrler, self).__init__(conf, app, req, tenant_id,
                                            *args)
        self.os_path = '/%s/servers' % (tenant_id)
        self.entity_uri = 'MachineVolume'

        self.metadata = Consts.MACHINEVOLUME_METADATA

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET Container (List Objects) request
        """

        env = self._fresh_env(req)
        env['PATH_INFO'] = concat(self.os_path, '/',
                                  parts[0], '/os-volume_attachments/',
                                  parts[1])
        new_req = Request(env)
        res = new_req.get_response(self.app)

        if res.status_int == 200:
            data = json.loads(res.body).get('volumeAttachment')

            body = {}
            body['id'] = concat(self.tenant_id, '/MachineVolume/',
                                data['serverId'], '/', data['id'])
            match_up(body, data, 'initialLocation', 'device')

            body['volume'] = {'href': concat(self.tenant_id,
                    '/Volume/', data['volumeId'])}

            # deal with machinevolume operations
            operations = []
            operations.append(self._create_op('edit', body['id']))
            operations.append(self._create_op('delete', body['id']))
            body['operations'] = operations

            if self.res_content_type == 'application/xml':
                response_data = {'MachineVolume': body}
            else:
                body['resourceURI'] = concat(self.uri_prefix, '/',
                                      self.entity_uri)
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

    def DELETE(self, req, *parts):
        """
        handle volume detach operation
        """
        #parts is /server_id/attach_id

        if len(parts) < 2:
            return get_err_response('BadRequest')

        env = self._fresh_env(req)
        env['PATH_INFO'] = concat(self.os_path, '/', parts[0],
                                  '/os-volume_attachments/', parts[1])
        env['CONTENT_TYPE'] = 'application/json'
        new_req = Request(env)
        res = new_req.get_response(self.app)

        return res


class MachineVolumeColCtrler(Controller):
    """
    Handles machineVolume collection request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(MachineVolumeColCtrler, self).__init__(conf, app, req, tenant_id,
                                                     *args)
        self.os_path = '/%s/servers' % (tenant_id)
        self.entity_uri = 'MachineVolumeCollection'

        self.metadata = Consts.MACHINEVOLUME_COL_METADATA
        self.machine_volume_metadata = Consts.MACHINEVOLUME_METADATA

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET machineVolumeCollection request
        """

        env = self._fresh_env(req)

        env['PATH_INFO'] = concat(self.os_path, '/',
                                  parts[0], '/os-volume_attachments')
        new_req = Request(env)
        res = new_req.get_response(self.app)

        if res.status_int == 200:
            content = json.loads(res.body)
            body = {}
            body['id'] = concat(self.tenant_id,
                                '/', self.entity_uri, '/', parts[0])
            body['resourceURI'] = concat(self.uri_prefix, '/',
                                            self.entity_uri)

            body['machineVolumes'] = []
            volumeAttachments = content.get('volumeAttachments', [])
            for data in volumeAttachments:
                entry = {}
                if self.res_content_type == 'application/json':
                    entry['resourceURI'] = concat(self.uri_prefix,
                                            '/MachineVolume')
                entry['id'] = concat(self.tenant_id, '/',
                                     'machineVolume/',
                                     data['serverId'], '/',
                                     data['id'])
                entry['initialLocation'] = data['device']
                entry['volume'] = {'href': concat(self.tenant_id,
                    '/Volume/', data['volumeId'])}

                operations = []
                operations.append(self._create_op('edit', entry['id']))
                operations.append(self._create_op('delete', entry['id']))
                entry['operations'] = operations

                body['machineVolumes'].append(entry)

            body['count'] = len(body['machineVolumes'])
            # deal with machinevolume operations
            operations = []
            operations.append(self._create_op('add', body['id']))
            body['operations'] = operations

            if self.res_content_type == 'application/xml':
                response_data = {'Collection': body}
                remove_member(response_data, 'resourceURI')
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

    # Use POST to handle all container read related operations.
    def POST(self, req, *parts):
        """
        Handle POST machineVolumeCollection request which will attach an volume
        """
        try:
            request_data = get_request_data(req.body, self.req_content_type)
        except Exception as error:
            return get_err_response('MalformedBody')

        if request_data:
            data = request_data.get('body').get('MachineVolume')
            if not data:
                data = request_data.get('body')
            if data:

                volume_url = data.get('volume', {}).get('href')
                if volume_url:
                    volume_id = volume_url.strip('/').split('/')[-1]
                else:
                    return get_err_response('MalformedBody')

                device = data.get('initialLocation')
                if not device:
                    return get_err_response('MalformedBody')

                reqdata = {}
                reqdata['volumeAttachment'] = {'volumeId': volume_id,
                                            'device': device}
                env = self._fresh_env(req)
                env['PATH_INFO'] = concat(self.os_path, '/', parts[0],
                                          '/os-volume_attachments')
                env['CONTENT_TYPE'] = 'application/json'
                new_req = Request(env)
                new_req.body = json.dumps(reqdata)
                res = new_req.get_response(self.app)
                if res.status_int == 200:
                    data = json.loads(res.body).get('volumeAttachment')
                    attach_id = data.get('id')
                    server_id = data.get('serverId')
                    volume_id = data.get('volumeId')

                    body = {}
                    match_up(body, data, 'initialLocation', 'device')

                    body['id'] = concat(self.tenant_id, '/machinevolume/',
                                        server_id, '/', attach_id)

                    body['volume'] = {'href': concat(self.tenant_id,
                                                    '/volume/', volume_id)}

                    # deal with volume attach operations
                    operations = []
                    operations.append(self._create_op('edit', body['id']))

                    operations.append(self._create_op('delete', body['id']))
                    body['operations'] = operations

                    if self.res_content_type == 'application/xml':
                        response_data = {'MachineVolume': body}
                    else:
                        body['resourceURI'] = concat(self.uri_prefix,
                                                    '/MachineVolume')
                        response_data = body

                    new_content = make_response_data(response_data,
                                                 self.res_content_type,
                                                 self.machine_volume_metadata,
                                                 self.uri_prefix)
                    resp = Response()
                    self._fixup_cimi_header(resp)
                    resp.headers['Content-Type'] = self.res_content_type
                    resp.headers['Location'] = \
                        '/'.join([self.request_prefix, body['id']])
                    resp.status = 201
                    resp.body = new_content
                    return resp
                else:
                    return res

            else:
                return get_err_response('BadRequest')
        else:
            return get_err_response('BadRequest')
