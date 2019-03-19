# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import colander


class CreateSchema(colander.Schema):
    create = colander.SchemaNode(
        colander.Bool(),
        title="Skapa röstgrupper i detta möte?",
        default=False,
        validator=colander.Function(lambda x: x == True, msg="Inte markerad")
    )


class SettingsSchema(colander.Schema):
    enabled = colander.SchemaNode(
        colander.Bool(),
        title = "Röstgruppssystemet aktivt?",
        default=False,
    )
    title = colander.SchemaNode(
        colander.String(),
        title = "Titel",
        validator=colander.Length(min=3, max=15)
    )


#class GroupSchema(colander.Schema):
#    pass


def includeme(config):
    config.add_schema('VGroups', CreateSchema, 'create')
    config.add_schema('VGroups', SettingsSchema, 'edit')
#    config.add_schema('VGroup', GroupSchema, ['add', 'edit'])
