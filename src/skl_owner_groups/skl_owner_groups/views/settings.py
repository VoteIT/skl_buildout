# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.views.base import BaseForm
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from voteit.core import security
from voteit.core.models.interfaces import IMeeting
from voteit.core.views.control_panel import control_panel_category

from skl_owner_groups.interfaces import GROUPS_NAME
from skl_owner_groups.models import create_groups
from skl_owner_groups.models import groups_exist
from skl_owner_groups.models import groups_active


CREATE_VIEW_NAME = '_create_skl_groups'


def create_link(context, request, va, **kw):
    if not groups_exist(context, request):
        url = request.resource_url(request.meeting, CREATE_VIEW_NAME)
        return """
        <li><a href="%s">%s</a></li>
        """ % (url, va.title)


def groups_main_link(context, request, va, **kw):
    if groups_active(context, request):
        groups = request.meeting[GROUPS_NAME]
        url = request.resource_url(groups)
        title = request.localizer.translate(groups.title)
        return """
        <li><a href="%s">%s</a></li>
        """ % (url, title)


def groups_context_cpanel(context, request, va, **kw):
    if groups_exist(context, request):
        groups = request.meeting[GROUPS_NAME]
        url = request.resource_url(groups)
        title = request.localizer.translate(groups.title)
        return """<li><a href="%s">%s</a></li>""" % (url, title)


@view_config(name = CREATE_VIEW_NAME,
             context = IMeeting,
             renderer = "arche:templates/form.pt",
             permission = security.MODERATE_MEETING)
class CreateForm(BaseForm):
    schema_name = 'create'
    type_name = 'VGroups'
    title = "Aktivera grupper"

    def appstruct(self):
        return {}

    def save_success(self, appstruct):
        if GROUPS_NAME in self.context:
            self.flash_messages.add("Röstgrupperna finns redan", type="warning", require_commit=False)
            raise HTTPFound(location = self.request.resource_url(self.context, GROUPS_NAME))
        self.context[GROUPS_NAME] = vgroups = self.request.content_factories['VGroups']()
        create_groups(vgroups, self.request)
        return HTTPFound(location = self.request.resource_url(self.context, GROUPS_NAME))

    def cancel_failure(self, *args):
        return HTTPFound(location = self.request.resource_url(self.context))


def includeme(config):
    config.scan(__name__)
    config.add_view_action(
        groups_main_link,
        'nav_meeting', 'vgroups',
        permission=security.VIEW,
    )
    config.add_view_action(
        control_panel_category,
        'control_panel', 'vgroups',
        panel_group='control_panel_vgroups',
        title="SKLs grupper",
        description="Hanterar rösträtt för olika kategorier av användare",
        permission=security.MODERATE_MEETING,
        check_active=groups_active
    )
    config.add_view_action(
        create_link,
        'control_panel_vgroups', 'create',
        title="Skapa grupper",
        permission=security.MODERATE_MEETING,
        view_name=CREATE_VIEW_NAME,

    )
    config.add_view_action(
        groups_context_cpanel,
        'control_panel_vgroups', 'settings',
        title="Inställningar",
        view_name="edit",
    )
