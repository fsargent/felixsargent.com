"""Satisfaction and left-right congruence for each scenario, from BES 2024.

Usage: python congruence.py BES.sav ge2024-constituency-results.json uk-westminster-hexes.json OUT.json

Builds on approval_estimate.py (same respondents, cells and approval rules), and adds:
- Party positions: mean placement of each party on the 0-10 left-right scale, wave 28 (June 2024).
- Voter positions: self-placement, wave 29 (fallback wave 28).
- Satisfaction: like-score (0-10) voters give their local MP's party, and the chamber as a whole.
- Congruence: median MP vs median voter, spread, Wasserstein distance between voter and MP
  distributions, and mean distance from each voter to their own MP.
"""
import json
import math
import sys
from collections import defaultdict

import pyreadstat

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from approval_estimate import LIKE, VOTE, REGION_ALIASES, MIN_CELL, available, approval_rules

LR_PARTY = {'conservative': 'lrConW28', 'labour': 'lrLabW28', 'liberal-democrats': 'lrLDW28', 'reform-uk': 'lrBrexitW28',
            'green': 'lrgreensW28', 'scottish-national-party': 'lrSNPW28', 'plaid-cymru': 'lrPCW28'}
GRID = [x / 10 for x in range(0, 101)]


def valid(value, top=10):
    return value is not None and not (isinstance(value, float) and math.isnan(value)) and 0 <= value <= top


