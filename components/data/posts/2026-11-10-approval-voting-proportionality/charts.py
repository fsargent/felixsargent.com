"""Draw the fallback PNG charts for the post. Usage: python charts.py results.json congruence.json OUTPUT_DIR"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

results = json.load(open(sys.argv[1]))
congruence = json.load(open(sys.argv[2]))
out = Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)

SURFACE = '#fcfcfb'
INK = '#0b0b0b'
INK_2 = '#52514e'
GRID = '#e4e3df'
BLUE = '#2a78d6'

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.size': 11, 'text.color': INK, 'axes.labelcolor': INK_2,
    'xtick.color': INK_2, 'ytick.color': INK, 'axes.edgecolor': GRID, 'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE,
})

NAMES = [
    ('First Past the Post (2024 result)', '2024 actual (First Past the Post)', None),
    ('Approval, favorite only', 'Approval: Bullet: favourite only', 'Bullet: favourite only'),
    ('Approval, rated 8 or more', 'Approval: Approve if rated 8+', 'Approve if rated 8+'),
    ('Approval, rated 7 or more', 'Approval: Approve if rated 7+', 'Approve if rated 7+'),
    ('Approval, rated 6 or more', 'Approval: Approve if rated 6+', 'Approve if rated 6+'),
    ('Approval, within 2 of favorite', 'Approval: Within 2 points of own top', 'Within 2 points of own top'),
    ('Proportional allocation', 'Proportional allocation', None),
]


def tidy(ax, axis='x'):
    for side in ('top', 'right', 'left'):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis='y', length=0)
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


# Chart 1: the Gallagher index by scenario.
gallagher = []
for label, _, key in NAMES:
    if label.startswith('First Past'):
        gallagher.append(results['actual']['gallagher_vs_sincere'])
    elif label.startswith('Proportional'):
        gallagher.append(results['proportional']['gallagher'])
    else:
        gallagher.append(results['scenarios'][key]['gallagher'])
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
labels = [n[0] for n in NAMES][::-1]
values = gallagher[::-1]
bars = ax.barh(labels, values, color=BLUE, height=0.55)
for bar, value in zip(bars, values):
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2, f'{value:.0f}', va='center', fontsize=10)
ax.set_xlim(0, 40)
ax.set_xlabel('Gallagher index (0 means seats match first choices)')
tidy(ax)
fig.tight_layout(rect=(0, 0, 1, 0.92))
fig.text(0.02, 0.96, 'Approval voting stays as disproportional as First Past the Post', fontsize=12.5, fontweight='bold', va='top')
fig.savefig(out / 'gallagher.png')
plt.close(fig)

# Chart 2: median MP against the median voter on the left-right scale.
fig, ax = plt.subplots(figsize=(8, 4.6), dpi=200)
voter = congruence['voter_median']
rows = [(label, congruence['scenarios'][ckey]['median_mp']) for label, ckey, _ in NAMES][::-1]
ax.axvline(voter, color=INK_2, linewidth=1.5, linestyle=(0, (4, 3)))
ax.text(voter + 0.1, -0.55, f'Median voter ({voter:.0f})', color=INK_2, fontsize=9.5, va='center')
for i, (label, median) in enumerate(rows):
    ax.plot([median, voter], [i, i], color=GRID, linewidth=3, solid_capstyle='round', zorder=1)
    ax.scatter([median], [i], s=90, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.text(median - 0.15, i, f'{median:.1f}', ha='right', va='center', fontsize=10)
ax.set_yticks(range(len(rows)), [r[0] for r in rows])
positions = congruence['party_position']
short = {'green': 'Grn', 'labour': 'Lab', 'liberal-democrats': 'LD', 'conservative': 'Con', 'reform-uk': 'Ref'}
for party, name in short.items():
    align = {'green': 'right', 'labour': 'left'}.get(party, 'center')
    ax.annotate(name, xy=(positions[party], len(rows) - 0.5), xytext=(positions[party], len(rows) + 0.05),
                ha=align, fontsize=9, color=INK_2, arrowprops={'arrowstyle': '-', 'color': GRID})
ax.set_xlim(0, 10)
ax.set_ylim(-0.9, len(rows) + 0.5)
ax.set_xlabel('Left (0) to right (10). Party labels mark where voters place each party.')
tidy(ax)
fig.tight_layout(rect=(0, 0, 1, 0.92))
fig.text(0.02, 0.96, 'Proportional allocation puts the median MP nearer the median voter', fontsize=12.5, fontweight='bold', va='top')
fig.savefig(out / 'median-mp.png')
plt.close(fig)
print('wrote', sorted(p.name for p in out.iterdir()))
