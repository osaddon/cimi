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
"""
Cimi middleware.
"""

from nova.openstack.common import log as logging
from urllib import unquote
from webob import Request
from urlparse import urlparse
import json
import threading

from cimiapp.machine import (MachineCtrler,
                                      MachineColCtrler)
from cimiapp.machineimage import (MachineImageCtrler,
                                           MachineImageColCtrler)
from cimiapp.machineconfig import (MachineConfigCtrler,
                                            MachineConfigColCtrler)
from cimiapp.network import (NetworkInterfaceCtrler,
                                      NetworkInterfaceColCtrler)
from cimiapp.cloudentrypoint import CloudEntryPointCtrler
from cimiapp.address import (NetworkAddressCtrler,
                                      NetworkAddressColCtrler)
from cimiapp.volume import VolumeColCtrler, VolumeCtrler
from cimiapp.machinevolume import (MachineVolumeCtrler,
                                            MachineVolumeColCtrler)

from cimiapp.cimiutils import get_err_response

LOG = logging.getLogger(__name__)

LOCK = threading.Lock()


class CIMIMiddleware(object):
    """CIMI Middleware"""

    CONTROLLERS = {'cloudentrypoint': CloudEntryPointCtrler,
                   'machine': MachineCtrler,
                   'machinecollection': MachineColCtrler,
                   'machineconfiguration': MachineConfigCtrler,
                   'machineconfigurationcollection': MachineConfigColCtrler,
                   'machineimage': MachineImageCtrler,
                   'machineimagecollection': MachineImageColCtrler,
                   'networkinterface': NetworkInterfaceCtrler,
                   'networkinterfacescollection': NetworkInterfaceColCtrler,
                   'machinenetworkinterfaceaddress': NetworkAddressCtrler,
                   'machinenetworkinterfaceaddressescollection':
                        NetworkAddressColCtrler,
                   'volumecollection': VolumeColCtrler,
                   'volume': VolumeCtrler,
                   'machinevolume': MachineVolumeCtrler,
                   'machinevolumecollection': MachineVolumeColCtrler}

    def __init__(self, app, conf, *args, **kwargs):
        self.app = app
        self.conf = conf
        self.request_prefix = self.conf.get('request_prefix')
        self.prefix_length = len(self.request_prefix)

    def _process_config(self, service_name):
        endpoint = self.conf.get(service_name)
        if endpoint:
            parts = urlparse(endpoint)
            self.conf.setdefault(service_name + '_host', parts.hostname)
            self.conf.setdefault(service_name + '_port', parts.port)
            self.conf.setdefault(service_name + '_scheme', parts.scheme)

    def _process_config_header(self, env):
        """
        this method get the catalog endpoints from the header if keystone
        is used.
        """
        if not self.conf.get('CONFIG_DONE'):
            LOG.info('processing header')
            # critical section, acquire a lock
            if LOCK.acquire():
                self.conf.setdefault('CONFIG_DONE', True)
                catalog_str = env.get('HTTP_X_SERVICE_CATALOG')
                if catalog_str:
                    catalogs = json.loads(catalog_str)
                    for catalog in catalogs:
                        name = catalog['type'] + '_endpoint'
                        if not self.conf.get(name):
                            uri = catalog['endpoints'][0]['publicURL']
                            self.conf.setdefault(name, uri)

                self._process_config('volume_endpoint')
                self._process_config('compute_endpoint')
                LOCK.release()

    def get_controller(self, path):
        """Get the request controller according to the request path

        this method returns a response, a controller and tenant id and parsed
        list of path.
        if the path starts with cimiv1, then this is CIMI request, the next
        segment in the path should indicate the controller. if the controller
        does not exist, then the response will indicate the error. if the
        controller is found, then the response will be None.
        if the path does not start with cimiv1, then this is not CIMI request,
        the controller and response will be none. the request should be
        forwarded to the next filter in the pipeline.

        """

        parts = path.strip('/').split('/')

        # each request should have /cimiv1/tenant_id/controller_key
        # in its url pattern.
        if len(parts) >= 2:
            controller_key = parts[1].lower()
            controller = self.CONTROLLERS.get(controller_key)
            return None, controller, parts[0], parts[2:]
        else:
            resp = get_err_response('BadRequest')
            return resp, None, None, None

    def __call__(self, env, start_response):

        LOG.info(env)
        if env.get('SCRIPT_NAME', '').startswith(self.request_prefix):
            self._process_config_header(env)
            path = unquote(env.get('PATH_INFO', ''))
            response, controller, tenant_id, parts = self.get_controller(path)

            if response:
                return response(env, start_response)
            elif controller:
                req = Request(env)
                ctrler = controller(self.conf, self.app, req,
                                    tenant_id, *parts)
                method = env.get('REQUEST_METHOD').upper()
                if hasattr(ctrler, method) and not method.startswith('_'):
                    res = getattr(ctrler, method)(req, *parts)
                    return res(env, start_response)
                else:
                    res = get_err_response('NotImplemented')
                    return res(env, start_response)
            else:
                res = get_err_response('NotImplemented')
                return res(env, start_response)
        else:
            return self.app(env, start_response)
