from unittest import TestCase

from pyramid import testing
from pyramid.httpexceptions import HTTPBadRequest
from pyramid.request import apply_request_extensions
from voteit.core.models.meeting import Meeting
from voteit.core.testing_helpers import bootstrap_and_fixture
from voteit.irl.models.interfaces import IElegibleVotersMethod, IMeetingPresence
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
