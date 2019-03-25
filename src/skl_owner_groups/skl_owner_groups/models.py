# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unicodecsv as csv
#from arche.utils import AttributeAnnotations
#from pyramid.httpexceptions import HTTPBadRequest
from pyramid.path import AssetResolver
#from voteit.irl.models.elegible_voters_method import ElegibleVotersMethod
from pyramid.traversal import find_interface

from skl_owner_groups.interfaces import IVGroup
from skl_owner_groups.interfaces import IVGroups
#from skl_owner_groups.interfaces import GROUPS_NAME


_KOMMUNER_FILE = "skl_owner_groups:data/kommuner.csv"
_REGIONER_FILE = "skl_owner_groups:data/regioner.csv"



# class RepresentativesAsVoters(ElegibleVotersMethod):
#
#
#     def get_voters(self, request = None, **kw):
#         if GROUPS_NAME not in self.context:
#             raise HTTPBadRequest("Hittar inte grupper")
#         groups = self.context[GROUPS_NAME]



def create_groups(groups, request):
    """ Skapa group-objekt i ett groups-object..

        Specialregler:

        * SKL ska alltid finnas
        * Kommunen Gotland ska tas bort, eftersom regionen Gotland är ägare

        Hantera nycklar och kommunkoder som strängar

    """
    assert IVGroups.providedBy(groups)

    # Remove ordering in case it's set
    del groups.order

    factory = request.content_factories['VGroup']

    # SKL
    groups['skl'] = factory(title='SKL', category='skl')

    # Regionerna
    for (key, title) in _get_kv_from_csv(_REGIONER_FILE):
        groups[key] = factory(title=title, category='region')

    # Kommunerna - minus Gotland!
    for (key, title) in _get_kv_from_csv(_KOMMUNER_FILE):
        if key == '0980':
            continue
        groups[key] = factory(title=title, category='kommun')


def _get_kv_from_csv(asset_spec):
    resolver = AssetResolver()
    resolved = resolver.resolve(asset_spec)
    with open(resolved.abspath(), 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=str(';'))
        for row in reader:
            # Första kolumnen är tom...
            if row[1]:
                yield row[1], row[2]


if __name__ == '__main__':
    print("=== Kommuner ===")
    for (key, title) in _get_kv_from_csv(_KOMMUNER_FILE):
        print (key.ljust(10) + title)

    print("=== Regioner ===")
    for (key, title) in _get_kv_from_csv(_REGIONER_FILE):
        print (key.ljust(10) + title)


def guard_representatives(reqest, context):
    groups = find_interface(context, IVGroups)
    return [groups[x] for x in groups.is_delegate_for(context.__name__)]


def includeme(config):
    config.add_ref_guard(
        guard_representatives,
        requires=(IVGroup,),
        catalog_result=False,
        title="Är representant för en annan grupp.",
        allow_move=False
    )
