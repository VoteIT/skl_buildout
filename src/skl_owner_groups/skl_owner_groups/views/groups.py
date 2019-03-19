from arche.views.base import BaseView
from voteit.core.security import VIEW

from skl_owner_groups.interfaces import IVGroups


class GroupsView(BaseView):

    def __call__(self):
        return {}


def includeme(config):
    config.add_view(
        GroupsView, context=IVGroups, permission=VIEW,
        renderer="skl_owner_groups:templates/groups.pt"
    )
