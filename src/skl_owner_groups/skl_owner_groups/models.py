# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import unicodecsv as csv

from pyramid.path import AssetResolver

from skl_owner_groups.interfaces import IVGroups


_KOMMUNER_FILE = "skl_owner_groups:data/kommuner.csv"
_REGIONER_FILE = "skl_owner_groups:data/regioner.csv"


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
