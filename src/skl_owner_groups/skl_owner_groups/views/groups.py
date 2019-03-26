# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.views.base import BaseView
from pyramid.httpexceptions import HTTPFound
from skl_owner_groups.models import update_skl_vote_power
from voteit.core.security import MODERATE_MEETING
from voteit.core.security import VIEW
from voteit.irl.models.interfaces import IMeetingPresence

from skl_owner_groups.interfaces import IVGroups
from skl_owner_groups.security import ADD_VGROUP


class GroupsView(BaseView):

    def __call__(self):
        presence = IMeetingPresence(self.request.meeting)
        return {'here_url': self.request.resource_url(self.context),
                'can_add': self.request.has_permission(ADD_VGROUP),
                'users': self.request.root['users'],
                'presence_check_open': presence.open,
                'present_userids': presence.present_userids}


class UpdateVotes(BaseView):

    def __call__(self):
        was_count, new_count = update_skl_vote_power(self.context)
        if was_count == new_count:
            self.flash_messages.add("Ingen förändring i rösttal")
        else:
            self.flash_messages.add("SKL har nu {} röster istället för {}".format(new_count, was_count))
        return HTTPFound(location=self.request.resource_url(self.context))


def includeme(config):
    config.add_view(
        GroupsView, context=IVGroups, permission=VIEW,
        renderer="skl_owner_groups:templates/groups.pt"
    )
    config.add_view(
        UpdateVotes, context=IVGroups, permission=MODERATE_MEETING, name='_update_skl_vote_power'
    )
