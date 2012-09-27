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
from cimiapp.volume import VolumeColCtrler

from cimiapp.cimiutils import get_err_response

LOG = logging.getLogger(__name__)


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
                    'volumecollection': VolumeColCtrler}

    def __init__(self, app, conf, *args, **kwargs):
        self.app = app
        self.conf = conf
        self.request_prefix = self.conf.get('request_prefix')
        self.prefix_length = len(self.request_prefix)

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
        LOG.info('the env')
        LOG.info(env)
        if env.get('SCRIPT_NAME', '').startswith(self.request_prefix):
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
