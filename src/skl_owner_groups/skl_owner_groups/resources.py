# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from BTrees.OOBTree import OOBTree, OOSet
from arche.resources import Base
from arche.resources import Content
from arche.resources import LocalRolesMixin
from arche.security import ROLE_OWNER
from zope.interface import implementer

from skl_owner_groups.security import ADD_VGROUP
from skl_owner_groups.interfaces import IVGroup
from skl_owner_groups.interfaces import IVGroups


@implementer(IVGroup)
class Group(Base, LocalRolesMixin):
    type_name = "VGroup"
    type_title = "Grupp"
    type_description = ""
    add_permission = ADD_VGROUP
    title = ""
    category = ""
    category_code = ""
    base_votes = 1

    @property
    def owner(self):
        """ Should only be one single owner for each group. """
        for (userid, roles) in self.local_roles.items():
            if ROLE_OWNER in roles:
                return userid

    @owner.setter
    def owner(self, value):
        """"""
        curr_owner = self.owner
        if value != curr_owner:
            self.local_roles.remove(curr_owner, ROLE_OWNER, event=False)
            self.local_roles.add(value, ROLE_OWNER, event=True)

    @property
    def delegate_to(self):
        return self.__parent__.has_delegated_to(self.__name__)

    @delegate_to.setter
    def delegate_to(self, value):
        if value:
            self.__parent__.delegate_vote_to(self.__name__, value)
        else:
            self.__parent__.remove_delegation(self.__name__)


@implementer(IVGroups)
class Groups(Content):
    """ Vote groups folder, contains group resources """
    type_name = "VGroups"
    type_title = "Grupper"
    type_description = ""
    add_permission = "Add %s" % type_name
    css_icon = "glyphicon glyphicon-folder-open"
    nav_visible = True
    listing_visible = True
    search_visible = False
    enabled = True
    title = "Grupper"

    def __init__(self, **kw):
        super(Groups, self).__init__(**kw)
        self._received_delegations = OOBTree()
        self._delegated_to = OOBTree()

    def get_sorted_values(self):
        """ Return all contained Group object sorted on title. """
        return sorted(self.values(), key=lambda x:x.title.lower())

    def delegate_vote_to(self, from_group, to_group):
        if not self.can_delegate_to(to_group):
            raise Exception("Kan inte delegera till %s" % to_group)
        if self.has_delegated_to(from_group):
            self.remove_delegation(from_group)
        if to_group not in self._received_delegations:
            self._received_delegations[to_group] = OOSet()
        self._received_delegations[to_group].add(from_group)
        self._delegated_to[from_group] = to_group

    def has_delegated_to(self, group_name):
        return self._delegated_to.get(group_name, None)

    def is_delegate_for(self, group_name):
        group_names = self._received_delegations.get(group_name, None)
        if group_names:
            return frozenset(group_names)
        return frozenset()

    def can_delegate_to(self, group_name):
        return group_name not in self._delegated_to

    def remove_delegation(self, group_name):
        to_group = self._delegated_to.get(group_name, None)
        if to_group is None:
            return
        self._received_delegations[to_group].remove(group_name)
        del self._delegated_to[group_name]
        return to_group

# FIXME: Write method to figure out active users and their vote power


def includeme(config):
    config.add_content_factory(Group)  # Don't specify as manually addable!
    config.add_content_factory(Groups)
