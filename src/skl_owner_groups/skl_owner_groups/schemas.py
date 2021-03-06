# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import colander
import deform
from arche.widgets import ReferenceWidget
from pyramid.traversal import find_interface
from pyramid.traversal import resource_path

from skl_owner_groups.interfaces import IVGroup
from skl_owner_groups.interfaces import IVGroups
from skl_owner_groups.interfaces import GRUPPKATEGORIER
from skl_owner_groups.models import extract_owner_data


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
class CSVTextValidator(object):

    def __init__(self, node, kw):
        self.context = kw['context']
        assert IVGroups.providedBy(self.context)

    def __call__(self, node, value):
        try:
            potential_data = tuple(extract_owner_data(value))
        except ValueError as exc:
            raise colander.Invalid(node, exc.message)
        counter = 1
        processed_emails = set()
        processed_names = set()
        for (email, group_name) in potential_data:
            email = email.strip()
            email_validator = colander.Email("Rad %s har en ogiltig epostadress: %s" % (counter, email))
            email_validator(node, email)
            if group_name not in self.context:
                raise colander.Invalid(node, "Rad %s har ett gruppnamn som inte finns: %s" % (counter, group_name))
            if email in processed_emails:
                raise colander.Invalid(node, "Rad %s försöker lägga till en epostadress som redan använts: %s" % (counter, email))
            processed_emails.add(email)
            if group_name in processed_names:
                raise colander.Invalid(node, "Rad %s försöker lägga till ett gruppnamn som redan använts: %s" % (counter, group_name))
            processed_names.add(group_name)
            counter += 1


class AssignPotentialOwnersSchema(colander.Schema):
    description = "Potentiella ansvariga är alltså en epostadress per kommun/region (grupp i det här systemet). " \
                  "Om en användare redan finns i systemet och har en matchande epostadress så " \
                  "knyts den personen som ansvarig direkt."
    csv_text = colander.SchemaNode(
        colander.String(),
        title = "Klistra in kolumner från excel eller dylikt",
        description="Ska ha formatet <epost>   <kommunkod> <kommunnamn>, ex namn.namnsson@nynashamn.se	0192 NYNÄSHAMN. "
                    "Notera att det är tab mellan epost och kommunkod - vilket det blir automatiskt om "
                    "informationen klistras in från t.ex. Excel.",
        widget=deform.widget.TextAreaWidget(rows=10),
        validator=CSVTextValidator,
    )
    clear_all_existing = colander.SchemaNode(
        colander.Bool(),
        title = "Radera alla nuvarande potentiella ansvariga?",
        description="Påverkar inte grupper som redan har en ansvarig och inte bara en potentiell ansvarig."
    )
    overwrite_owner = colander.SchemaNode(
        colander.Bool(),
        title = "Byt ansvarig för kommuner som redan har en annan ansvarig person "
                "om den nya ansvariga finns registrerad i systemet?",
    )


@colander.deferred
class SingleGroupMembershipValidator(object):

    def __init__(self, node, kw):
        self.context = kw['context']  # The group here

    def __call__(self, node, value):
        groups = find_interface(self.context, IVGroups)
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
   groups = find_interface(context, IVGroups)
   query_params = {'path': resource_path(groups), 'type_name': 'VGroup'}
   return ReferenceWidget(query_params=query_params, multiple=False, id_attr = '__name__')


@colander.deferred
class UsableAsDelegationValidator(object):

    def __init__(self, node, kw):
        self.context = kw['context']  # The group here

    def __call__(self, node, value):
        groups = find_interface(self.context, IVGroups)
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
    groups = find_interface(context, IVGroups)
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

    def after_bind(self, node, kw):
        context = kw['context']
        if IVGroup.providedBy(context):
            groups = find_interface(context, IVGroups)
            if context.category in ('ombud', 'skl') or groups.is_delegate_for(context.__name__):
                del node['delegate_to']


class AddGroupSchema(GroupSchema):
    """ Att lägga till standardgrupperna för kommuner, regioner och SKL händer när själva gruppfoldern skapas.
        Det här formuläret är bara för att lägga till ombudsgrupper, som är en entitet att ge bort en röst till.
    """
    title = colander.SchemaNode(
        colander.String(),
        title = "Titel på ombudsorganisation",
    )
    category = colander.SchemaNode(
        colander.String(),
        default="ombud",
        widget=deform.widget.HiddenWidget(),
    )
    base_votes = colander.SchemaNode(
        colander.Int(),
        default=0,
        widget=deform.widget.HiddenWidget(),
    )

    def after_bind(self, node, kw):
        # Delegating away the vote isn't a usecase for these types of orgs
        del node['delegate_to']


def includeme(config):
    config.add_schema('VGroups', CreateSchema, 'create')
    config.add_schema('VGroups', SettingsSchema, 'edit')
    config.add_schema('VGroups', AssignPotentialOwnersSchema, 'assign')
    config.add_schema('VGroup', AddGroupSchema, 'add')
    config.add_schema('VGroup', GroupSchema, 'edit')
