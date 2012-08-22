# Copyright (c) 2011 IBM
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


from nova import log as logging
from webob import Request, Response
import json
import copy

from cimiapp.cimibase import Controller
from cimiapp.cimibase import CimiXMLSerializer
from cimiapp.cimibase import make_response_data
from cimiapp.cimibase import get_request_data
from cimiapp.cimiutils import concat, get_err_response
from cimiapp.cimiutils import match_up, sub_path
from nova.api.openstack.wsgi import XMLDictSerializer, JSONDictSerializer

LOG = logging.getLogger(__name__)


class NetworkInterfaceCtrler(Controller):
    """
    Handles machine request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(NetworkInterfaceCtrler, self).__init__(conf, app, req,
                                tenant_id, *args)
        self.os_path = '/%s/servers' % (tenant_id)
        self.metadata = {'attributes': {'networkInterfaces': 'resourceURI',
                                        'Entry': 'resourceURI'},
                         'plurals': {'entries': 'Entry'}}


class NetworkInterfaceColCtrler(Controller):
    """
    Handles machine collection request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(NetworkInterfaceColCtrler, self).__init__(conf,
            app, req, tenant_id, *args)
        self.os_path = '/%s/servers' % (tenant_id)
        self.entity_uri = 'MachineNetworkInterfacesCollection'
        self.metadata = {'attributes': {'Collection': 'resourceURI',
                                       'Entry': 'resourceURI',
                                       'addresses': 'href'},
                         'plurals': {'entries': 'Entry'},
                         'sequence': {self.entity_uri:
                                      ['id', 'entries'],
                                      'Entry':
                                      ['id', 'addresses']}}

    def _get_entry(self, data, id):

        def _make_entry(key, source_key, entries):
            adds = {}
            match_up(adds, data, 'addr', source_key)
            if adds.get('addr'):
                entry = {}
                name = 'MachineNetworkInterfacesCollectionEntry'
                entry['id'] = concat(self.tenant_id, '/', name,
                                     '/', id, '/', key)
                entry['resourceURI'] = concat(self.uri_prefix,
                    '/', name,)
                name = 'MachineNetworkInterfaceAddressesCollection'
                entry['addresses'] = {'href': concat(self.tenant_id,
                    '/', name, '/', id, '/', key)}
                entries.append(entry)

        entries = []
        _make_entry('private', 'addresses/private', entries)
        _make_entry('public',  'addresses/public', entries)
        return entries

    # Use GET to handle all container read related operations.
    def GET(self, req, *parts):
        """
        Handle GET machine request
        """

        env = self._fresh_env(req)
        env['PATH_INFO'] = concat(self.os_path, '/', parts[0])

        new_req = Request(env)
        res = new_req.get_response(self.app)

        if res.status_int == 200:
            data = json.loads(res.body).get('server')

            body = {}
            body['id'] = concat(self.tenant_id,
                                '/networkInterfacesCollection/',
                                parts[0])
            body['resourceURI'] = concat(self.uri_prefix, self.entity_uri)
            body['entries'] = self._get_entry(data, parts[0])

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
