
      Copyright 2010-2011 United States Government as represented by the
      Administrator of the National Aeronautics and Space Administration. 
      All Rights Reserved.

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

=================================
CIMI REST Implementation On Nova
=================================

----------------
Design decisions
----------------

The CIMI implementation on OpenStack Nova was designed to be a filter so that
the implementation can be easily configured to run like any other modules in
Nova pipeline. It can also take advantages of Nova authentication filter so
that the CIMI implementation modules can be completely independent from other
modules. When not needed, changing Nova configuration to disable it.

The implementation includes total of 10 modules. Nine modules are the
implementations and one module contains the test cases. The first module is
named cimi.py which serves as a bootstrap or SWGI server. This module should be
placed in nova/api directory. This module also defines the
filter_factory method which is to make the entire module an OpenStack filter.
It also inspect each request and dispatch the request to other modules which
various controllers were defined. Other than the first module, other
implementation modules can be found in nova/api/cimiapp directory. Module
cimibase.py is created as a base controller class for other controllers to
extend so that the some common handlings can be implemented once and shared
between all controllers. Module cimiutils.py defines utility methods for
controllers. Module cloudentrypoint.py is to handle CIMI cloud entry point
request. machine.py is to handle all machine and machine collection requests.
machineconfig.py is to handle all machine configuration collection and machine
configuration request. machineimage.py is to handle machine image and
machine image collection requests. network.py and address.py are the modules to
handle machine network related requests.

Test case module is located in nova/tests/api/cimi directory. It is named
test_cimi.py.

-----------------------------------------------
Install onto an existing OpenStack Nova server
-----------------------------------------------

Please follow the following steps to configure CIMI filter on an Nova
installation.

    1. In etc/nova directory, change file api-paste.ini, add cimi filter,
       notice the word cimi before osapi_compute_app_v2 and also add the
       filter definition as demostrated below.

        [composite:openstack_compute_api_v2]
        use = call:nova.api.auth:pipeline_factory
        noauth = faultwrap ... cimi osapi_compute_app_v2
        deprecated = faultwrap ... cimi osapi_compute_app_v2
        keystone = faultwrap ... cimi osapi_compute_app_v2
        keystone_nolimit = faultwrap ... cimi osapi_compute_app_v2


        [filter:cimi]
        paste.filter_factory = nova.api.cimi:filter_factory
        request_prefix = /cimiv1
        os_version = /v2


    2. If cimi implementation is not part of the OpenStack Nova distribution,
       manually unzip the cimi implementation into nova installation directory.
       Once this step is done, there should be file structures like
       the following:
            nova/api/cimi.py
            nova/api/cimiapp/__init__.py
            nova/api/cimiapp/address.py
            nova/api/cimiapp/cimibase.py
            nova/api/cimiapp/cimiutils.py
            nova/api/cimiapp/cloudentrypoint.py
            nova/api/cimiapp/machine.py
            nova/api/cimiapp/machineconfig.py
            nova/api/cimiapp/machineimage.py
            nova/api/cimiapp/network.py
            nova/tests/api/cimi/test_cimi.py
            doc/source/cimi.rst (this file)

    3. Once the above two steps are done, restart Nova.

------------------------------
How to use this implementation
------------------------------

The following steps assume that you are using devstack.
If your installation is something other than devstack, the user id and password
used in the following example may differ but the steps should remain the same.

Once it is installed and configured, a client can use the CIMI API
by following the steps below.

    1. Use http://hostname:port/v2/token to login, the host name and port should
       be the same host name and port number Nova uses, normally it should be
       5000 in a devstack environment. The login should be a POST
       request with header like the following:

        POST http://example.com:5000/v2.0/tokens HTTP/1.1
        User-Agent: Fiddler
        Host: example.com:5000
        Content-Type: application/json
        Accept: application/xml
        Content-Length: 165
        
        {
            "auth":{
                "passwordCredentials":{
                    "username":"admin",
                    "password":"admin"
                },
                "tenantName":"admin"
            }
        }

    2. Once you logged in, you should get something like the following in the
       response header.

        HTTP/1.1 200 OK
        Content-Type: application/json
        Vary: X-Auth-Token
        Content-Length: 2175
        Date: Tue, 29 May 2012 20:47:22 GMT
        
        {"access": 
            {"token": 
                {"expires": "2012-05-30T20:47:22Z",
                 "id": "31c320be59654ccfa2d551191c3c483a",
                 "tenant": {"enabled": true,
                    "id": "4090a642f50f4bf49b6cb88575e9db97",
                    "name": "admin",
                    "description": null}},
                    ...
                 }
             }
        }

    3. Use the token id as the X-Auth-Token and tenant id for all following
       requests.

    4. Retrieve the cloud entry point by issuing a GET request:

        GET http://host:port/cimiv1/<tenant_id>/cloudentrypoint


        Assume you have a tenant id being
        1234
        
        Token id being:
        4567

        your request may look like this
        GET http://example.com:8774/cimiv1/1234/cloudentrypoint HTTP/1.1
        User-Agent: Fiddler
        X-Auth-Token: 4567
        Host: example.com:8774
        Accept: application/xml
        Content-Length: 0

        The response may look like this

        HTTP/1.1 200 OK
        Cimi-Specification-Version: 1.0.0
        Content-Type: application/xml
        Content-Length: 587
        Date: Tue, 29 May 2012 18:13:54 GMT
        
        <?xml version="1.0" encoding="UTF-8"?>
        <CloudEntryPoint xmlns="http://schemas.dmtf.org/cimi/1/">
          <id>
            1234/CloudEntryPoint
          </id>
          <name>
            CloudEntryPoint
          </name>
          <description>
            Cloud Entry Point
          </description>
          <baseURI>
            http://192.168.56.101:8774/cimiv1/
          </baseURI>
          <machineConfigs href="1234/MachineConfigurationCollection"/>
          <machineImages href="1234/MachineImageCollection"/>
          <machines href="1234/MachineCollection"/>
        </CloudEntryPoint>

    4. After you get the URLs from cloud entry point response, you can simply
       issue various http requests to get and manipulate your cloud artifacts
       by following the CIMI specification

    5. Detailed request and response examples can be found in file
       cimi_request_response.pdf which is located in the same directory
       as this file.

--------------
Run Test Cases
--------------

CIMI test cases were developed as functional tests, it will access a running
Nova system with CIMI filter enabled. Before you run the test cases, make
sure CIMI filter configuration is correct by checking the file at
etc/nova/api-paste.ini.

Once OpenStack Nova is up running, switch to the following directory

    <NovaInstallDir>/tests/api/cimi directory

Run the following command.

    python test_cimi.py
