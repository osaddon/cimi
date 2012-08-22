from cimi import CIMIMiddleware

def filter_factory(global_conf, **local_conf):
    """Standard filter factory to use the middleware with paste.deploy"""

    conf = global_conf.copy()
    conf.update(local_conf)

    # Process the cdmi root and strip off leading or trailing space and slashes
    conf.setdefault('request_prefix', '/cimiv1')
    conf.setdefault('os_version', '/v2')

    def cimi_filter(app):
        return CIMIMiddleware(app, conf)

    return cimi_filter
