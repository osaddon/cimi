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


from xml.dom import minidom
from webob import Request
from nova.openstack.common import log as logging
from nova.api.openstack.wsgi import XMLDictSerializer, JSONDictSerializer
from nova.api.openstack.wsgi import XMLDeserializer, JSONDeserializer
from cimiutils import best_match
import copy
import json

LOG = logging.getLogger(__name__)


class CimiJSONDictSerializer(JSONDictSerializer):
    """Default JSON request body serialization"""

    def default(self, data):
        return json.dumps(data, indent=2)


class CimiXMLSerializer(XMLDictSerializer):

    def default(self, data):
        # We expect data to contain a single key which is the XML root.
        root_key = data.keys()[0]
        doc = minidom.Document()
        node = self._to_xml_node(doc, self.metadata, root_key,
                                 data[root_key], None)

        header = '<?xml version="1.0" encoding="UTF-8"?>\n'
        return header + self.to_xml_string(node)

    def to_xml_string(self, node, has_atom=False):
        self._add_xmlns(node, has_atom)
        return node.toprettyxml(indent='  ')
        #return node.toxml('UTF-8')

    def _to_xml_node(self, doc, metadata, nodename, data, parentnode=None):
        """Recursive method to convert data members to XML nodes."""

        if isinstance(data, list):
            collections = metadata.get('list_collections', {})
            singular = metadata.get('plurals', {}).get(nodename, None)
            if singular is None:
                if nodename.endswith('s'):
                    singular = nodename[:-1]
                else:
                    singular = 'item'
            for item in data:
                node = self._to_xml_node(doc, metadata, singular,
                                         item, parentnode)
                #result.appendChild(node)
                if parentnode:
                    parentnode.appendChild(node)
            result = None
        elif isinstance(data, dict):
            result = doc.createElement(nodename)

            if self.xmlns and parentnode is None:
                result.setAttribute('xmlns', self.xmlns)

            attrs = metadata.get('attributes', {}).get(nodename, {})
            sequence = metadata.get('sequence', []).get(nodename, {})

            # Deal with the specified elements
            for k in sequence:

                if k in data:
                    v = data.get(k)
                    if k in attrs:
                        result.setAttribute(k, str(v))
                    else:
                        node = self._to_xml_node(doc, metadata, k, v, result)
                        if node:
                            result.appendChild(node)
                    data.pop(k)

            # Process the items still left
            for k, v in data.items():
                if k in attrs:
                    result.setAttribute(k, str(v))
                else:
                    node = self._to_xml_node(doc, metadata, k, v, result)
                    if node:
                        result.appendChild(node)
        else:
            # Type is atom
            result = doc.createElement(nodename)

            if self.xmlns and parentnode is None:
                result.setAttribute('xmlns', self.xmlns)

            node = doc.createTextNode(str(data))
            result.appendChild(node)
        return result


def make_response_data(data, content_type, metadata, namespace):
    """
    Use xml serializer and json serializer to create response body
    """
    xml_serializer = CimiXMLSerializer(metadata, namespace)
    serializer = {'application/xml': xml_serializer,
                  'application/json': CimiJSONDictSerializer()
                 }.get(content_type, None)
    if serializer:
        return serializer.serialize(data)
    else:
        return ''


def get_request_data(data, content_type):
    """
    Use openstack json and xml deserializer to parse request body and
    return a python object.
    """

    deserializer = {'application/xml': XMLDeserializer(),
                    'application/json': JSONDeserializer()
                   }.get(content_type)
    if deserializer:
        return deserializer.default(data)
    else:
        return None