def main(bes_path, results_path, hexes_path, out_path):
    cols = ['generalElectionVoteW29', 'gorW29', 'wt_new_W29_result', 'leftRightW29', 'leftRightW28', *LIKE.values(), *LR_PARTY.values()]
    df, _ = pyreadstat.read_sav(bes_path, usecols=cols)

    # Party positions: mean placement by everyone who placed the party in wave 28.
    position = {}
    for party, col in LR_PARTY.items():
        values = [v for v in df[col].tolist() if valid(v)]
        position[party] = sum(values) / len(values)

    df = df[df['generalElectionVoteW29'].isin(VOTE.keys()) & df['gorW29'].notna() & df['wt_new_W29_result'].notna()]
    respondents = []
    for row in df.itertuples(index=False):
        r = row._asdict()
        region = REGION_ALIASES.get(r['gorW29'], r['gorW29'])
        vote = VOTE[int(r['generalElectionVoteW29'])]
        likes = {p: r[LIKE[p]] for p in available(region) if valid(r[LIKE[p]])}
        if likes:
            top = max(likes.values())
            tied = [p for p, v in likes.items() if v == top]
            fav = vote if vote in tied else tied[0]
        else:
            fav = vote if vote != 'others' else None
        self_lr = r['leftRightW29'] if valid(r['leftRightW29']) else (r['leftRightW28'] if valid(r['leftRightW28']) else None)
        respondents.append({'region': region, 'vote': vote, 'w': r['wt_new_W29_result'], 'likes': likes, 'fav': fav, 'lr': self_lr})

    seats_json = json.load(open(results_path))['seats']
    region_of = {s['id']: s['regionName'] for s in json.load(open(hexes_path))['seats']}
    gb = [s for s in seats_json if not s['id'].startswith('N')]

    # Per-cell summaries that do not depend on the approval rule.
    counts = defaultdict(int)
    acc = defaultdict(lambda: {'w': 0.0, 'like': defaultdict(float), 'like_w': defaultdict(float), 'dist': defaultdict(float),
                               'dist_w': 0.0, 'hist': [0.0] * 11, 'fav': defaultdict(float)})
    for p in respondents:
        counts[(p['region'], p['vote'])] += 1
        for key in ((p['region'], p['vote']), ('GB', p['vote'])):
            a = acc[key]
            a['w'] += p['w']
            a['fav'][p['fav'] or 'others'] += p['w']
            for party, like in p['likes'].items():
                a['like'][party] += p['w'] * like
                a['like_w'][party] += p['w']
            if p['lr'] is not None:
                a['dist_w'] += p['w']
                a['hist'][int(round(p['lr']))] += p['w']
                for party, pos in position.items():
                    a['dist'][party] += p['w'] * abs(p['lr'] - pos)

    def cell(region, vote):
        return acc[(region, vote) if counts[(region, vote)] >= MIN_CELL else ('GB', vote)]

    def mean_like(c, party):
        return c['like'][party] / c['like_w'][party] if c['like_w'][party] else 0.0

    # Electorate: left-right distribution and sincere first-choice shares, rebuilt from each seat's vote mix.
    voter_hist = [0.0] * 11
    sincere = defaultdict(float)
    for s in gb:
        for voted, n in s['partyVotes'].items():
            voted = 'others' if voted in ('others', 'speaker') else voted
            c = cell(region_of[s['id']], voted)
            if c['dist_w']:
                for i in range(11):
                    voter_hist[i] += n * c['hist'][i] / c['dist_w']
            for party, share in c['fav'].items():
                sincere[party] += n * share / c['w']
    total = sum(sincere.values())
    sincere_share = {p: v / total for p, v in sincere.items()}

    def cdf_from_hist(hist):
        t = sum(hist)
        cum, out = 0.0, []
        for x in GRID:
            out.append(sum(h for i, h in enumerate(hist) if i <= x) / t)
        return out

    def weighted_median(points):
        points = sorted(points)
        t = sum(w for _, w in points)
        run = 0.0
        for x, w in points:
            run += w
            if run >= t / 2:
                return x
        return points[-1][0]

    def sd(points):
        t = sum(w for _, w in points)
        m = sum(x * w for x, w in points) / t
        return math.sqrt(sum(w * (x - m) ** 2 for x, w in points) / t)

    voter_points = [(i, h) for i, h in enumerate(voter_hist)]
    voter_cdf = cdf_from_hist(voter_hist)

    def chamber_stats(seat_counts):
        mp_points = [(position[p], n) for p, n in seat_counts.items() if p in position and n > 0]
        t = sum(n for _, n in mp_points)
        mp_cdf = [sum(n for x, n in mp_points if x <= g) / t for g in GRID]
        wasserstein = sum(abs(a - b) for a, b in zip(voter_cdf, mp_cdf)) * (GRID[1] - GRID[0])
        # Chamber satisfaction: the like-score the average voter gives a randomly chosen MP's party.
        chamber_like = 0.0
        votes_total = 0.0
        for s in gb:
            for voted, n in s['partyVotes'].items():
                voted = 'others' if voted in ('others', 'speaker') else voted
                c = cell(region_of[s['id']], voted)
                chamber_like += n * sum(seat_counts.get(p, 0) / t * mean_like(c, p) for p in position)
                votes_total += n
        return {
            'median_mp': weighted_median(mp_points), 'sd_mp': sd(mp_points),
            'median_gap': abs(weighted_median(mp_points) - weighted_median(voter_points)),
            'wasserstein': wasserstein, 'chamber_like': chamber_like / votes_total,
        }

    def local_stats(winners):
        like_sum = dist_sum = votes_total = dist_votes = 0.0
        for s, winner in zip(gb, winners):
            if winner not in position:
                continue
            for voted, n in s['partyVotes'].items():
                voted = 'others' if voted in ('others', 'speaker') else voted
                c = cell(region_of[s['id']], voted)
                like_sum += n * mean_like(c, winner)
                votes_total += n
                if c['dist_w']:
                    dist_sum += n * c['dist'][winner] / c['dist_w']
                    dist_votes += n
        return {'local_like': like_sum / votes_total, 'local_distance': dist_sum / dist_votes}

    def approval_winners(rule):
        cell_rate = defaultdict(lambda: defaultdict(float))
        cell_w = defaultdict(float)
        for p in respondents:
            approved = rule(p['likes'], p['fav'])
            for key in ((p['region'], p['vote']), ('GB', p['vote'])):
                cell_w[key] += p['w']
                for party in approved:
                    cell_rate[key][party] += p['w']
        winners = []
        for s in gb:
            region = region_of[s['id']]
            if 'speaker' in s['partyVotes']:
                winners.append('speaker')
                continue
            standing = [p for p in available(region) if s['partyVotes'].get(p, 0) > 0]
            score = defaultdict(float)
            for voted, n in s['partyVotes'].items():
                key = (region, voted) if counts[(region, voted)] >= MIN_CELL else ('GB', voted)
                for party in standing:
                    score[party] += n * cell_rate[key][party] / (cell_w[key] or 1)
            winners.append(max(score, key=score.get))
        return winners

    def tally(winners):
        out = defaultdict(int)
        for w in winners:
            out[w] += 1
        return dict(out)

    results = {'party_position': position, 'voter_median': weighted_median(voter_points), 'voter_sd': sd(voter_points), 'scenarios': {}}

    actual = [max(s['partyVotes'], key=s['partyVotes'].get) for s in gb]
    scenarios = [('2024 actual (First Past the Post)', actual)]
    scenarios += [(f'Approval: {name}', approval_winners(rule)) for name, rule in approval_rules().items()]
    for name, winners in scenarios:
        seats = tally(winners)
        results['scenarios'][name] = {'seats': seats, **chamber_stats(seats), **local_stats(winners)}

    # Proportional benchmark: Sainte-Lague on sincere first-choice shares, parties only.
    parties = {p: v for p, v in sincere_share.items() if p in position}
    alloc = {p: 0 for p in parties}
    for _ in range(len(gb)):
        best = max(alloc, key=lambda p: parties[p] / (2 * alloc[p] + 1))
        alloc[best] += 1
    pr = {'seats': alloc, **chamber_stats(alloc)}
    # Best-represented party: like-score for the voter's best-liked party that holds seats, and distance to the nearest one.
    like_sum = dist_sum = wsum = dwsum = 0.0
    for p in respondents:
        held = [q for q in p['likes'] if alloc.get(q, 0) > 0]
        if held:
            like_sum += p['w'] * max(p['likes'][q] for q in held)
            wsum += p['w']
        if p['lr'] is not None:
            dist_sum += p['w'] * min(abs(p['lr'] - position[q]) for q in alloc if alloc[q] > 0)
            dwsum += p['w']
    pr['best_party_like'] = like_sum / wsum
    pr['nearest_party_distance'] = dist_sum / dwsum
    results['scenarios']['Proportional allocation'] = pr

    json.dump(results, open(out_path, 'w'), indent=1)
    print('party positions', {k: round(v, 2) for k, v in position.items()})
    print(f"voters: median {results['voter_median']}, sd {results['voter_sd']:.2f}")
    head = f"{'Scenario':40}{'localLike':>10}{'chamberLike':>12}{'medianMP':>9}{'gap':>6}{'sdMP':>6}{'EMD':>6}{'localDist':>10}"
    print(head)
    for name, r in results['scenarios'].items():
        local_like = r.get('local_like', r.get('best_party_like'))
        local_dist = r.get('local_distance', r.get('nearest_party_distance'))
        print(f"{name:40}{local_like:10.2f}{r['chamber_like']:12.2f}{r['median_mp']:9.2f}{r['median_gap']:6.2f}{r['sd_mp']:6.2f}{r['wasserstein']:6.2f}{local_dist:10.2f}")


if __name__ == '__main__':
    main(*sys.argv[1:5])
