from unittest import TestCase

from arche.scripting import StaticAuthenticationPolicy
from arche.security import groupfinder, context_effective_principals
from pyramid import testing
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.request import apply_request_extensions
from pyramid.security import remember
from voteit.core.testing_helpers import bootstrap_and_fixture
from voteit.core.security import ROLE_MODERATOR
from voteit.core.security import MODERATE_MEETING

from skl_owner_groups.interfaces import GROUPS_NAME


class SecurityIntegrationTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        self.config.set_authorization_policy(ACLAuthorizationPolicy())
        self.config.set_authentication_policy(StaticAuthenticationPolicy(callback=groupfinder))
        root = bootstrap_and_fixture(self.config)
        self.config.include('arche.portlets')
        self.config.include('arche.models.reference_guard')
        self.config.include('voteit.core.models.meeting')
        self.config.include('skl_owner_groups')
        request = testing.DummyRequest()
        apply_request_extensions(request)
        self.config.begin(request)
        request.root = root
        root['m'] = meeting = request.content_factories['Meeting']()
        request.meeting = meeting
        meeting[GROUPS_NAME] = request.content_factories['VGroups']()
        return root, request

    def test_setup(self):
        root, request = self._fixture()
        remember(request, 'jane')
        meeting = root['m']
        meeting.local_roles.add('jane', ROLE_MODERATOR)
        self.assertEqual(request.authenticated_userid, 'jane')
        self.failUnless(request.has_permission(MODERATE_MEETING, meeting))

    def test_add_perm_for_moderator(self):
        from skl_owner_groups.security import ADD_VGROUP
        root, request = self._fixture()
        remember(request, 'jane')
        meeting = root['m']
        meeting.local_roles.add('jane', ROLE_MODERATOR)
        #import pdb;pdb.set_trace()
        #self.failUnless(request.has_permission(ADD_VGROUP, meeting))
        self.failUnless(request.has_permission(ADD_VGROUP, meeting[GROUPS_NAME]))

    def test_context_effective(self):
        from skl_owner_groups.security import ADD_VGROUP
        root, request = self._fixture()
        remember(request, 'jane')
        meeting = root['m']
        meeting.local_roles.add('jane', ROLE_MODERATOR)
