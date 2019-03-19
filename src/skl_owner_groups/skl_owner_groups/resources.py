# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.resources import Base
from arche.resources import Content
from arche.resources import LocalRolesMixin
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

    def __acl__(self):
        # Traverse
        raise AttributeError()


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


def includeme(config):
    config.add_content_factory(Group)  # Don't specify as manually addable!
    config.add_content_factory(Groups)
