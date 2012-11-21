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

from cimibase import Controller
from cimibase import make_response_data
from cimiutils import concat

LOG = logging.getLogger(__name__)


class CloudEntryPointCtrler(Controller):
    """
    Handles machine image request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(CloudEntryPointCtrler, self).__init__(conf, app, req,
                                                    tenant_id, *args)
        self.entity_uri = 'CloudEntryPoint'
        self.metadata = {'attributes': {'machineConfigs': 'href',
                                        'machineImages': 'href',
                                        'machines': 'href',
                                        'volumes': 'href',
                                        'CloudEntryPoint': 'resourceURI'},
                         'sequence': {self.entity_uri:
                                      ['id', 'name', 'description',
                                       'created', 'updated', 'property',
                                       'baseURI', 'machines','machineConfigs',
                                       'machineImages', 'volumes',
                                       'operation']}}

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET Container (List Objects) request
        """
        body = {}
        body['id'] = concat(self.tenant_id,
                            '/', self.entity_uri)
        body['name'] = self.entity_uri
        body['description'] = 'Cloud Entry Point'
        body['baseURI'] = concat(req.host_url, self.request_prefix, '/')

        body['machineConfigs'] = {'href':
                '/'.join([self.tenant_id, 'MachineConfigurationCollection'])}

        body['machines'] = {'href':
                '/'.join([self.tenant_id, 'MachineCollection'])}

        body['machineImages'] = {'href':
                '/'.join([self.tenant_id, 'MachineImageCollection'])}

        body['volumes'] = {'href':
                '/'.join([self.tenant_id, 'VolumeCollection'])}

        if self.res_content_type == 'application/xml':
            response_data = {'CloudEntryPoint': body}
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