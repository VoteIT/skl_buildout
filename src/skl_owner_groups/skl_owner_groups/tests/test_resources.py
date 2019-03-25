from unittest import TestCase

from pyramid import testing
from pyramid.request import apply_request_extensions
from voteit.core.testing_helpers import bootstrap_and_fixture

from skl_owner_groups.interfaces import GROUPS_NAME


class GroupsTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        root = bootstrap_and_fixture(self.config)
        self.config.include('skl_owner_groups.resources')
        request = testing.DummyRequest()
        apply_request_extensions(request)
        self.config.begin(request)
        request.root = root
        groups = root[GROUPS_NAME] = request.content_factories['VGroups']()
        gfact = request.content_factories['VGroup']
        groups['a'] = gfact(owner='adam', title='A')
        groups['b'] = gfact(owner='berit', title='B')
        groups['c'] = gfact(owner='cina', title='C')
        return groups, request

    def test_get_sorted(self):
        groups, request = self._fixture()
        self.assertEqual([x.title for x in groups.get_sorted_values()], ['A', 'B', 'C'])

    def test_vote_delegation(self):
        groups, request = self._fixture()
        groups.delegate_vote_to('a', 'b')
        self.assertEqual(groups.has_delegated_to('a'), 'b')

    def test_delegation_to(self):
        groups, request = self._fixture()
        groups.delegate_vote_to('a', 'b')
        self.assertFalse(groups.can_delegate_to('a'))
        self.assertTrue(groups.can_delegate_to('b'))
        self.assertTrue(groups.can_delegate_to('c'))

    def test_redelegate(self):
        groups, request = self._fixture()
        groups.delegate_vote_to('a', 'b')
        groups.delegate_vote_to('a', 'c')
        self.assertEqual(groups.has_delegated_to('a'), 'c')
        self.assertEqual(groups.has_delegated_to('b'), None)
        self.assertEqual(groups.has_delegated_to('c'), None)

    def test_is_delegate_for(self):
        groups, request = self._fixture()
        groups.delegate_vote_to('a', 'c')
        groups.delegate_vote_to('b', 'c')
        self.assertEqual(groups.is_delegate_for('a'), frozenset())
        self.assertEqual(groups.is_delegate_for('b'), frozenset())
        self.assertEqual(groups.is_delegate_for('c'), frozenset(['a', 'b']))

    def test_get_vote_power_delegation(self):
        groups, request = self._fixture()
        for x in ('a', 'b', 'c'):
            self.assertEqual(groups.get_vote_power(x), 1)

        groups.delegate_vote_to('a', 'c')
        self.assertEqual(groups.get_vote_power('a'), 0)
        self.assertEqual(groups.get_vote_power('c'), 2)

        groups.delegate_vote_to('b', 'c')
        self.assertEqual(groups.get_vote_power('a'), 0)
        self.assertEqual(groups.get_vote_power('b'), 0)
        self.assertEqual(groups.get_vote_power('c'), 3)

    def test_get_vote_power_count(self):
        groups, request = self._fixture()
        groups['a'].base_votes = 3
        groups['b'].base_votes = 2
        self.assertEqual(groups.get_vote_power('a'), 3)
        self.assertEqual(groups.get_vote_power('b'), 2)
        self.assertEqual(groups.get_vote_power('c'), 1)

        groups.delegate_vote_to('a', 'b')
        self.assertEqual(groups.get_vote_power('a'), 0)
        self.assertEqual(groups.get_vote_power('b'), 5)
        self.assertEqual(groups.get_vote_power('c'), 1)


class GroupTest(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        root = bootstrap_and_fixture(self.config)
        self.config.include('skl_owner_groups.resources')
        request = testing.DummyRequest()
        apply_request_extensions(request)
        self.config.begin(request)
        request.root = root
        groups = root[GROUPS_NAME] = request.content_factories['VGroups']()
        gfact = request.content_factories['VGroup']
        groups['a'] = gfact(owner='adam', title='A')
        groups['b'] = gfact(owner='berit', title='B')
        groups['c'] = gfact(owner='cina', title='C')
        return groups, request

    def test_get_delegate_to(self):
        groups, request = self._fixture()
        group = groups['a']
        self.assertEqual(group.delegate_to, None)

    def test_set_delegate_to(self):
        groups, request = self._fixture()
        group = groups['a']
        group.delegate_to = 'b'
        self.assertEqual(group.delegate_to, 'b')
