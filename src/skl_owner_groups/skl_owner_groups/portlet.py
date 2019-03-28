# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from decimal import Decimal

from arche.portlets import get_portlet_manager
from arche.interfaces import IObjectAddedEvent
from arche.interfaces import IObjectUpdatedEvent
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.traversal import find_interface
from voteit.core import security
from voteit.core.models.interfaces import IMeeting, IAgendaItem
from voteit.core.portlets.agenda_item import PollsInline
from voteit.core.portlets.agenda_item import PollsPortlet

from skl_owner_groups.interfaces import IVGroups
from skl_owner_groups.interfaces import GROUPS_NAME
from skl_owner_groups.models import get_total_categorized_vote_power


SKL_POLLS_PORTLET = 'ai_polls_skl'
DEFAULT_POLLS_PORTLET = PollsPortlet.name
SKL_POLLS_VIEW_NAME = '__skl_ai_polls__'


class SKLPollsPortlet(PollsPortlet):
    name = SKL_POLLS_PORTLET
    view_name = SKL_POLLS_VIEW_NAME


class SKLPollsInline(PollsInline):

    def get_voted_estimate(self, poll):
        """ Returns an approx guess without doing expensive calculations.
            This method should rely on other things later on.

            Should only be called during ongoing or closed polls.
        """
        response = {'added': len(poll), 'total': 0}
        wf_state = poll.get_workflow_state()
        try:
            vote_power = get_total_categorized_vote_power(self.request.meeting[GROUPS_NAME])
            response['total'] = vote_power['total']
        except HTTPBadRequest:
            pass
        if response['total'] != 0:
            try:
                response['percentage'] = int(
                    round(100 * Decimal(response['added']) / Decimal(response['total']), 0))
            except ZeroDivisionError:
                response['percentage'] = 0
        else:
            response['percentage'] = 0
        return response


def adjust_poll_portlet(context, skl_version=True):
    """ Adjust poll portlet to this type"""
    PSLOT = 'agenda_item'
    if skl_version:
        portlet_name = SKL_POLLS_PORTLET
        remove_portlet_name = DEFAULT_POLLS_PORTLET
    else:
        portlet_name = DEFAULT_POLLS_PORTLET
        remove_portlet_name = SKL_POLLS_PORTLET
    meeting = find_interface(context, IMeeting)
    assert meeting
    manager = get_portlet_manager(meeting)
    unwanted_portlet = None
    for p in manager.get_portlets(PSLOT, remove_portlet_name):
        unwanted_portlet = p
    if unwanted_portlet:
        manager.remove(PSLOT, unwanted_portlet.uid)
    if not manager.get_portlets(PSLOT, portlet_name):
        added_portlet = manager.add(PSLOT, portlet_name)
        portlet_folder = manager[PSLOT]
        order = list(portlet_folder.order)
        order.remove(added_portlet.uid)
        order.insert(0, added_portlet.uid)
        portlet_folder.order = order


def groups_added_subscriber(context, event):
    """ Add the custom poll portlet. """
    adjust_poll_portlet(context, skl_version=True)


def groups_changed_subscriber(context, event):
    """ Insert the custom poll portlet if vote groups was enabled. Restore original portlet if it was removed. """
    if event.changed is None or 'enabled' in event.changed:
        adjust_poll_portlet(context, skl_version=context.enabled)


def includeme(config):
    config.add_portlet(SKLPollsPortlet)
    config.add_subscriber(groups_added_subscriber, [IVGroups, IObjectAddedEvent])
    config.add_subscriber(groups_changed_subscriber, [IVGroups, IObjectUpdatedEvent])
    # Custom version of polls inline view - __ai_polls__
    config.add_view(SKLPollsInline,
                    name=SKL_POLLS_VIEW_NAME,
                    context=IAgendaItem,
                    permission=security.VIEW,
                    renderer='skl_owner_groups:templates/skl_polls_inline.pt')
