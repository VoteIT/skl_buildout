# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.views.base import DefaultEditForm
from arche.views.base import BaseView
from pyramid.httpexceptions import HTTPFound
from voteit.core.security import MODERATE_MEETING
from voteit.core.security import VIEW
from voteit.irl.models.interfaces import IMeetingPresence

from skl_owner_groups.interfaces import IVGroups
from skl_owner_groups.models import assign_potential_from_csv
from skl_owner_groups.models import update_skl_vote_power
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
            self.flash_messages.add("SKR har nu {} röster istället för {}".format(new_count, was_count))
        return HTTPFound(location=self.request.resource_url(self.context))


class PotentialOwnersView(BaseView):

    def __call__(self):
        return {}


class AssignPotentialOwnersForm(DefaultEditForm):
    schema_name = 'assign'
    title = "Knyt ansvariga via epost"

    def save_success(self, appstruct):
        csv_text = appstruct.pop('csv_text')
        results = assign_potential_from_csv(self.context, csv_text, **appstruct)
        out = "Resultat: \n"
        overwritten = results['overwritten']
        already_owned = results['already_owned']
        new_assigned = results['new_assigned']
        new_potential = results['new_potential']
        replaced_potential = results['replaced_potential']
        if overwritten:
            out += "%s fått ny ansvarig. \n" % overwritten
        if already_owned:
            out += "%s ändrades inte eftersom de redan hade en ansvarig. \n" % already_owned
        if new_assigned:
            out += "%s fick en ny ägare. \n" % new_assigned
        if new_potential:
            out += "%s hittades inte i VoteIT men väntar på registrering. " % new_potential
        if replaced_potential:
            out += "%s fick sin potentiellt ansvarige ersatt av ny. " % replaced_potential
        self.flash_messages.add(out, auto_destruct=False)
        return HTTPFound(location=self.request.resource_url(self.context))


def includeme(config):
    config.add_view(
        GroupsView, context=IVGroups, permission=VIEW,
        renderer="skl_owner_groups:templates/groups.pt"
    )
    config.add_view(
        UpdateVotes, context=IVGroups, permission=MODERATE_MEETING, name='_update_skl_vote_power'
    )
    config.add_view(
        PotentialOwnersView, context=IVGroups, permission=MODERATE_MEETING, name='_potential_owners',
        renderer="skl_owner_groups:templates/potential_owners.pt"
    )
    config.add_view(
        AssignPotentialOwnersForm, context=IVGroups, permission=MODERATE_MEETING, name='_import_potential_owners',
        renderer="arche:templates/form.pt"
    )