# Define a constant class which only hold all the strings
class Consts(object):
    REQUEST_PREFIX = '/cimiv1'
    REQUEST_PREFIX_LENGTH = len(REQUEST_PREFIX)
    RESPONSE_VERSION_KEY = 'CIMI-Specification-Version'
    RESPONSE_VERSION_VALUE = '1.0.0'
    CIMI_NS = 'http://schemas.dmtf.org/cimi/1'
    VOLUME_COL_METADATA = {'attributes':
        {'Collection': 'resourceURI', 'Entry': 'resourceURI',
         'volume': 'href'},
        'plurals': {'volumes': 'Volume'},
        'sequence': {'Collection': ['id', 'count', 'volumes', 'operation']}}

    VOLUME_METADATA = {'attributes':
        {'property': 'key', 'volumes': 'href',
         'images': 'href', 'meters': 'href',
         'Entry': 'resourceURI', 'operation': ['rel', 'href']},
        'plurals': {'entries': 'Entry'},
        'sequence': {'Volume': ['id', 'name', 'description',
                                'created', 'updated', 'property',
                                'state', 'type', 'capacity',
                                'bootable', 'images', 'meters',
                                'eventLog', 'operations']}}
    ADDRESS_METADATA = {'attributes': {'property': 'version'},
                         'plurals': {'properties': 'property'},
                         'sequence': {'Address':
                                      ['id', 'name', 'description',
                                       'created', 'updated', 'property',
                                       'ip', 'hostname']}}
    ADDRESS_COL_METADATA = {'attributes': {'Collection': 'resourceURI',
                                       'Entry': 'resourceURI',
                                       'addresses': 'href'},
                         'plurals': {'entries': 'Entry'},
                         'sequence': {'Collection':
                                      ['id', 'entries'],
                                      'entries':
                                      ['id', 'address']}}
    CLOUDENTRYPOINT_METADATA = {'attributes': {'machineConfigs': 'href',
                                        'machineImages': 'href',
                                        'machines': 'href',
                                        'volumes': 'href',
                                        'CloudEntryPoint': 'resourceURI'},
                         'sequence': {'CloudEntryPoint':
                                      ['id', 'name', 'description',
                                       'created', 'updated', 'property',
                                       'baseURI', 'machines', 'machineConfigs',
                                       'machineImages', 'volumes',
                                       'operation']}}
    MACHINE_METADATA = {'attributes': {'property': 'key',
                                        'volumes': 'href',
                                        'disks': 'href',
                                        'networkInterfaces': 'href',
                                        'Entry': 'resourceURI',
                                        'operation': ['rel', 'href']},
                         'plurals': {'entries': 'Entry'},
                         'sequence': {'Machine':
                                      ['id', 'name', 'description',
                                       'created', 'updated', 'property',
                                       'state', 'cpu', 'memory', 'disks',
                                       'networkInterfaces', 'credentials',
                                       'operations']}}
    MACHINE_COL_METADATA = {'attributes': {'Collection': 'resourceURI',
                                       'Entry': 'resourceURI',
                                       'machine': 'href',
                                       'operation': ['rel', 'href']},
                         'plurals': {'machines': 'Machine',
                                     'operations': 'operation'},
                         'sequence': {'Collection':
                                      ['id', 'count', 'machines',
                                       'operation']}}
    MACHINECONFIG_METADATA = {'attributes': {},
                         'plurals': {'disks': 'disk'},
                         'sequence': {'MachineConfiguration':
                                      ['id', 'name', 'description', 'created',
                                       'updated', 'property', 'cpu', 'memory',
                                       'disks', 'operation'],
                                      'disk': ['capacity']}}
    MACHINECONFIG_COL_METADATA = {'attributes': {'Collection': 'resourceURI',
                                       'Entry': 'resourceURI',
                                       'machineConfiguration': 'href'},
                         'plurals': {'machineConfigurations':
                                     'MachineConfiguration'},
                         'sequence': {'Collection':
                                      ['id', 'count',
                                       'machineConfigurations']}}

    MACHINEIMAGE_METADATA = {'attributes': {'property': ['minRam', 'minDisk']},
                         'plurals': {'properties': 'property'},
                         'sequence': {'MachineImage':
                                      ['id', 'name', 'description',
                                       'created', 'updated', 'property',
                                       'state', 'type', 'imageLocation',
                                       'operations']}}
    MACHINEIMAGE_COL_METADATA = {'attributes': {'Collection': 'resourceURI',
                                       'Entry': 'resourceURI',
                                       'machineImage': 'href'},
                         'plurals': {'machineImages': 'MachineImage'},
                         'sequence': {'Collection':
                                      ['id', 'count', 'machineImages']}}

    MACHINEVOLUME_METADATA = {'attributes': {'volume': 'href',
                                        'operation': ['rel', 'href']},
                         'plurals': {},
                         'sequence': {'MachineVolume': ['id', 'name',
                                       'description', 'created', 'updated',
                                       'property', 'initialLocation',
                                       'volume' 'operation']}}

    MACHINEVOLUME_COL_METADATA = {'attributes': {'Collection': 'resourceURI',
                                        'volume': 'href',
                                        'operation': ['rel', 'href']},
                         'plurals': {'machineVolumes': 'MachineVolume',
                                     'operations': 'operation'},
                         'sequence': {'Collection':
                                      ['id', 'count', 'machineVolumes',
                                       'operation']}}

    NETWORK_METADATA = {'attributes': {'networkInterfaces': 'resourceURI',
                                        'Entry': 'resourceURI'},
                         'plurals': {'entries': 'Entry'}}

    NETWORK_COL_METADATA = {'attributes': {'Collection': 'resourceURI',
                                       'Entry': 'resourceURI',
                                       'addresses': 'href'},
                         'plurals': {'entries': 'Entry'},
                         'sequence': {'MachineNetworkInterfacesCollection':
                                      ['id', 'entries'],
                                      'Entry':
                                      ['id', 'addresses']}}

    MACHINE_ACTIONS = [CIMI_NS + '/action/start',
                       CIMI_NS + '/action/restart',
                       CIMI_NS + '/action/pause',
                       CIMI_NS + '/action/stop',
                       CIMI_NS + '/action/suspend']

    # use the OS machine status and the cimi action to make a key, then
    # the value will be the action used to be sent to Nova.
    MACHINE_ACTION_MAPS = {'paused_start': 'unpause',
                           'paused_restart': 'unpause',
                           'suspended_start': 'resume',
                           'suspended_restart': 'resume',
                           'shutoff_start': 'os-start',
                           'shutoff_restart': 'os-start',
                           'active_restart': 'reboot',
                           'active_pause': 'pause',
                           'active_suspend': 'suspend',
                           'active_stop': 'os-stop',
                           'active_delete': 'delete'}


