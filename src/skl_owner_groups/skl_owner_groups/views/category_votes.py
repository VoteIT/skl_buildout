# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import Counter
from decimal import Decimal

from arche.views.base import BaseView
from pyramid.view import view_config
from skl_owner_groups.interfaces import GROUPS_NAME, GRUPPKATEGORIER
from voteit.core.models.interfaces import IPoll
from voteit.core.security import VIEW
from voteit.irl.models.interfaces import IMeetingPresence

from skl_owner_groups.models import analyze_vote_distribution, groups_exist
from skl_owner_groups.models import get_total_categorized_vote_power


@view_config(context=IPoll, name="_category_votets", permission=VIEW,
             renderer="skl_owner_groups:templates/category_votes.pt")
class CategoryVotes(BaseView):

    def __call__(self):
        if not groups_exist(self.context, self.request):
            return {'error': "Inga grupper existerar i mötet."}
        presence = IMeetingPresence(self.request.meeting)
        if presence.open:
            return {'error': "Närvarokontrollen är öppen, den här vyn fungerar inte korrekt då. "
                                    "Avsluta kontrollen först."}
        if not hasattr(self, 'method_%s' % self.context.poll_plugin):
            return {'error': "Omröstningsmetoden kan inte analyseras med detta verktyg. "
                             "(metoden %s saknas)" % self.context.poll_plugin}
        self.total_vote_power = get_total_categorized_vote_power(self.request.meeting[GROUPS_NAME])
        self.hashed_votes, self.categorized_votes = analyze_vote_distribution(self.context)
        view_cats = list(GRUPPKATEGORIER)
        # Ta bort ombud
        view_cats.pop(-1)
        # Lägg till total
        view_cats.append(('total', 'Total'))
        self.view_cats = view_cats
        return {
            'view_cats': view_cats,
        }

    def vote_count(self, uid):
        return getattr(self, "method_%s" % self.context.poll_plugin)(uid)

    def method_combined_simple(self, uid):
        pass

    def method_majority_poll(self, uid):
        use_hash = None
        for (hash, vote_data) in self.hashed_votes.items():
            if vote_data == {'proposal': uid}:
                use_hash = hash
                break
        # Hash may not match anything
        counter = Counter()
        for (cat, votemap) in self.categorized_votes.items():
            if use_hash in votemap:
                counter[cat] += votemap[use_hash]
                counter['total'] += votemap[use_hash]
        return counter

    def calc_perc(self, num, total):
        if total:
            return int(round(100 * Decimal(num) / Decimal(total), 0))
        return 0

    def percentages(self, vote_count):
        results = {}
        for cat, title in self.view_cats:
            results[cat] = self.calc_perc(vote_count[cat], self.total_vote_power[cat])
        return results

    def colouring(self, percentages):
        results = {}
        results['skl'] = 'success'
        # The 50 bar is really the case for this meeting, it's not a mistake!
        if percentages['kommun'] > 32 and percentages['region'] > 32 and percentages['total'] >= 50:
            results['total'] = 'success'
        else:
            results['total'] = 'danger'
        for cat in ('kommun', 'region'):
            if percentages[cat] > 32:
                results[cat] = 'success'
            else:
                results[cat] = 'danger'
        return results


def includeme(config):
    config.scan(__name__)
