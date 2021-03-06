# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import Counter

from BTrees.OOBTree import OOBTree
from BTrees.OOBTree import OOSet
from arche.resources import Base
from arche.resources import Content
from arche.resources import LocalRolesMixin
from arche.security import ROLE_OWNER
from zope.interface import implementer
from six import string_types

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
    base_votes = 1
    naming_attr = 'uid'

    def __init__(self, **kw):
        # The default behaviour is to give the owner role to the current user. We don't want that here,
        # since owner has a special meaning to these groups.
        # Also make sure there's no conflict with local_roles / owner settings
        if 'owner' in kw:
            kw['local_roles'] = {kw.pop('owner'): ROLE_OWNER}
        kw.setdefault('local_roles', {})
        super(Group, self).__init__(**kw)

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
            # Skip all events in case resource isn't attached
            use_event = self.__parent__ is not None
            self.local_roles.remove(curr_owner, ROLE_OWNER, event=False)
            self.local_roles.add(value, ROLE_OWNER, event=use_event)

    @property
    def delegate_to(self):
        return self.__parent__.has_delegated_to(self.__name__)

    @delegate_to.setter
    def delegate_to(self, value):
        if value:
            self.__parent__.delegate_vote_to(self.__name__, value)
        else:
            self.__parent__.remove_delegation(self.__name__)

    @property
    def potential_owner(self):
        groups = self.__parent__
        # Lazy, so check if we need to bother with iteration
        if groups is None:
            raise Exception("Resource isn't attached to the resource tree")
        if self.__name__ in groups.potential_owners.values():
            for (k, v) in groups.potential_owners.items():
                if self.__name__ == v:
                    return k

    @potential_owner.setter
    def potential_owner(self, value):
        groups = self.__parent__
        groups.potential_owners[value] = self.__name__

    @potential_owner.deleter
    def potential_owner(self):
        k = self.potential_owner
        if k is not None:
            groups = self.__parent__
            del groups.potential_owners[k]


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
        self.potential_owners = OOBTree()

    def remove(self, name, send_events=True):
        """ Override removal of folders to make sure they clean up rerences.
            Removing a group that's a delegate for someone else will be blocked by the reference guard in models.
        """
        if self.has_delegated_to(name):
            self.remove_delegation(name)
        return super(Groups, self).remove(name, send_events=send_events)

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
        return frozenset(self._received_delegations.get(group_name, ()))

    def can_delegate_to(self, group_name):
        return group_name not in self._delegated_to

    def remove_delegation(self, group_name):
        to_group = self._delegated_to.get(group_name, None)
        if to_group is None:
            return
        self._received_delegations[to_group].remove(group_name)
        del self._delegated_to[group_name]
        return to_group

    def get_vote_power(self, group_name):
        """ Return the amounts of votes this group should have, based on:
            A) Did they delegate their vote somewhere?
            B) Did someone else delegate their vote here?
            C) How many base votes?
        """
        if self.has_delegated_to(group_name) is not None:
            return 0
        group = self[group_name]
        votes = group.base_votes
        for name in self.is_delegate_for(group_name):
            votes += self[name].base_votes
        return votes

    def get_users_group(self, userid):
        """ We don't need to use the catalog since we don't expect a lot of load here."""
        assert isinstance(userid, string_types)
        for x in self.values():
            if x.owner == userid:
                return x

    def get_categorized_vote_power(self, userid):
        """ All the kinds of vote power this user has. This doesn't check if a user is actually a voter."""
        counter = Counter()
        primary_group = self.get_users_group(userid)
        if primary_group is None or self.has_delegated_to(primary_group.__name__):
            return counter
        counter[primary_group.category] += primary_group.base_votes
        for name in self.is_delegate_for(primary_group.__name__):
            group = self[name]
            counter[group.category] += group.base_votes
        return counter

    def add_potential_owner(self, email, group_name):
        if group_name not in self:
            raise ValueError("Ingen grupp med namnet '%s' finns" % group_name)
        self.potential_owners[email] = group_name


def includeme(config):
    config.add_content_factory(Group, addable_to='VGroups')
    config.add_content_factory(Groups)
