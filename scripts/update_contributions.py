#!/usr/bin/env python3
"""Draw the last year of contributions as animated SVGs, dark and light.

Standard library only. The SVGs use CSS animation because GitHub shows them
through <img>, where scripts never run. Needs GITHUB_TOKEN for the GraphQL API.
"""

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

USER = "Ryuu-x"
ASSETS = Path(__file__).resolve().parent.parent / "assets"

CELL = 11
PITCH = 14
LEFT = 34
TOP = 48
SWEEP_WIDTH = 150
SWEEP_SECONDS = 7

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionLevel } }
      }
    }
  }
}
"""

LEVELS = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]

THEMES = {
    "dark": {
        "text": "#c9d1d9",
        "muted": "#8b949e",
        "cells": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "sweep": "#c9a2ff",
        "sweep_opacity": "0.85",
    },
    "light": {
        "text": "#1f2328",
        "muted": "#59636e",
        "cells": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "sweep": "#6e40c9",
        "sweep_opacity": "0.6",
    },
}


def fetch_calendar():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is required to read the contribution calendar")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-updater",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        sys.exit(f"GraphQL error: {result['errors']}")
    return result["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def column_x(index):
    return LEFT + index * PITCH


def row_y(day):
    # isoweekday: Monday 1 ... Sunday 7. The graph starts on Sunday.
    return TOP + (day.isoweekday() % 7) * PITCH


def month_labels(weeks, colour):
    starts = []
    previous = None
    for index, week in enumerate(weeks):
        first = date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != previous:
            starts.append((index, first))
            previous = first.month
    # A month that only clips the edge of the graph has no room for its label.
    if len(starts) > 1 and starts[1][0] - starts[0][0] < 3:
        starts.pop(0)
    return [
        f'<text x="{column_x(index)}" y="{TOP - 8}" fill="{colour}">{first:%b}</text>'
        for index, first in starts
    ]


def render(calendar, theme):
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    width = column_x(len(weeks)) + 4
    height = TOP + 7 * PITCH + 4
    # Fixed rather than per-column delays stay small; 20 steps read as a wave.
    steps = 20
    cells = []
    active = []
    for index, week in enumerate(weeks):
        step = index * steps // len(weeks)
        for entry in week["contributionDays"]:
            day = date.fromisoformat(entry["date"])
            level = LEVELS.index(entry["contributionLevel"])
            x, y = column_x(index), row_y(day)
            shape = f'x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2"'
            cells.append(f'<rect class="s{step}" {shape} fill="{theme["cells"][level]}"/>')
            if level:
                active.append(f"<rect {shape}/>")

    delays = "".join(
        f".s{step}{{animation-delay:{step * 0.04:.2f}s}}" for step in range(steps)
    )
    travel = width + SWEEP_WIDTH
    days = " ".join(
        f'<text x="{LEFT - 8}" y="{TOP + row * PITCH + 9}" text-anchor="end" '
        f'fill="{theme["muted"]}">{name}</text>'
        for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{total} contributions in the last year">
<style>
text{{font:11px -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
.total{{font-size:15px;font-weight:600}}
rect[class]{{transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.2,1.5,.4,1) both}}
{delays}
.band{{animation:sweep {SWEEP_SECONDS}s 1.2s linear infinite;transform:translateX(-{SWEEP_WIDTH}px)}}
@keyframes pop{{from{{opacity:0;transform:scale(.2)}}to{{opacity:1;transform:scale(1)}}}}
@keyframes sweep{{from{{transform:translateX(-{SWEEP_WIDTH}px)}}to{{transform:translateX({travel - SWEEP_WIDTH}px)}}}}
@media (prefers-reduced-motion:reduce){{rect[class],.band{{animation:none}}}}
</style>
<defs>
<linearGradient id="g"><stop offset="0" stop-color="{theme['sweep']}" stop-opacity="0"/><stop offset=".5" stop-color="{theme['sweep']}" stop-opacity="{theme['sweep_opacity']}"/><stop offset="1" stop-color="{theme['sweep']}" stop-opacity="0"/></linearGradient>
<clipPath id="active">{"".join(active)}</clipPath>
</defs>
<text class="total" x="0" y="16" fill="{theme['text']}">{total} contributions in the last year</text>
{"".join(month_labels(weeks, theme["muted"]))}
{days}
{"".join(cells)}
<g clip-path="url(#active)"><g class="band"><rect x="0" y="{TOP}" width="{SWEEP_WIDTH}" height="{7 * PITCH}" fill="url(#g)" style="animation:none"/></g></g>
</svg>
"""


def main():
    calendar = fetch_calendar()
    ASSETS.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        path = ASSETS / f"contributions-{name}.svg"
        path.write_text(render(calendar, theme), encoding="utf-8", newline="\n")
    print(f"{calendar['totalContributions']} contributions drawn")


if __name__ == "__main__":
    main()
