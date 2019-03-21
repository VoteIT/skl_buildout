from pyramid.httpexceptions import HTTPFound

from skl_owner_groups.interfaces import IVGroup


def _redirect_parent(context, request):
    return HTTPFound(request.resource_url(context.__parent__))


def includeme(config):
    config.add_view(_redirect_parent, context=IVGroup)