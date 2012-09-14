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

from nova.api.openstack.wsgi import XMLDictSerializer, JSONDictSerializer

from cimibase import Controller
from cimibase import CimiXMLSerializer
from cimibase import make_response_data
from cimibase import get_request_data
from cimiutils import concat, get_err_response
from cimiutils import match_up, sub_path

LOG = logging.getLogger(__name__)


class NetworkAddressCtrler(Controller):
    """
    Handles machine request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(NetworkAddressCtrler, self).__init__(conf, app, req,
                                tenant_id, *args)
        self.os_path = '/%s/servers' % (tenant_id)
        self.entity_uri = 'MachineNetworkInterfacesAddress'
        self.machine_id = args[0] if len(args) > 0 else ''
        self.address_key = args[1] if len(args) > 1 else ''
        self.machine_ip = args[2] if len(args) > 2 else ''
        self.metadata = {'attributes': {'property': 'version'},
                         'plurals': {'properties': 'property'},
                         'sequence': {'Address':
                                      ['id', 'name', 'description',
                                       'created', 'updated', 'property',
                                       'ip', 'hostname']}}

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
            body['id'] = concat(self.tenant_id, '/',
                                self.entity_uri, '/',
                                self.machine_id, '/',
                                self.address_key, '/',
                                self.machine_ip)
            adds = {}
            match_up(adds, data, 'addr', 'addresses/'+self.address_key)
            ips = adds.get('addr')
            if ips:
                for ip in ips:
                    if self.machine_ip == ip.get('addr'):
                        body['ip'] = self.machine_ip

            if self.res_content_type == 'application/xml':
                response_data = {'Address': body}
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

class NetworkAddressColCtrler(Controller):
    """
    Handles machine collection request.
    """
    def __init__(self, conf, app, req, tenant_id, *args):
        super(NetworkAddressColCtrler, self).__init__(conf,
            app, req, tenant_id, *args)
        self.os_path = '/%s/servers' % (tenant_id)
        self.machine_id = args[0] if len(args) > 0 else ''
        self.address_key = args[1] if len(args) > 1 else ''
        self.entity_uri = 'MachineNetworkInterfacesAddressesCollection'
        self.metadata = {'attributes': {'Collection': 'resourceURI',
                                       'Entry': 'resourceURI',
                                       'addresses': 'href'},
                         'plurals': {'entries': 'Entry'},
                         'sequence': {'Collection':
                                      ['id', 'entries'],
                                      'entries':
                                      ['id', 'address']}}

    def _get_entry(self, data):

        def _make_entry(entries):
            adds = {}
            match_up(adds, data, 'addr', 'addresses/'+self.address_key)
            if adds.get('addr'):
                ips = adds.get('addr')
                for addr in ips:
                    entry = {}
                    name = 'MachineNetworkInterfacesAddressesCollectionEntry'
                    entry['id'] = concat(self.tenant_id, '/', name,
                         '/', self.machine_id, '/', self.address_key,
                                     '/', addr.get('addr'))
                    entry['resourceURI'] = concat(self.uri_prefix,
                        '/', name,)
                    name = 'MachineNetworkInterfaceAddress'
                    entry['address'] = {'href': concat(self.tenant_id,
                        '/', name, '/', self.machine_id, '/',
                        self.address_key, '/', addr.get('addr'))}
                    entries.append(entry)

        entries = []
        _make_entry(entries)
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
            body['id'] = concat(self.tenant_id, '/',
                                self.entity_uri, '/',
                                self.machine_id, '/',
                                self.address_key)
            body['resourceURI'] = concat(self.uri_prefix, self.entity_uri)
            body['entries'] = self._get_entry(data)

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
