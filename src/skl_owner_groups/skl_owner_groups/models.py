# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from hashlib import md5
from collections import Counter
from json import dumps
from uuid import uuid4

import unicodecsv as csv
from arche.interfaces import IEmailValidatedEvent
from arche.interfaces import IObjectAddedEvent
from arche.interfaces import IObjectUpdatedEvent
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.path import AssetResolver
from pyramid.threadlocal import get_current_request
from pyramid.traversal import find_interface
from pyramid.traversal import find_root
from repoze.catalog.query import Eq
from repoze.catalog.query import Any
from six import string_types
from voteit.core.models.interfaces import IMeeting
from voteit.core.models.interfaces import IVote
from voteit.irl.models.elegible_voters_method import ElegibleVotersMethod
from voteit.irl.models.interfaces import IMeetingPresence

from skl_owner_groups.interfaces import IVGroup
from skl_owner_groups.interfaces import IVGroups
from skl_owner_groups.interfaces import GROUPS_NAME


_KOMMUNER_FILE = "skl_owner_groups:data/kommuner.csv"
_REGIONER_FILE = "skl_owner_groups:data/regioner.csv"
_VOTE_DIST_CACHEATTR = '_v_cat_vote_power'
_VOTE_CAT_CACHEATTR = '_v_cat_votes'


def groups_exist(context, request, *args, **kwargs):
    return GROUPS_NAME in request.meeting


def groups_active(context, request, *args, **kw):
    return groups_exist(context, request) and request.meeting[GROUPS_NAME].enabled


class RepresentativesAsVoters(ElegibleVotersMethod):
    name = 'skl_owner_groups'
    title = "SKRs metod för att sätta röstberättigade"
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
    groups['skl'] = factory(title='SKR', category='skl')

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
        - The result will be cached
    """
    assert IVGroups.providedBy(groups)
    meeting = find_interface(groups, IMeeting)
    presence = IMeetingPresence(meeting)
    if presence.open:  #pragma: no coverage
        raise HTTPBadRequest("Närvarokontrollen är inte avslutad")
    if hasattr(groups, _VOTE_DIST_CACHEATTR):
        return getattr(groups, _VOTE_DIST_CACHEATTR)
    counter = Counter()
    for userid in presence:
        counter.update(groups.get_categorized_vote_power(userid))
    counter['total'] = sum(counter.itervalues())
    setattr(groups, _VOTE_DIST_CACHEATTR, counter)
    return counter


def update_skl_vote_power(groups):
    """ Update SKLs votes based on meeting presence. """
    counter = get_total_categorized_vote_power(groups)
    skl = groups['skl']
    was_count = skl.base_votes
    skl.base_votes = counter['kommun'] + counter['region'] - 1
    if hasattr(groups, _VOTE_DIST_CACHEATTR):
        delattr(groups, _VOTE_DIST_CACHEATTR)
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

    # There may be situations when users can vote and don't have a group.
    # Before the meeting starts or during demos for instance.
    if group is None:
        return

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


def analyze_vote_distribution(poll):
    """ Check vote distribution, cache result. """
    if hasattr(poll, _VOTE_CAT_CACHEATTR):
        return getattr(poll, _VOTE_CAT_CACHEATTR)
    hashed = {}
    categorized = {}
    for v in [x for x in poll.values() if IVote.providedBy(x)]:
        vote_content = v.get_vote_data()
        if isinstance(vote_content, string_types):
            hashable_content = vote_content
        else:
            hashable_content = dumps(vote_content)
        checksum = md5(hashable_content).hexdigest()
        if checksum not in hashed:
            hashed[checksum] = vote_content
        counter = categorized.setdefault(getattr(v, 'category', ''), Counter())
        counter[checksum] += 1
    setattr(poll, _VOTE_CAT_CACHEATTR, (hashed, categorized))
    return hashed, categorized


def percentages_pass(percentages):
    """ Accepts a dict of categorized percentages. Returns bool. """
    # The 50 bar is really the case for this meeting, it's not a mistake!
    return percentages['kommun'] > 32 and percentages['region'] > 32 and percentages['total'] >= 50


def maybe_assign_user_to_group(event):
    """ A user has just validated their email address.
        Check groups to see if that user is an expected owner somewhere.
    """
    # Find upcoming and ongoing meetings
    user = event.user
    root = find_root(user)
    email = user.email
    for obj in root.values():
        if IMeeting.providedBy(obj) and obj.get_workflow_state() in ('upcoming', 'ongoing') and GROUPS_NAME in obj:
            groups = obj[GROUPS_NAME]
            if email in groups.potential_owners:
                group = groups.get(groups.potential_owners[email])
                if group:
                    if not group.owner:
                        group.owner = user.userid
                    del groups.potential_owners[email]


def extract_owner_data(text):
    """
    Text probably looks something like:
    namn.namnsson@alvkarleby.se	0319 ÄLVKARLEBY (Where there's a tab after the email)
    :param text: csv tab separated text
    :return: generator with email, group_name
    """
    counter = 1
    for row in text.splitlines():
        if not row:
            counter += 1
            continue
        cols = row.split("\t")
        if len(cols) < 2:
            raise ValueError("Rad %s verkar inte innehålla något tabtecken" % counter)
        if len(cols) > 2:
            raise ValueError("Rad %s har för många tabtecken" % counter)
        email = cols[0].strip()
        if not email:
            raise ValueError("Rad %s saknar epost" % counter)
        group_name = cols[1].split()[0]
        if not group_name:
            raise ValueError("Rad %s saknar information om gruppnamn" % counter)
        counter += 1
        yield email, group_name


def assign_potential_from_csv(groups, text, clear_all_existing=False, overwrite_owner=False):
    # Note validation must be done before using this
    if clear_all_existing:
        groups.potential_owners.clear()
    root = find_root(groups)
    already_potential_groups = groups.potential_owners.values()
    overwritten = 0
    already_owned = 0
    new_assigned = 0
    new_potential = 0
    replaced_potential = 0

    for (email, group_name) in extract_owner_data(text):
        group = groups[group_name]

        # Should we overwrite the owner if the group is already owned?
        if group.owner and not overwrite_owner:
            already_owned += 1
            continue

        # Does the user already exist?
        user = root.users.get_user_by_email(email, only_validated=True)
        if user is not None:
            if group.owner:
                overwritten += 1
            else:
                new_assigned += 1
            group.owner = user.userid
            continue

        if group_name in already_potential_groups:
            replaced_potential += 1
            del group.potential_owner
        else:
            # Not other action, so add the email as a potential
            new_potential += 1
        groups.add_potential_owner(email, group_name)

    return dict(
        overwritten=overwritten,
        already_owned=already_owned,
        new_assigned=new_assigned,
        new_potential=new_potential,
        replaced_potential=replaced_potential
    )


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
    config.add_subscriber(maybe_assign_user_to_group, IEmailValidatedEvent)