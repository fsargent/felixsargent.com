"""Estimate single-member approval voting results from BES 2024 wave 29 like-scores.

Usage: python approval_estimate.py BES.sav ge2024-constituency-results.json uk-westminster-hexes.json

Method
1. Respondents: BES Internet Panel wave 29 (post-election, July 2024), weighted by wt_new_W29_result.
2. Approval sets come from like-scores (0-10), not from votes, so tactical votes do not shape them.
3. For each region and each 2024 vote choice, estimate the share of those voters who approve each party,
   and the share whose sincere favourite (highest like-score) is each party.
4. Apply those rates to each GB constituency's actual 2024 vote mix. The most-approved party wins.
5. Score with the Gallagher index against sincere first-choice shares.
"""
import json
import math
import sys
from collections import defaultdict

import pyreadstat

PARTIES = ['conservative', 'labour', 'liberal-democrats', 'reform-uk', 'green', 'scottish-national-party', 'plaid-cymru']
LIKE = {
    'conservative': 'likeConW29', 'labour': 'likeLabW29', 'liberal-democrats': 'likeLDW29', 'reform-uk': 'likeBrexitPartyW29',
    'green': 'likeGrnW29', 'scottish-national-party': 'likeSNPW29', 'plaid-cymru': 'likePCW29',
}
VOTE = {1: 'conservative', 2: 'labour', 3: 'liberal-democrats', 4: 'scottish-national-party', 5: 'plaid-cymru', 7: 'green', 12: 'reform-uk',
        6: 'others', 8: 'others', 9: 'others', 11: 'others', 13: 'others'}
SHORT = {'labour': 'Lab', 'conservative': 'Con', 'reform-uk': 'Ref', 'liberal-democrats': 'LD', 'green': 'Grn',
         'scottish-national-party': 'SNP', 'plaid-cymru': 'PC', 'others': 'Oth'}
REGION_ALIASES = {'East': 'East of England'}
MIN_CELL = 40


def available(region):
    parties = ['conservative', 'labour', 'liberal-democrats', 'reform-uk', 'green']
    if region == 'Scotland':
        parties.append('scottish-national-party')
    if region == 'Wales':
        parties.append('plaid-cymru')
    return parties


def approval_rules():
    return {
        'Bullet: favourite only': lambda likes, fav: {fav} if fav else set(),
        'Approve if rated 8+': lambda likes, fav: {p for p, v in likes.items() if v >= 8} or ({fav} if fav else set()),
        'Approve if rated 7+': lambda likes, fav: {p for p, v in likes.items() if v >= 7} or ({fav} if fav else set()),
        'Approve if rated 6+': lambda likes, fav: {p for p, v in likes.items() if v >= 6} or ({fav} if fav else set()),
        'Within 2 points of own top': lambda likes, fav: {p for p, v in likes.items() if likes and v >= max(likes.values()) - 2},
    }


