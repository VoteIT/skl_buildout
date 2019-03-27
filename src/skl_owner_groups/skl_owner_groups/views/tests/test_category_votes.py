from collections import Counter
from unittest import TestCase

from arche.utils import get_view
from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.request import apply_request_extensions
from pyramid.traversal import find_interface
from voteit.core.models.agenda_item import AgendaItem
from voteit.core.models.interfaces import IMeeting
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


class CategoryVotesViewsTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.include('arche.testing')
        self.config.include('arche.testing.catalog')

#        self.config.include('arche.models.reference_guard')
        self.config.include('voteit.core.helpers')
        self.config.include('voteit.core.plugins.majority_poll')
        self.config.include('voteit.irl.models.meeting_presence')
        self.config.include('skl_owner_groups.resources')
 #       self.config.include('skl_owner_groups.models')

    def tearDown(self):
        testing.tearDown()

    def _fixture(self, votes):
        # Meeting fixture
        root = SiteRoot()
        root['m'] = meeting = Meeting()
        meeting['ai'] = ai = AgendaItem()
        ai['poll'] = poll = Poll(poll_plugin='majority_poll')
        ai['p1'] = Proposal(text="proposal one", uid='uid1')
        ai['p2'] = Proposal(text="proposal two", uid='uid2')

        # Groups
        from skl_owner_groups.resources import Group
        from skl_owner_groups.resources import Groups
        groups = meeting[GROUPS_NAME] = Groups()
        groups['a'] = Group(owner='adam', title='A', category='kommun', base_votes=4)
        groups['b'] = Group(owner='berit', title='B', category='kommun', base_votes=1)
        groups['c'] = Group(owner='cina', title='C', category='region', base_votes=1)
        groups['skl'] = Group(owner='teresa', title='SKL', category='skl', base_votes=5)

        # All should be present
        presence = IMeetingPresence(meeting)
        presence.start_check()
        for userid in ('adam', 'berit', 'cina', 'teresa'):
            presence.add(userid)
        presence.end_check()

        # Add votes - the manual way!
        class _Counter(object):
            def __init__(self):
                self.i = 0

            def __call__(self):
                self.i += 1
                return str(self.i)

        c = _Counter()

        # 5 skl for one - teresa
        for i in range(5):
            vote = Vote()
            vote.set_vote_data(votes['one'], notify=False)
            vote.category = 'skl'
            poll[c()] = vote

        # 1 region for one - cina
        vote = Vote()
        vote.set_vote_data(votes['one'], notify=False)
        vote.category = 'region'
        poll[c()] = vote

        # 4 kommun for two - adam
        for i in range(4):
            vote = Vote()
            vote.set_vote_data(votes['two'], notify=False)
            vote.category = 'kommun'
            poll[c()] = vote

        # 1 region for two - berit
        vote = Vote()
        vote.set_vote_data(votes['two'], notify=False)
        vote.category = 'region'
        poll[c()] = vote

        return poll

    def _majority_poll_fixture(self):
        votes = {
            'one': {'proposal': 'uid1'},
            'two': {'proposal': 'uid2'}
        }
        return self._fixture(votes)

    def _combined_simple_fixture(self):
        votes = {
            'one': {'uid1': 'approve'},
            'two': {'uid2': 'approve', 'uid1': 'deny'}
        }
        return self._fixture(votes)

    @property
    def _cut(self):
        from skl_owner_groups.views.category_votes import CategoryVotes
        return CategoryVotes

    def _mk_request(self, poll):
        self.config.testing_securitypolicy(userid='anyone', permissive=True)
        request = testing.DummyRequest(is_xhr=True)
        request.context = poll
        apply_request_extensions(request)
        self.config.begin(request)
        return request

    def test_majority_poll_count(self):
        poll = self._majority_poll_fixture()
        request = self._mk_request(poll)
        view = self._cut(poll, request)
        view()
        counter = view.method_majority_poll('uid1')
        self.assertEqual(counter, {'skl': 5, 'region': 1, 'total': 6})
        counter = view.method_majority_poll('uid2')
        self.assertEqual(counter, {'kommun': 4, 'region': 1, 'total': 5})

    def test_majority_poll_render(self):
        self.config.include('skl_owner_groups.views.category_votes')
        self.config.include('pyramid_chameleon')
        poll = self._majority_poll_fixture()
        request = self._mk_request(poll)
        view = get_view(poll, request, '_category_votets')
        response = view(poll, request)
        self.assertEqual(response.status_int, 200)
