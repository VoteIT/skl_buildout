from unittest import TestCase

from arche.portlets import get_portlet_manager
from pyramid import testing
from pyramid.request import apply_request_extensions
from voteit.core.bootstrap import bootstrap_voteit
from voteit.core.models.meeting import Meeting, add_default_portlets_meeting
from voteit.core.models.site import SiteRoot
from voteit.core.testing_helpers import bootstrap_and_fixture


from skl_owner_groups.interfaces import GROUPS_NAME


class PortletSubscriberIntegrationTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.include('arche.testing')
        self.config.include('arche.portlets')

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        root = SiteRoot()
        self.config.include('skl_owner_groups.resources')
        request = testing.DummyRequest()
        apply_request_extensions(request)
        self.config.begin(request)
        request.root = root
        root['m'] = meeting = Meeting()
        add_default_portlets_meeting(meeting)
        return meeting, request

    def test_add(self):
        from skl_owner_groups.portlet import SKL_POLLS_PORTLET
        from skl_owner_groups.portlet import DEFAULT_POLLS_PORTLET
        meeting, request = self._fixture()
        self.config.include('skl_owner_groups.portlet')
        meeting[GROUPS_NAME] = request.content_factories['VGroups']()
        manager = get_portlet_manager(meeting)
        self.failUnless(manager.get_portlets('agenda_item', SKL_POLLS_PORTLET))
        self.failIf(manager.get_portlets('agenda_item', DEFAULT_POLLS_PORTLET))

    def test_enable_disable_changes_portlets(self):
        from skl_owner_groups.portlet import SKL_POLLS_PORTLET
        from skl_owner_groups.portlet import DEFAULT_POLLS_PORTLET
        meeting, request = self._fixture()
        self.config.include('skl_owner_groups.portlet')
        groups = meeting[GROUPS_NAME] = request.content_factories['VGroups']()
        manager = get_portlet_manager(meeting)
        self.failUnless(manager.get_portlets('agenda_item', SKL_POLLS_PORTLET))
        self.failIf(manager.get_portlets('agenda_item', DEFAULT_POLLS_PORTLET))
        groups.update(enabled=False)
        self.failIf(manager.get_portlets('agenda_item', SKL_POLLS_PORTLET))
        self.failUnless(manager.get_portlets('agenda_item', DEFAULT_POLLS_PORTLET))
        groups.update(enabled=True)
        self.failUnless(manager.get_portlets('agenda_item', SKL_POLLS_PORTLET))
        self.failIf(manager.get_portlets('agenda_item', DEFAULT_POLLS_PORTLET))
