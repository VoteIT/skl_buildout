# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import Counter
from uuid import uuid4

import unicodecsv as csv
from arche.interfaces import IObjectAddedEvent
from arche.interfaces import IObjectUpdatedEvent
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.path import AssetResolver
from pyramid.threadlocal import get_current_request
from pyramid.traversal import find_interface
from voteit.core.models.interfaces import IVote, IMeeting
from voteit.irl.models.elegible_voters_method import ElegibleVotersMethod
from voteit.irl.models.interfaces import IMeetingPresence

from skl_owner_groups.interfaces import IVGroup
from skl_owner_groups.interfaces import IVGroups
from skl_owner_groups.interfaces import GROUPS_NAME


_KOMMUNER_FILE = "skl_owner_groups:data/kommuner.csv"
_REGIONER_FILE = "skl_owner_groups:data/regioner.csv"


def groups_exist(context, request, *args, **kwargs):
    return GROUPS_NAME in request.meeting


def groups_active(context, request, *args, **kw):
    return groups_exist(context, request) and request.meeting[GROUPS_NAME].enabled


class RepresentativesAsVoters(ElegibleVotersMethod):
    name = 'skl_owner_groups'
    title = "SKLs metod för att sätta röstberättigade"
    description = "Sätter rösträtt användare som är ansvariga för en grupp och närvarande."

    def get_voters(self, request = None, **kw):
        """ Returns userids that are:
            - owner (responsible) for a group.
            - present
            - that group has votes
        """
        if GROUPS_NAME not in self.context: # pragma: no coverage
            raise HTTPBadRequest("Hittar inte grupper")
        presence = IMeetingPresence(self.context)
        if presence.open:
            raise HTTPBadRequest("Stäng närvarokontrollen först")
        groups = self.context[GROUPS_NAME]
        for group in groups.values():
            userid = group.owner
            if userid and userid in presence and groups.get_vote_power(group.__name__):
                yield userid


def create_groups(groups, request):
    """ Skapa group-objekt i ett groups-object..

        Specialregler:

        * SKL ska alltid finnas
        * Kommunen Gotland ska tas bort, eftersom regionen Gotland är ägare

        Hantera nycklar och kommunkoder som strängar

    """
    assert IVGroups.providedBy(groups)

    # Remove ordering in case it's set
    del groups.order

    factory = request.content_factories['VGroup']

    # SKL
    groups['skl'] = factory(title='SKL', category='skl')

    # Regionerna
    for (key, title) in _get_kv_from_csv(_REGIONER_FILE):
        groups[key] = factory(title=title, category='region')

    # Kommunerna - minus Gotland!
    for (key, title) in _get_kv_from_csv(_KOMMUNER_FILE):
        if key == '0980':
            continue
        groups[key] = factory(title=title, category='kommun')


def _get_kv_from_csv(asset_spec):
    resolver = AssetResolver()
    resolved = resolver.resolve(asset_spec)
    with open(resolved.abspath(), 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=str(';'))
        for row in reader:
            # Första kolumnen är tom...
            if row[1]:
                yield row[1], row[2]


if __name__ == '__main__':
    print("=== Kommuner ===")
    for (key, title) in _get_kv_from_csv(_KOMMUNER_FILE):
        print (key.ljust(10) + title)

    print("=== Regioner ===")
    for (key, title) in _get_kv_from_csv(_REGIONER_FILE):
        print (key.ljust(10) + title)


def guard_representatives(request, context):
    groups = find_interface(context, IVGroups)
    return [groups[x] for x in groups.is_delegate_for(context.__name__)]


def get_total_categorized_vote_power(groups):
    """ Get a counter of the total vote power for all categories.

        - This does care about meeting presence
        - It does NOT adjust SKL votes
    """
    assert IVGroups.providedBy(groups)
    meeting = find_interface(groups, IMeeting)
    presence = IMeetingPresence(meeting)
    if presence.open:  #pragma: no coverage
        raise HTTPBadRequest("Närvarokontrollen är inte avslutad")
    counter = Counter()
    for userid in presence:
        counter.update(groups.get_categorized_vote_power(userid))
    return counter


def update_skl_vote_power(groups):
    """ Update SKLs votes based on meeting presence. """
    counter = get_total_categorized_vote_power(groups)
    skl = groups['skl']
    was_count = skl.base_votes
    skl.base_votes = counter['kommun'] + counter['region'] - 1
    return was_count, skl.base_votes


def multiply_and_categorize_votes(obj, event):
    """ This subscriber multiplies votes for users who have several votes.
        It also categorizes them according to the users membership.
        The attribute 'category' will be set on the vote object.
    """
    request = get_current_request()
    if not groups_active(obj, request):
        return
    userid = request.authenticated_userid

    # Only perform this function on the inital vote object
    if userid != obj.__name__:
        return
    meeting = request.meeting
    groups = meeting[GROUPS_NAME]
    group = groups.get_users_group(userid)

    vote_counter = groups.get_vote_power(group.__name__)
    # Since one vote was used already, that caused this subscriber to fire :)
    vote_counter -= 1

    # Regardless of vote power left, we want the rest of the function to categorize added votes so don't halt here!
    poll = obj.__parent__
    poll_plugin = poll.get_poll_plugin()
    vote_data = poll[userid].get_vote_data()  # Just to make sure, get from the initial one

    if IObjectAddedEvent.providedBy(event):
        # Also categorize the votes here
        votes = [obj]

        Vote = poll_plugin.get_vote_class()
        assert IVote.implementedBy(Vote)
        for i in range(vote_counter):
            name = unicode(uuid4())
            vote = Vote(creators=[userid])
            vote.set_vote_data(vote_data, notify=False)
            poll[name] = vote
            votes.append(vote)

        #Categorize the votes according to the counter obj
        counter = groups.get_categorized_vote_power(userid)
        assert sum(counter.itervalues()) == len(votes)
        i = 0
        for cat in counter.elements():
            setattr(votes[i], 'category', cat)
            i += 1

    elif IObjectUpdatedEvent.providedBy(event):
        for vote in poll.get_content(iface=IVote):
            if vote.creators[0] != userid:
                continue
            if vote.__name__ == userid:
                continue
            vote.set_vote_data(vote_data)


def includeme(config):
    config.add_ref_guard(
        guard_representatives,
        requires=(IVGroup,),
        catalog_result=False,
        title="Är representant för en annan grupp.",
        allow_move=False
    )
    config.registry.registerAdapter(RepresentativesAsVoters, name=RepresentativesAsVoters.name)
    config.add_subscriber(multiply_and_categorize_votes, [IVote, IObjectAddedEvent])
    config.add_subscriber(multiply_and_categorize_votes, [IVote, IObjectUpdatedEvent])
