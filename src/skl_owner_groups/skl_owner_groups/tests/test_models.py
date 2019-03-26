from collections import Counter
from unittest import TestCase

from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.request import apply_request_extensions
from voteit.core.models.agenda_item import AgendaItem
from voteit.core.models.meeting import Meeting
from voteit.core.models.poll import Poll
from voteit.core.models.proposal import Proposal
from voteit.core.models.site import SiteRoot
from voteit.core.models.vote import Vote
from voteit.core.testing_helpers import bootstrap_and_fixture
from voteit.irl.models.interfaces import IElegibleVotersMethod
from voteit.irl.models.interfaces import IMeetingPresence
from zope.interface.verify import verifyObject

from skl_owner_groups.interfaces import GROUPS_NAME


class RepresentativesAsVotersTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        root = bootstrap_and_fixture(self.config)
        self.config.include('voteit.irl.models.meeting_presence')
        self.config.include('skl_owner_groups.resources')
        request = testing.DummyRequest()
        apply_request_extensions(request)
        self.config.begin(request)
        request.root = root
        root['m'] = meeting = Meeting()
        groups = meeting[GROUPS_NAME] = request.content_factories['VGroups']()
        gfact = request.content_factories['VGroup']
        groups['a'] = gfact(owner='adam', title='A')
        groups['b'] = gfact(owner='berit', title='B')
        groups['c'] = gfact(owner='cina', title='C')
        presence = IMeetingPresence(meeting)
        return groups, request, presence

    @property
    def _cut(self):
        from skl_owner_groups.models import RepresentativesAsVoters
        return RepresentativesAsVoters

    def test_integration(self):
        self.config.include('arche.models.reference_guard')
        self.config.include('skl_owner_groups.models')
        meeting = Meeting()
        method = self.config.registry.queryAdapter(meeting, IElegibleVotersMethod, name = self._cut.name)
        self.assertIsNotNone(method)

    def test_iface(self):
        obj = self._cut(testing.DummyResource())
        self.assertTrue(verifyObject(IElegibleVotersMethod, obj))

    def test_two_present(self):
        groups, request, presence = self._fixture()
        presence.start_check()
        presence.add('adam')
        presence.add('berit')
        presence.end_check()
        obj = self._cut(groups.__parent__)
        self.assertEqual({'adam', 'berit'}, set(obj.get_voters()))

    def test_present_but_no_votes(self):
        groups, request, presence = self._fixture()
        groups.delegate_vote_to('a', 'b')
        presence.start_check()
        presence.add('adam')
        presence.add('berit')
        presence.end_check()
        obj = self._cut(groups.__parent__)
        self.assertEqual({'berit'}, set(obj.get_voters()))

    def test_presence_check_not_closed(self):
        groups, request, presence = self._fixture()
        presence.start_check()
        obj = self._cut(groups.__parent__)
        generator = obj.get_voters()
        self.assertRaises(HTTPBadRequest, list, generator)


class SKLVotePowerTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        root = bootstrap_and_fixture(self.config)
        self.config.include('voteit.irl.models.meeting_presence')
        self.config.include('skl_owner_groups.resources')
        request = testing.DummyRequest()
        apply_request_extensions(request)
        self.config.begin(request)
        request.root = root
        root['m'] = meeting = Meeting()
        groups = meeting[GROUPS_NAME] = request.content_factories['VGroups']()
        gfact = request.content_factories['VGroup']
        # We use other base votes to make the tests clearer
        groups['a'] = gfact(owner='adam', title='A', category='kommun', base_votes=1)
        groups['b'] = gfact(owner='berit', title='B', category='kommun', base_votes=2)
        groups['c'] = gfact(owner='cina', title='C', category='region', base_votes=4)
        groups['skl'] = gfact(owner='teresa', title='SKL', category='skl', base_votes=8)  # Will be overridden
        presence = IMeetingPresence(meeting)
        return groups, request, presence

    @property
    def _fut(self):
        from skl_owner_groups.models import update_skl_vote_power
        return update_skl_vote_power

    def _present(self, presence, *userids):
        presence.start_check()
        for userid in userids:
            presence.add(userid)
        presence.end_check()

    def test_all_present(self):
        groups, request, presence = self._fixture()
        self._present(presence, 'adam', 'berit', 'cina', 'teresa')
        was, new = self._fut(groups)
        self.assertEqual(groups['skl'].base_votes, 6)
        self.assertEqual(was, 8)
        self.assertEqual(new, 6)

    def test_delegated_votes(self):
        groups, request, presence = self._fixture()
        self._present(presence, 'adam', 'berit', 'cina', 'teresa')
        self.assertEqual(groups['skl'].base_votes, 8)

        # Delegate votes to c
        groups.delegate_vote_to('a', 'c')
        groups.delegate_vote_to('b', 'c')
        self._fut(groups)
        self.assertEqual(groups['skl'].base_votes, 6)

        # Delegate all votes to skl should have same result
        for x in ('a', 'b', 'c'):
            groups.delegate_vote_to(x, 'skl')
        self._fut(groups)
        self.assertEqual(groups['skl'].base_votes, 6)
        self.assertEqual(groups.get_vote_power('skl'), 6+7)  # Base votes + delegations

        # Just to make sure
        self.assertEqual(groups.get_categorized_vote_power('adam'), {})
        self.assertEqual(groups.get_categorized_vote_power('teresa'), {'skl': 6, 'region': 4, 'kommun': 3})

    def test_delegated_votes_and_presence(self):
        groups, request, presence = self._fixture()
        # SKL and one region present, no delegated votes
        self._present(presence, 'cina', 'teresa')
        self._fut(groups)
        # This decimates SKL votes too
        self.assertEqual(groups['skl'].base_votes, 3)

        # If votes are delegated from inactive accounts, they should matter
        groups.delegate_vote_to('b', 'c')
        self._fut(groups)
        self.assertEqual(groups['skl'].base_votes, 5)

        # Just to make sure
        self.assertEqual(groups.get_vote_power('skl'), 5)  # Base votes, since no delegations
        self.assertEqual(groups.get_vote_power('c'), 6)  # Base votes, and the delegation from b
        # This doesn't check presence
        self.assertEqual(groups.get_categorized_vote_power('berit'), {})
        self.assertEqual(groups.get_categorized_vote_power('cina'), {'region': 4, 'kommun': 2})
        self.assertEqual(groups.get_categorized_vote_power('teresa'), {'skl': 5})


class TotalCategorizedVotePowerTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        root = bootstrap_and_fixture(self.config)
        self.config.include('voteit.irl.models.meeting_presence')
        self.config.include('skl_owner_groups.resources')
        request = testing.DummyRequest()
        apply_request_extensions(request)
        self.config.begin(request)
        request.root = root
        root['m'] = meeting = Meeting()
        groups = meeting[GROUPS_NAME] = request.content_factories['VGroups']()
        gfact = request.content_factories['VGroup']
        # We use other base votes to make the tests clearer
        groups['a'] = gfact(owner='adam', title='A', category='kommun', base_votes=1)
        groups['b'] = gfact(owner='berit', title='B', category='kommun', base_votes=2)
        groups['c'] = gfact(owner='cina', title='C', category='region', base_votes=4)
        groups['skl'] = gfact(owner='teresa', title='SKL', category='skl', base_votes=8)  # Will be overridden
        presence = IMeetingPresence(meeting)
        return groups, request, presence

    @property
    def _fut(self):
        from skl_owner_groups.models import get_total_categorized_vote_power
        return get_total_categorized_vote_power

    def _present(self, presence, *userids):
        presence.start_check()
        for userid in userids:
            presence.add(userid)
        presence.end_check()

    def test_presence_matter(self):
        groups, request, presence = self._fixture()
        self._present(presence, 'adam', 'teresa')
        self.assertEqual(self._fut(groups), {'skl': 8, 'kommun': 1})

    def test_delegation_and_presence(self):
        groups, request, presence = self._fixture()
        self._present(presence, 'adam', 'teresa')
        groups.delegate_vote_to('c', 'skl')
        self.assertEqual(self._fut(groups), {'skl': 8, 'kommun': 1, 'region': 4})


class MultiplyVotesSubscriberIntegrationTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.include('arche.testing')
        self.config.include('arche.models.reference_guard')
        self.config.include('voteit.core.helpers')
        self.config.include('voteit.core.plugins.majority_poll')
        self.config.include('voteit.irl.models.meeting_presence')
        self.config.include('skl_owner_groups.resources')
        self.config.include('skl_owner_groups.models')

    def tearDown(self):
        testing.tearDown()

    def _poll_fixture(self):
        root = SiteRoot()
        root['m'] = meeting = Meeting()
        meeting['ai'] = ai = AgendaItem()
        ai['p1'] = Proposal()
        ai['p2'] = Proposal()
        ai['poll'] = Poll(poll_plugin='majority_poll')
        return meeting

    def _groups_fixture(self, meeting):
        from skl_owner_groups.resources import Group
        from skl_owner_groups.resources import Groups
        groups = meeting[GROUPS_NAME] = Groups()
        groups['a'] = Group(owner='adam', title='A', category='kommun', base_votes=1)
        groups['b'] = Group(owner='berit', title='B', category='kommun', base_votes=2)
        groups['c'] = Group(owner='cina', title='C', category='region', base_votes=4)
        groups['skl'] = Group(owner='teresa', title='SKL', category='skl', base_votes=8)  # Will be overridden
        return groups

    def _mk_request(self, meeting, userid):
        self.config.testing_securitypolicy(userid=userid, permissive=True)
        request = testing.DummyRequest()
        request.context = meeting
        apply_request_extensions(request)
        self.config.begin(request)
        return request

    def _mk_present(self, meeting, *userids):
        presence = IMeetingPresence(meeting)
        presence.start_check()
        for userid in userids:
            presence.add(userid)
        presence.end_check()

    def _mk_vote_power(self, groups):
        from skl_owner_groups.models import update_skl_vote_power
        update_skl_vote_power(groups)

    def test_vote_no_extra_votes(self):
        meeting = self._poll_fixture()
        groups = self._groups_fixture(meeting)
        self._mk_present(meeting, 'adam')
        self._mk_request(meeting, 'adam')
        poll = meeting['ai']['poll']
        # Add one vote as adam
        poll['adam'] = vote = Vote()
        self.assertEqual(len(poll), 1)
        self.assertEqual(getattr(vote, 'category', None), 'kommun')

    def test_skl_with_extra_votes(self):
        meeting = self._poll_fixture()
        groups = self._groups_fixture(meeting)
        groups.delegate_vote_to('a', 'skl')
        groups.delegate_vote_to('c', 'skl')
        self._mk_request(meeting, 'teresa')
        self._mk_present(meeting, 'teresa')
        self._mk_vote_power(groups)  # Presence check and delegation will cause SKL to have 4 votes
        poll = meeting['ai']['poll']
        # Add one vote as teresa, will add a lot of votes
        poll['teresa'] = vote = Vote()
        counter = Counter()
        for v in poll.values():
            counter[v.category] += 1
        self.assertEqual(counter, {'skl': 4, 'kommun': 1, 'region': 4})
        self.assertEqual(len(poll), 9)
        # Primary vote will be skl
        self.assertEqual(getattr(vote, 'category', None), 'skl')
        # All of them added by teresa
        for v in poll.values():
            self.assertIn('teresa', v.creators)

    def test_all_votes_change_on_update(self):
        meeting = self._poll_fixture()
        groups = self._groups_fixture(meeting)
        groups.delegate_vote_to('a', 'skl')
        groups.delegate_vote_to('b', 'skl')
        self._mk_request(meeting, 'teresa')
        self._mk_present(meeting, 'teresa')
        self._mk_vote_power(groups)  # Presence check and delegation will cause SKL to have 4 votes
        poll = meeting['ai']['poll']
        # Add one vote as teresa, will add a lot of votes
        vote = Vote()
        vote.set_vote_data('Hello world', notify=False)
        poll['teresa'] = vote
        self.assertEqual(len(poll), 5)
        # Check current value
        for v in poll.values():
            self.assertEqual(v.get_vote_data(), 'Hello world')
        # Update and recheck
        vote.set_vote_data('Bye world', notify=True)
        for v in poll.values():
            self.assertEqual(v.get_vote_data(), 'Bye world')

    def test_inactive_groups_cancel_subscriber(self):
        meeting = self._poll_fixture()
        groups = self._groups_fixture(meeting)
        groups.enabled = False
        self._mk_present(meeting, 'adam')
        self._mk_request(meeting, 'adam')
        poll = meeting['ai']['poll']
        # Add one vote as adam
        poll['adam'] = vote = Vote()
        self.assertEqual(len(poll), 1)
        self.assertEqual(getattr(vote, 'category', None), None)


class AnalyzeVoteDistributionTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        poll = Poll()

        # 2 for Hello, cat A + B
        vote = Vote()
        vote.set_vote_data('Hello', notify=False)
        vote.category = 'A'
        poll['a'] = vote

        vote = Vote()
        vote.set_vote_data('Hello', notify=False)
        vote.category = 'B'
        poll['b'] = vote

        # 1 for Bye, cat A
        vote = Vote()
        vote.set_vote_data('Bye', notify=False)
        vote.category = 'A'
        poll['c'] = vote

        return poll

    @property
    def _fut(self):
        from skl_owner_groups.models import analyze_vote_distribution
        return analyze_vote_distribution

    def test_distribution(self):
        poll = self._fixture()
        hashes, categories = self._fut(poll)
        self.assertEqual(hashes, {'8b1a9953c4611296a827abf8c47804d7': 'Hello', 'b665d826e919381052ec23b9eaec3b62': 'Bye'})
        self.assertIn('A', categories)
        self.assertIn('B', categories)
        self.assertEqual(categories['A'], {'8b1a9953c4611296a827abf8c47804d7': 1, 'b665d826e919381052ec23b9eaec3b62': 1})
        self.assertEqual(categories['B'], {'8b1a9953c4611296a827abf8c47804d7': 1})
