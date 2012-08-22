CDMI for OpenStack's Swift
--------------------------

A Python egg that adds support for the [CIMI protocol] to OpenStack Nova.

Setup
=====

1. Install [Openstack with Swift](http://docs.openstack.org/essex/openstack-object-storage/admin/content/)
2. Grab the code from github:
     `git clone http://github.com/osaddon/cimi`
3. Install this python egg: `sudo python setup.py install`
4. Configure Nova:

In `/etc/nova/api-paste.ini`, add cimi filter before osapi_compute_app_v2

    [composite:openstack_compute_api_v2]
    use = call:nova.api.auth:pipeline_factory
    noauth = faultwrap sizelimit noauth ratelimit cimi osapi_compute_app_v2
    deprecated = faultwrap sizelimit auth ratelimit cimi osapi_compute_app_v2
    keystone = faultwrap sizelimit authtoken keystonecontext ratelimit cimi osapi_compute_app_v2
    keystone_nolimit = faultwrap sizelimit authtoken keystonecontext cimi osapi_compute_app_v2

And add the following section to the file:

    [filter:cimi]
    use = egg:cimiapi#cimiapp
    request_prefix = /cimiv1
    os_version = /v2

Running tests
=============

First copy a test config file to /etc/swift:

	cp /opt/stack/swift/test/sample.conf /etc/swift/test.conf

Now the test cases in the test directory can be run using `python <name_of_test.py>` in the tests directory.

Development with devstack
=========================

Please make sure `swift` is enabled in your devstack environment file `localrc`.

Some sample curl commands
=========================

Authenticate:

    curl -v -H 'X-Storage-User: test:tester' -H 'X-Storage-Pass: testing' http://127.0.0.1:8080/auth/v1.0

Use the Authentication token and URL which is in the response from the last curl command to perform an *GET* operation:

    curl -v -X GET -H 'X-Auth-Token: AUTH_tk56b01c82710b41328db7c9f953d3933d' http://127.0.0.1:8080/v1/AUTH_test

Create a Container:

    curl -v -X PUT -H 'X-Auth-Token: AUTH_tk56b01c82710b41328db7c9f953d3933d' -H 'Content-tType: application/directory'-H 'Content-Length: 0' http://127.0.0.1:8080/v1/AUTH_test/<container_name>

Query the capabilites of a Container:

    curl -v -X GET -H 'X-Auth-Token: AUTH_tk56b01c82710b41328db7c9f953d3933d' -H 'X-CDMI-Specification-Version: 1.0.1' http://127.0.0.1:8080/cdmi/cdmi_capabilities/AUTH_test/<container_name>

Add an Object to a Container:

    curl -v -X PUT -H 'X-Auth-Token: AUTH_tk56b01c82710b41328db7c9f953d3933d' -H 'X-CDMI-Specification-Version: 1.0.1' -H 'Accept: application/cdmi-object' -H 'Content-Type: application/cdmi-object' http://127.0.0.1:8080/v1/AUTH_test/<container_name>/<object_name> -d '<Some JSON>'
