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

from test_utils import get_config
from lxml import etree
import unittest
import json

from nova.tests.integrated.api.client import TestOpenStackClient

class CIMITestCase(unittest.TestCase):

    def setUp(self):
        try:
            config = get_config()
            
            self.client = TestOpenStackClient(config.get('os_username'),
                                              config.get('os_password'),
                                              config.get('auth_url'))
            self.client.tenant_name = config.get('os_tenant_name')
            self._authenticate()

            self.ns = 'http://schemas.dmtf.org/cimi/1'
            self.nsmap = {'ns':self.ns}
            self.host = config.get('api_url')
            self.vol_host = config.get('vol_api_url')
            self.baseURI = self.host + '/cimiv1'
            self.image_id = self._prepare_id('images')
            self.flavor_id = self._prepare_id('flavors')
            self.volume_id = self._prepare_id('volumes')
            if not self.volume_id:
                self._create_volume()
            self.server_id = self._prepare_id('servers')
            if not self.server_id:
                self._create_machine()
                #self.server_id = self._prepare_id('servers')
        except Exception as login_error:
            raise login_error

    def tearDown(self):
        pass

    def _authenticate(self):
        ''' Authenticate with Nova '''

        auth_body = '''
            {
                "auth":{
                    "passwordCredentials":{
                        "username":"xxx",
                        "password":"xxx"
                    },
                    "tenantName":"xxx"
                }
            }
        '''

        # use configurable variables to replace the crednetials
        auth_body = json.loads(auth_body)
        auth_body['auth']['passwordCredentials']['username'] = \
            self.client.auth_user
        auth_body['auth']['passwordCredentials']['password'] = \
            self.client.auth_key
        auth_body['auth']['tenantName'] = self.client.tenant_name
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}

        response = self.client.request(self.client.auth_uri, method='POST',
                                  body=json.dumps(auth_body), headers=headers)

        http_status = response.status
        if http_status == 401:
            raise Exception('Login failed')

        resp_body = response.read()
        resp_data = json.loads(resp_body)
        #print 'json=', resp_data
        self.token = resp_data['access']['token']['id']
        self.tenant = resp_data['access']['token']['tenant']['id']

    def _prepare_id(self, key):
        if key == 'volumes':
            uri = '%s/v1/%s/%s' % (self.vol_host, self.tenant, key)
        else:
            uri = '%s/v2/%s/%s' % (self.host, self.tenant, key)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        if res.status == 200:
            root = json.loads(res.read())
            all_items = root.get(key, [])
            if len(all_items) > 0:
                return all_items[0].get('id')

    
    def _create_volume(self):
        body = '''
            { "resourceURI": "http://schemas.dmtf.org/cimi/1/VolumeCreate",
              "name": "init use",
              "description": "My first new volume", 
              "volumeTemplate": {
                "volumeConfig": { "capacity": 1 }
                }
            }
        '''
        uri = '%s/%s/VolumeCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [200, 201, 202], 'create volume json failed')
        res_data = json.loads(res.read())
        
        tmp = res_data.get('id').strip('/').split('/')
        self.volume_id = tmp[len(tmp)-1]
        
    def _create_machine(self):
        body = '''
        {
           "server" : {
               "name": "cimi-test-server",
               "imageRef": "/v2/%s/images/%s",
               "flavorRef": "/v2/%s/flavors/%s",
               "metadata": { "My Server Name" : "Apache2" }
           }
        }
        '''
        body_data = json.loads(body)
        server = body_data['server']
        server['imageRef'] = server['imageRef'] % (self.tenant,
                                                         self.image_id)
        server['flavorRef'] = server['flavorRef'] % (self.tenant,
                                                           self.flavor_id)
        uri = '%s/v2/%s/servers' % (self.host, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=json.dumps(body_data))
        if res.status in [201, 202]:
            res_data = json.loads(res.read())
            self.server_id = res_data.get('server').get('id')
            print ''
            print 'Machine created'

    def test_get_cloud_entry_point_xml(self):
        uri = '%s/%s/cloudentrypoint' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read cloud entry point failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element, 'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')

        els = root.xpath('/ns:CloudEntryPoint', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'Root element should be CloudEntryPoint')
        els = root.xpath('//ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should exist')
        els = root.xpath('//ns:baseURI', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'baseURI should be present')
        els = root.xpath('//ns:machineConfigs', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'machineConfigs should be present')
        els = root.xpath('//ns:machineImages', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'machineImages should be present')
        els = root.xpath('//ns:machines', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'machines should be present')

    def test_get_cloud_entry_point_json(self):
        uri = '%s/%s/cloudentrypoint' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read cloud entry point failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('resourceURI'), 'missing resourceURI')
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertIsNotNone(root.get('baseURI'), 'baseURI should be present')
        self.assertIsNotNone(root.get('machineConfigs'),
                             'machineConfigs should be present')
        self.assertIsNotNone(root.get('machineImages'),
                             'machineImages should be present')
        self.assertIsNotNone(root.get('machines'),
                             'machines should be present')

    def test_get_machine_images_xml(self):
        uri = '%s/%s/machineImageCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machineImages failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element, 'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')

        els = root.xpath('/ns:Collection', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'Root element should be Collection')
        els = root.xpath('/ns:Collection/ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')

        #test read machine image
        els = root.xpath('/ns:Collection/ns:Entry', namespaces=self.nsmap)
        if len(els) > 0:
            entry = els[0]
            els = entry.xpath('./ns:id', namespaces=self.nsmap)
            self.assertEqual(len(els), 1, 'id should be present')
            els = entry.xpath('./ns:machineImage', namespaces=self.nsmap)
            self.assertIsNotNone(els[0].get('href'),
                                 'machineImage should have href')

    def test_get_machine_image_xml(self):
        uri = '%s/%s/machineImage/%s' % (self.baseURI, self.tenant,
                                         self.image_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machineImages failed')

        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element,
                              'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')
        els = root.xpath('/ns:MachineImage', namespaces=self.nsmap)
        self.assertEqual(len(els), 1,
                         'Root element should be MachineImage')
        els = root.xpath('./ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')
        els = root.xpath('./ns:imageLocation', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'imageLocation should be present')

    def test_get_machine_images_json(self):
        uri = '%s/%s/machineImageCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machineImages failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/MachineImageCollection' % (self.ns),
                         'resourceURI is not corret')

        entries = root.get('entries', [])
        if len(entries) > 0:
            entry = entries[0]
            self.assertIsNotNone(entry.get('id'),
                                 'id should be present')
            self.assertIsNotNone(entry.get('machineImage'),
                                 'machineImage should be present')
            href = entry.get('machineImage').get('href')
            self.assertIsNotNone(href, 'href should be present')

    def test_get_machine_image_json(self):
        uri = '%s/%s/machineImage/%s' % (self.baseURI, self.tenant,
                                         self.image_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machineImage failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/MachineImage' % (self.ns),
                         'resourceURI is not corret')

    def test_get_machine_configurations_xml(self):
        uri = '%s/%s/machineConfigurationCollection' % (self.baseURI,
                                                        self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machineConfigs failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element, 'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')

        els = root.xpath('/ns:Collection', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'Root element should be Collection')
        els = root.xpath('/ns:Collection/ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')

        #test read machine conconfiguration
        els = root.xpath('/ns:Collection/ns:Entry', namespaces=self.nsmap)
        if len(els) > 0:
            entry = els[0]
            els = entry.xpath('./ns:id', namespaces=self.nsmap)
            self.assertEqual(len(els), 1, 'id should be present')
            els = entry.xpath('./ns:machineConfiguration', namespaces=self.nsmap)
            self.assertIsNotNone(els[0].get('href'),
                                 'machineConfiguration should have href')

    def test_get_machine_configuration_xml(self):
        uri = '%s/%s/machineConfiguration/%s' % (self.baseURI, self.tenant,
            self.flavor_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}

        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machineConfig failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element,
                              'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')
        els = root.xpath('/ns:MachineConfiguration', namespaces=self.nsmap)
        self.assertEqual(len(els), 1,
                         'Root element should be MachineConfiguration')
        els = root.xpath('./ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')

    def test_get_machine_configurations_json(self):
        uri = '%s/%s/machineConfigurationCollection' % (self.baseURI,
                                                        self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machineConfigs failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/MachineConfigurationCollection' % (self.ns),
                         'resourceURI is not corret')

        entries = root.get('entries', [])
        if len(entries) > 0:
            entry = entries[0]
            self.assertIsNotNone(entry.get('id'),
                                 'id should be present')
            self.assertIsNotNone(entry.get('machineConfiguration'),
                                 'machineConfiguration should be present')
            href = entry.get('machineConfiguration').get('href')
            self.assertIsNotNone(href, 'href should be present')

    def test_get_machine_configuration_json(self):
        uri = '%s/%s/machineConfiguration/%s' % (self.baseURI, self.tenant,
            self.flavor_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200,
                         'Read machineConfiguration failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/MachineConfiguration' % (self.ns),
                         'resourceURI is not corret')

    def test_get_machines_xml(self):
        uri = '%s/%s/machineCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machines failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element, 'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')

        els = root.xpath('/ns:Collection', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'Root element should be Collection')
        els = root.xpath('/ns:Collection/ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')

        #test read machine
        els = root.xpath('/ns:Collection/ns:Entry', namespaces=self.nsmap)
        if len(els) > 0:
            entry = els[0]
            els = entry.xpath('./ns:id', namespaces=self.nsmap)
            self.assertEqual(len(els), 1, 'id should be present')
            els = entry.xpath('./ns:machine', namespaces=self.nsmap)
            self.assertIsNotNone(els[0].get('href'),
                                 'machine should have href')

    def test_get_machine_xml(self):
        uri = '%s/%s/machine/%s' % (self.baseURI, self.tenant,
            self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machine failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element,
                              'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')
        els = root.xpath('/ns:Machine', namespaces=self.nsmap)
        self.assertEqual(len(els), 1,
                         'Root element should be Machine')
        els = root.xpath('./ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')

    def test_get_machines_json(self):
        uri = '%s/%s/machineCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machines failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/MachineCollection' % (self.ns),
                         'resourceURI is not corret')

        entries = root.get('entries', [])
        if len(entries) > 0:
            entry = entries[0]
            self.assertIsNotNone(entry.get('id'),
                                 'id should be present')
            self.assertIsNotNone(entry.get('machine'),
                                 'machine should be present')
            href = entry.get('machine').get('href')
            self.assertIsNotNone(href, 'href should be present')

    def test_get_machine_json(self):
        uri = '%s/%s/machine/%s' % (self.baseURI, self.tenant,
            self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}

        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200,
                         'Read machine failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/Machine' % (self.ns),
                         'resourceURI is not corret')

    def test_invalid_controller(self):
        uri = '%s/%s/xxxxx' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 501, 'Read should fail')

    def test_create_machine_xml(self):
        body = '''
            <MachineCreate xmlns="http://schemas.dmtf.org/cimi/1">
              <name>myMachineXML</name>
              <description>My very first XML machine</description>
              <machineTemplate>
                  <machineConfig href="/cimiv1/%s/machineConfiguration/%s" />
                  <machineImage href="/cimiv1/%s/machineImage/%s" />
              </machineTemplate>
            </MachineCreate>
        '''
        body = body % (self.tenant, self.flavor_id, self.tenant,
                       self.image_id)

        uri = '%s/%s/machineCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/xml',
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [201, 202], 'create machine failed')

        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element,
                              'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')
        els = root.xpath('/ns:Machine', namespaces=self.nsmap)
        self.assertEqual(len(els), 1,
                         'Root element should be Machine')
        els = root.xpath('./ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')

    def test_create_machine_json(self):
        body = '''
            { "entityURI": "http://schemas.dmtf.org/cimi/1/MachineCreate",
              "name": "myMachineJSON",
              "description": "My very first JSON machine",
              "machineTemplate": {
                  "machineConfig": { "href": "/cimiv1/%s/machineConfig/%s" },
                  "machineImage": { "href": "/cimiv1/%s/machineImage/%s" }
              }
            }
        '''
        body = body % (self.tenant, self.flavor_id, self.tenant,
                       self.image_id)

        uri = '%s/%s/machineCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [201, 202], 'create machine failed')

        res_data = json.loads(res.read())
        self.assertIsNotNone(res_data.get('id'),
                             'machine id should be present')

    def test_stop_machine_xml(self):
        body = '''
            <Action xmlns="http://schemas.dmtf.org/cimi/1">
                <action>http://schemas.dmtf.org/cimi/1/action/stop</action>
                <force>true</force>
            </Action>
        '''
        uri = '%s/%s/machine/%s' % (self.baseURI, self.tenant, self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/xml',
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [200, 202, 204], 'stop machine failed')

    def test_stop_machine_json(self):
        body = '''
            { "resourceURI": "http://schemas.dmtf.org/cimi/1/Action",
              "action": "http://schemas.dmtf.org/cimi/1/action/stop",
              "force": true
            }
        '''
        uri = '%s/%s/machine/%s' % (self.baseURI, self.tenant, self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [200, 202, 204], 'stop machine failed')

    def test_restart_machine_xml(self):
        body = '''
            <Action xmlns="http://schemas.dmtf.org/cimi/1">
                <action>http://schemas.dmtf.org/cimi/1/action/restart</action>
                <force>true</force>
            </Action>
        '''
        uri = '%s/%s/machine/%s' % (self.baseURI, self.tenant, self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/xml',
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [200, 202, 204], 'restart machine failed')

    def test_restart_machine_json(self):
        body = '''
            { "resourceURI": "http://schemas.dmtf.org/cimi/1/Action",
              "action": "http://schemas.dmtf.org/cimi/1/action/restart",
              "force": true
            }
        '''
        uri = '%s/%s/machine/%s' % (self.baseURI, self.tenant, self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [200, 202, 204], 'restart machine failed')

    def test_create_volume_json(self):
        body = '''
            { "resourceURI": "http://schemas.dmtf.org/cimi/1/VolumeCreate",
              "name": "myVolume1",
              "description": "My first new volume", 
              "volumeTemplate": {
                "volumeConfig": { "capacity": 1 }
                }
            }
        '''
        uri = '%s/%s/VolumeCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [200, 201, 202], 'create volume json failed')

    def test_create_volume_xml(self):
        """
        This use case is NG
        """
        body = '''
            <VolumeCreate xmlns="http://schemas.dmtf.org/cimi/1">
              <name>myVolume1</name>
              <description>My first new volume</description>
              <volumeTemplate>
                  <volumeConfig>
                      <capacity>1</capacity>
                  </volumeConfig>
              </volumeTemplate>
            </VolumeCreate>
        '''
        uri = '%s/%s/VolumeCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/xml',
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        print res.status
        self.assertIn(res.status, [200, 201, 202], 'create volume xml failed')
        
    def test_get_volumes_json(self):
        uri = '%s/%s/volumeCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read volumes failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/VolumeCollection' % (self.ns),
                         'resourceURI is not corret')

        entries = root.get('volumes', [])
        if len(entries) > 0:
            entry = entries[0]
            self.assertIsNotNone(entry.get('id'),
                                 'id should be present')
            
            self.assertEqual(entry.get('resourceURI'),
                            '%s/Volume' % (self.ns),
                            'resourceURI is not corret')
        return
    
    def test_get_volumes_xml(self):
        uri = '%s/%s/volumeCollection' % (self.baseURI, self.tenant)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machines failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element, 'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')

        els = root.xpath('/ns:Collection', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'Root element should be Collection')
        els = root.xpath('/ns:Collection/ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')

        #test read machine
        els = root.xpath('/ns:Collection/ns:Volume', namespaces=self.nsmap)
        if len(els) > 0:
            entry = els[0]
            els = entry.xpath('./ns:id', namespaces=self.nsmap)
            self.assertEqual(len(els), 1, 'id should be present')
            els = entry.xpath('./ns:resourceURI', namespaces=self.nsmap)
            self.assertEqual(len(els), 1, 'resourceURI should be present')
    
    def test_get_volume_json(self):
        uri = '%s/%s/volume/%s' % (self.baseURI, self.tenant,
            self.volume_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}

        res = self.client.request(uri, method='GET', headers=headers)
        print res.status
        self.assertEqual(res.status, 200,
                         'Read volume failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/Volume' % (self.ns),
                         'resourceURI is not corret')

    def test_get_volume_xml(self):
        uri = '%s/%s/volume/%s' % (self.baseURI, self.tenant,
            self.volume_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read volume xml failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element,
                              'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')
        els = root.xpath('/ns:Volume', namespaces=self.nsmap)
        self.assertEqual(len(els), 1,
                         'Root element should be Volume')
        els = root.xpath('./ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')
        
    #delete operation may be failed because the volume is creating but not available
    def test_del_volume_json(self):
        uri = '%s/%s/volume/%s' % (self.baseURI, self.tenant,
            self.volume_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}

        res = self.client.request(uri, method='DELETE', headers=headers)
        print res.status
        self.assertEqual(res.status, [200, 201, 202],
                         'delete volume json failed')

    def test_del_volume_xml(self):
        uri = '%s/%s/volume/%s' % (self.baseURI, self.tenant,
            self.volume_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}

        res = self.client.request(uri, method='DELETE', headers=headers)
        
        self.assertEqual(res.status, [200, 201, 202],
                         'delete volume xml failed')
    
    def test_attach_volume_json(self):
        body = '''
            { "resourceURI": "http://schemas.dmtf.org/cimi/1/MachineVolume",
              "initialLocation": "/dev/vdh",
              "volume": { "href": "/cimiv1/%s/volume/%s" }
            }
        '''
        
        body = body % (self.tenant, self.volume_id)
        
        uri = '%s/%s/MachineVolumeCollection/%s' % (self.baseURI, self.tenant, self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        print res.status
        self.assertIn(res.status, [200, 201, 202], 'attach volume json failed')

    def test_attach_volume_xml(self):
        body = '''
            <MachineVolume xmlns="http://schemas.dmtf.org/cimi/1">
              <initialLocation>/dev/vdi</initialLocation>
              <volume href="/cimiv1/%s/volume/%s" />
            </MachineVolume>
        '''
        body = body % (self.tenant, self.volume_id)

        uri = '%s/%s/MachineVolumeCollection/%s' % (self.baseURI, self.tenant, self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Content-Type': 'application/xml',
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='POST', headers=headers,
                                  body=body)
        self.assertIn(res.status, [201, 202], 'attach volume xml failed')

        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element,
                              'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')
        els = root.xpath('/ns:MachineVolume', namespaces=self.nsmap)
        self.assertEqual(len(els), 1,
                         'Root element should be MachineVolume')
        els = root.xpath('./ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')
    
    
    def test_get_machinevolumes_json(self):
        uri = '%s/%s/MachineVolumeCollection/%s' % (self.baseURI, self.tenant, self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machine volumes json failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/MachineVolumeCollection' % (self.ns),
                         'resourceURI is not corret')

        entries = root.get('machineVolumes', [])
        if len(entries) > 0:
            entry = entries[0]
            self.assertIsNotNone(entry.get('id'),
                                 'id should be present')
            
            self.assertEqual(entry.get('resourceURI'),
                            '%s/MachineVolume' % (self.ns),
                            'resourceURI is not corret')
        return
    
    def test_get_machinevolumes_xml(self):
        uri = '%s/%s/MachineVolumeCollection/%s' % (self.baseURI, self.tenant, self.server_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machine volumes failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element, 'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')

        els = root.xpath('/ns:Collection', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'Root element should be Collection')
        els = root.xpath('/ns:Collection/ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')

        #test read machine
        els = root.xpath('/ns:Collection/ns:MachineVolume', namespaces=self.nsmap)
        if len(els) > 0:
            entry = els[0]
            els = entry.xpath('./ns:id', namespaces=self.nsmap)
            self.assertEqual(len(els), 1, 'id should be present')
            # in xml format, I delete the resourceURI
            """
            els = entry.xpath('./ns:resourceURI', namespaces=self.nsmap)
            self.assertEqual(len(els), 1, 'resourceURI should be present')
            """
    def test_get_machinevolume_json(self):
        uri = '%s/%s/MachineVolume/%s/%s' % (self.baseURI, self.tenant, self.server_id,self.volume_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machine volume json failed')
        root = json.loads(res.read())
        self.assertIsNotNone(root.get('id'), 'id should exist')
        self.assertEqual(root.get('resourceURI'),
                         '%s/MachineVolume' % (self.ns),
                         'resourceURI is not corret')
    
    def test_get_machinevolume_xml(self):
        uri = '%s/%s/MachineVolume/%s/%s' % (self.baseURI, self.tenant,self.server_id, self.volume_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}
        res = self.client.request(uri, method='GET', headers=headers)
        self.assertEqual(res.status, 200, 'Read machine volume xml failed')
        root = etree.fromstring(res.read())
        self.assertIsInstance(root, etree._Element,
                              'returned is not a xml')
        ns = ''.join(root.nsmap.values())
        self.assertEqual(ns, self.ns, 'namespace is not correct')
        els = root.xpath('/ns:MachineVolume', namespaces=self.nsmap)
        self.assertEqual(len(els), 1,
                         'Root element should be MachineVolume')
        els = root.xpath('./ns:id', namespaces=self.nsmap)
        self.assertEqual(len(els), 1, 'id should be present')
    
    def test_detach_machinevolume_json(self):
        uri = '%s/%s/MachineVolume/%s/%s' % (self.baseURI, self.tenant,self.server_id,self.volume_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}

        res = self.client.request(uri, method='DELETE', headers=headers)
        print res.status
        self.assertEqual(res.status, 202,'delete machinevolume json failed')
    
    def test_detach_machinevolume_xml(self):
        uri = '%s/%s/MachineVolume/%s/%s' % (self.baseURI, self.tenant,self.server_id,self.volume_id)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/xml'}

        res = self.client.request(uri, method='DELETE', headers=headers)
        print res.status
        self.assertEqual(res.status, 202,'delete machinevolume xml failed')

    
suite = unittest.TestLoader().loadTestsFromTestCase(CIMITestCase)
unittest.TextTestRunner(verbosity=2).run(suite)
