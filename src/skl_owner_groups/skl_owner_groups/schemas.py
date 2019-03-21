# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import colander
import deform
from arche.widgets import ReferenceWidget
from arche.widgets import UserReferenceWidget
from pyramid.traversal import resource_path
from skl_owner_groups.interfaces import IVGroups, GRUPPKATEGORIER


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
        title="Röstgruppssystemet aktivt?",
        default=False,
    )
    title = colander.SchemaNode(
        colander.String(),
        title="Titel",
        validator=colander.Length(min=3, max=15)
    )


@colander.deferred
class SingleGroupMembershipValidator(object):

    def __init__(self, node, kw):
        self.context = kw['context']  # The group here

    def __call__(self, node, value):
        groups = self.context.__parent__
        for group in groups.values():
            if group is self.context:
                continue
            if group.owner == value:
                raise colander.Invalid(node,
                                       "AnvändarID '{}' är redan ansvarig för '{}'".format(value, group.title)
                                       )


@colander.deferred
def local_groups_reference(node, kw):
   context = kw['context']
   groups = context.__parent__
   query_params = {'path': resource_path(groups), 'type_name': 'VGroup'}
   return ReferenceWidget(query_params=query_params, multiple=False, id_attr = '__name__')


@colander.deferred
class UsableAsDelegationValidator(object):

    def __init__(self, node, kw):
        self.context = kw['context']  # The group here

    def __call__(self, node, value):
        groups = self.context.__parent__
        if value not in groups:
            raise colander.Invalid(node, "Finns ingen grupp med det namnet")
        group = groups[value]
        if group.delegate_to:
            raise colander.Invalid(node, "%s har delegerat sin rösträtt och kan "
                                         "därför inte ta emot röster från andra." % group.title)
        if self.context.__name__ == value:
            raise colander.Invalid(node, "Gruppen kan inte vara ombud för sig själv.")


@colander.deferred
def meeting_users_widget(node, kw):
    """ We're simply going to guess that anyone with a local role within the meeting is an eligible candidate.
        It's okay to add things that the validator will block, since that at least explains why it won't work.
    """
    request = kw['request']
    meeting = request.meeting
    root = request.root
    values = [('', '(Ingen)')]
    for userid in meeting.local_roles.keys():
        user = root['users'].get(userid, None)
        if user is None:
            continue
        values.append((userid, "{} ({})".format(user.title, userid)))
    return deform.widget.Select2Widget(multiple=False, values=values)


def _get_categorized_groups(groups):
    assert IVGroups.providedBy(groups)
    results = {}
    for group in groups.get_sorted_values():
        assert group.category, "%s has no category" % group.title
        found = results.setdefault(group.category, [])
        found.append(group)
    return results


@colander.deferred
def delegation_widget(node, kw):
    titles = dict(GRUPPKATEGORIER)
    context = kw['context']
    groups = context.__parent__
    values = [('', '(Ingen)')]
    for (category, items) in _get_categorized_groups(groups).items():
        title = titles.get(category, '(Okänd)')
        cat_values = [(x.__name__, x.title) for x in items]
        optgroup = deform.widget.OptGroup(title, *cat_values)
        values.append(optgroup)
    return deform.widget.Select2Widget(multiple=False, values=values)


class GroupSchema(colander.Schema):
    owner = colander.SchemaNode(
        colander.String(),
        title="Ansvarig användare",
        description="Anges som användarID, du kan söka på namn också.",
        widget=meeting_users_widget,
        validator=SingleGroupMembershipValidator,
        missing="",
    )
    delegate_to = colander.SchemaNode(
        colander.String(),
        title="Använd denna grupp som ombud",
        description="Måste vara en grupp som inte använder ett annat ombud",
        missing="",
        validator=UsableAsDelegationValidator,
        widget=delegation_widget
    )


def includeme(config):
    config.add_schema('VGroups', CreateSchema, 'create')
    config.add_schema('VGroups', SettingsSchema, 'edit')
    config.add_schema('VGroup', GroupSchema, ['add', 'edit'])