class Controller(object):
    def __init__(self, conf, app, req, tenant_id, *args):
        self.conf = conf
        self.app = app
        self.tenant_id = tenant_id
        self.request_prefix = self.conf.get('request_prefix')
        self.os_version = self.conf.get('os_version')
        self.uri_prefix = Consts.CIMI_NS
        self.res_content_type = best_match(req.environ.get('HTTP_ACCEPT', ''))
        self.req_content_type = best_match(req.environ.get('CONTENT_TYPE', ''))

    def _create_op(self, name, href):
        entry = {}
        entry['rel'] = name
        entry['href'] = href
        return entry

    def _fresh_request(self, req):
        env = copy.copy(req.environ)

        env['SCRIPT_NAME'] = self.os_version
        env['PATH_INFO'] = self.os_path
        # we will always use json format to get Nova information
        env['HTTP_ACCEPT'] = 'application/json'
        env['CONTENT_TYPE'] = 'application/json'

        # need to remove this header, otherwise, it will always take the
        # original request accept content type
        if env.has_key('nova.best_content_type'):
            env.pop('nova.best_content_type')
        new_req = Request(env)
        return new_req

    def _fresh_env(self, req):
        env = copy.copy(req.environ)

        env['SCRIPT_NAME'] = self.os_version
        env['PATH_INFO'] = self.os_path
        # we will always use json format to get Nova information
        env['HTTP_ACCEPT'] = 'application/json'

        # need to remove this header, otherwise, it will always take the
        # original request accept content type
        if env.has_key('nova.best_content_type'):
            env.pop('nova.best_content_type')
        return env

    def _fixup_cimi_header(self, res):
        if res:
            res.headers['CIMI-Specification-Version'] = '1.0.0'