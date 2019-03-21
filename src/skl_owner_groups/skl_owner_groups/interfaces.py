# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.interfaces import IBase
from arche.interfaces import IContent
from arche.interfaces import IIndexedContent

GROUPS_NAME = '_groups'
GRUPPKATEGORIER = (
    ("skl", "SKL"),
    ("kommun", "Kommun"),
    ("region", "Region"),
)


class IVGroup(IBase, IIndexedContent):
    """ A voting group. """


class IVGroups(IContent):
    """ Container for the group objects. """
