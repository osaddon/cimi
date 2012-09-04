CIMI for OpenStack's Nova
--------------------------

A Python egg that adds support for the [CIMI protocol] to OpenStack Nova.

Setup
=====

1. Install [Openstack Nova](http://wiki.openstack.org/InstallInstructions/Nova)
2. Grab the cimi implementation from github:
     `git clone http://github.com/osaddon/cimi`
3. Install this python egg: `sudo python setup.py install`
4. Configure cimi to work with Nova:

In `/etc/nova/api-paste.ini`, add cimiv1 path to enable the cimi request

    [composite:osapi_compute]
    use = call:nova.api.openstack.urlmap:urlmap_factory
    /: oscomputeversions
    /v1.1: openstack_compute_api_v2
    /v2: openstack_compute_api_v2
    /cimiv1: openstack_compute_api_v2

In `/etc/nova/api-paste.ini`, add cimi filter before osapi_compute_app_v2

    [composite:openstack_compute_api_v2]
    use = call:nova.api.auth:pipeline_factory
    noauth = faultwrap sizelimit noauth ratelimit cimi osapi_compute_app_v2
    keystone = faultwrap sizelimit authtoken keystonecontext ratelimit cimi osapi_compute_app_v2
    keystone_nolimit = faultwrap sizelimit authtoken keystonecontext cimi osapi_compute_app_v2

And add the following section to the file:

    [filter:cimi]
    use = egg:cimiapi#cimiapp
    request_prefix = /cimiv1
    os_version = /v2

To enable logging for cimi, add the following three lines in /etc/nova/nova.conf file

    use_syslog=False
    logfile=/opt/stack/logs/nova.log
    default_log_levels=nova=ERROR,cimi=INFO


Running tests
=============

    TODO