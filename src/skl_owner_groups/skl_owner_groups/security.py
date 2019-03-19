# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from voteit.core import security as vcsec


# Permissiions
ADD_VGROUP = "Add VGroup"
EDIT_VGROUP = "Edit VGroup"


def includeme(config):
    acl = config.registry.acl
    meeting_default = acl['Meeting:default']
    meeting_default.add(vcsec.ROLE_MODERATOR, [ADD_VGROUP, EDIT_VGROUP])
    meeting_default.add(vcsec.ROLE_ADMIN, [ADD_VGROUP, EDIT_VGROUP])
