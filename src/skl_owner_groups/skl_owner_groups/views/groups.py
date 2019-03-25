from arche.views.base import BaseView
from deform_autoneed import need_lib
from voteit.core.security import VIEW
from voteit.irl.models.interfaces import IMeetingPresence

from skl_owner_groups.interfaces import IVGroups
from skl_owner_groups.security import ADD_VGROUP


class GroupsView(BaseView):

    def __call__(self):
        #need_lib('select2')
        presence = IMeetingPresence(self.request.meeting)
        return {'here_url': self.request.resource_url(self.context),
                'can_add': self.request.has_permission(ADD_VGROUP),
                'users': self.request.root['users'],
                'presence_check_open': presence.open,
                'present_userids': presence.present_userids}


def includeme(config):
    config.add_view(
        GroupsView, context=IVGroups, permission=VIEW,
        renderer="skl_owner_groups:templates/groups.pt"
    )
