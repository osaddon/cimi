# Copyright 2011 Cloudscaling, Inc.
# Author: Matthew Hooker <matt@cloudscaling.com>
# All Rights Reserved.
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

from lxml import etree
import unittest
import json

from nova.tests.integrated.api.client import TestOpenStackClient

class CIMITestCase(unittest.TestCase):

    def setUp(self):
        try:
            self.client = TestOpenStackClient('admin', 'ps',
                                         'http://localhost:5000/v2.0/tokens')
            self.client.project_id = 'admin'
            self.client.tenant_name = 'admin'
            self._authenticate()

            self.ns = 'http://schemas.dmtf.org/cimi/1/'
            self.nsmap = {'ns':self.ns}
            self.host = 'http://localhost:8774'
            self.baseURI = 'http://localhost:8774/cimiv1'
            self.image_id = self._prepare_id('images')
            self.flavor_id = self._prepare_id('flavors')
            self.server_id = self._prepare_id('servers')
            if not self.server_id:
                self._create_machine()
                #self.server_id = self._prepare_id('servers')
        except Exception as login_error:
            raise login_error

    def tearDown(self):
        pass

    def _authenticate(self):
        '''
        Authenticate with Nova
        '''

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
        uri = '%s/v2/%s/%s' % (self.host, self.tenant, key)
        headers = {'X-Auth-Token': self.token,
                   'Accept': 'application/json'}
        res = self.client.request(uri, method='GET', headers=headers)
        if res.status == 200:
            root = json.loads(res.read())
            all_items = root.get(key, [])
            if len(all_items) > 0:
                return all_items[0].get('id')

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
            print 'Mahcine created'

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
                         '%sMachineImageCollection' % (self.ns),
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
                         '%sMachineImage' % (self.ns),
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
                         '%sMachineConfigurationCollection' % (self.ns),
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
                         '%sMachineConfiguration' % (self.ns),
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
                         '%sMachineCollection' % (self.ns),
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
                         '%sMachine' % (self.ns),
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
                  <machineConfig href="/cimiv1/%s/machineConfig/%s" />
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
        self.assertIn(res.status, [200, 202, 204], 'stop machine failed')

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
        self.assertIn(res.status, [200, 202, 204], 'stop machine failed')


suite = unittest.TestLoader().loadTestsFromTestCase(CIMITestCase)
unittest.TextTestRunner(verbosity=2).run(suite)