def main(bes_path, results_path, hexes_path):
    cols = ['generalElectionVoteW29', 'gorW29', 'wt_new_W29_result', *LIKE.values()]
    df, _ = pyreadstat.read_sav(bes_path, usecols=cols)
    df = df[df['generalElectionVoteW29'].isin(VOTE.keys()) & df['gorW29'].notna() & df['wt_new_W29_result'].notna()]

    respondents = []
    for row in df.itertuples(index=False):
        record = row._asdict()
        region = REGION_ALIASES.get(record['gorW29'], record['gorW29'])
        vote = VOTE[int(record['generalElectionVoteW29'])]
        likes = {}
        for party in available(region):
            value = record[LIKE[party]]
            if value is not None and not math.isnan(value) and value <= 10:
                likes[party] = value
        if likes:
            top = max(likes.values())
            tied = [p for p, v in likes.items() if v == top]
            favourite = vote if vote in tied else tied[0]
        else:
            favourite = vote if vote != 'others' else None
        respondents.append((region, vote, record['wt_new_W29_result'], likes, favourite))
    print(f'{len(respondents)} wave 29 respondents used')

    seats_json = json.load(open(results_path))['seats']
    region_of = {s['id']: s['regionName'] for s in json.load(open(hexes_path))['seats']}
    gb = [s for s in seats_json if not s['id'].startswith('N')]

    def rates(rule):
        cell = defaultdict(lambda: defaultdict(float))
        fav = defaultdict(lambda: defaultdict(float))
        weight = defaultdict(float)
        for region, vote, w, likes, favourite in respondents:
            approved = rule(likes, favourite)
            for key in ((region, vote), ('GB', vote)):
                weight[key] += w
                for party in approved:
                    cell[key][party] += w
                fav[key][favourite or 'others'] += w
        counts = defaultdict(int)
        for region, vote, *_ in respondents:
            counts[(region, vote)] += 1
        def lookup(region, vote):
            key = (region, vote) if counts[(region, vote)] >= MIN_CELL else ('GB', vote)
            total = weight[key] or 1
            return ({p: v / total for p, v in cell[key].items()}, {p: v / total for p, v in fav[key].items()})
        return lookup

    def run(rule):
        lookup = rates(rule)
        seats = defaultdict(int)
        sincere = defaultdict(float)
        for s in gb:
            region = region_of[s['id']]
            votes = {('others' if p in ('others', 'speaker') else p): n for p, n in s['partyVotes'].items()}
            if 'speaker' in s['partyVotes']:
                seats['others'] += 1
                for p, n in votes.items():
                    sincere[p] += n
                continue
            standing = [p for p in available(region) if s['partyVotes'].get(p, 0) > 0]
            approvals = defaultdict(float)
            for voted, n in votes.items():
                approve, favourite = lookup(region, voted)
                for party in standing:
                    approvals[party] += n * approve.get(party, 0)
                for party, share in favourite.items():
                    sincere[party] += n * share
            seats[max(approvals, key=approvals.get)] += 1
        total_votes = sum(sincere.values())
        share = {p: 100 * v / total_votes for p, v in sincere.items()}
        n_seats = len(gb)
        keys = set(share) | set(seats)
        gallagher = math.sqrt(sum((share.get(p, 0) - 100 * seats.get(p, 0) / n_seats) ** 2 for p in keys) / 2)
        return seats, share, gallagher

    actual = defaultdict(int)
    actual_votes = defaultdict(float)
    for s in gb:
        votes = s['partyVotes']
        winner = max(votes, key=votes.get)
        actual['others' if winner in ('others', 'speaker') else winner] += 1
        for p, n in votes.items():
            actual_votes['others' if p in ('others', 'speaker') else p] += n
    tv = sum(actual_votes.values())
    actual_share = {p: 100 * v / tv for p, v in actual_votes.items()}
    keys = set(actual_share) | set(actual)
    actual_g = math.sqrt(sum((actual_share.get(p, 0) - 100 * actual.get(p, 0) / len(gb)) ** 2 for p in keys) / 2)

    order = ['labour', 'conservative', 'reform-uk', 'liberal-democrats', 'green', 'scottish-national-party', 'plaid-cymru', 'others']
    header = 'Scenario'.ljust(30) + ''.join(SHORT[p].rjust(6) for p in order) + '  Gallagher'
    print(header)
    print('2024 actual (tactical votes)'.ljust(30) + ''.join(str(actual.get(p, 0)).rjust(6) for p in order) + f'  {actual_g:9.1f}')
    sincere_shares = None
    out = {'actual': {'seats': dict(actual), 'gallagher_vs_votes': actual_g, 'vote_share': actual_share}, 'scenarios': {}}
    for name, rule in approval_rules().items():
        seats, share, g = run(rule)
        sincere_shares = share
        out['scenarios'][name] = {'seats': dict(seats), 'gallagher': g}
        print(name.ljust(30) + ''.join(str(seats.get(p, 0)).rjust(6) for p in order) + f'  {g:9.1f}')
    g_vs_sincere = math.sqrt(sum((sincere_shares.get(p, 0) - 100 * actual.get(p, 0) / len(gb)) ** 2 for p in set(sincere_shares) | set(actual)) / 2)
    print('2024 actual vs sincere shares'.ljust(30) + ''.join(str(actual.get(p, 0)).rjust(6) for p in order) + f'  {g_vs_sincere:9.1f}')
    # Proportional benchmark: Sainte-Lague on sincere first-choice shares across all GB seats.
    alloc = {p: 0 for p in sincere_shares}
    for _ in range(len(gb)):
        best = max(alloc, key=lambda p: sincere_shares[p] / (2 * alloc[p] + 1))
        alloc[best] += 1
    g_pr = math.sqrt(sum((sincere_shares[p] - 100 * alloc[p] / len(gb)) ** 2 for p in alloc) / 2)
    print('Proportional (Sainte-Lague)'.ljust(30) + ''.join(str(alloc.get(p, 0)).rjust(6) for p in order) + f'  {g_pr:9.1f}')
    out['actual']['gallagher_vs_sincere'] = g_vs_sincere
    out['proportional'] = {'seats': alloc, 'gallagher': g_pr}
    out['sincere_share'] = sincere_shares
    out['gb_seats'] = len(gb)
    out['respondents'] = len(respondents)
    if len(sys.argv) > 4:
        json.dump(out, open(sys.argv[4], 'w'), indent=1)
    print('Sincere first choice %'.ljust(30) + ''.join(f'{sincere_shares.get(p, 0):6.1f}' for p in order))
    print('2024 vote %'.ljust(30) + ''.join(f'{actual_share.get(p, 0):6.1f}' for p in order))


if __name__ == '__main__':
    main(*sys.argv[1:4])
