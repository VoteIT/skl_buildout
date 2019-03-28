# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.portlets import get_portlet_manager
from arche.interfaces import IObjectAddedEvent
from arche.interfaces import IObjectUpdatedEvent
from pyramid.traversal import find_interface
from skl_owner_groups.interfaces import IVGroups
from voteit.core.models.interfaces import IMeeting
from voteit.core.portlets.agenda_item import PollsPortlet


SKL_POLLS_PORTLET = 'ai_polls_skl'
DEFAULT_POLLS_PORTLET = PollsPortlet.name


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
    config.add_subscriber(groups_added_subscriber, [IVGroups, IObjectAddedEvent])
    config.add_subscriber(groups_changed_subscriber, [IVGroups, IObjectUpdatedEvent])
