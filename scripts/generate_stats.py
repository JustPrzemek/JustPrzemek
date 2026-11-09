#!/usr/bin/env python3
"""Builds assets/terminal.svg: static intro from the template + live GitHub stats."""

import json
import os
import re
import sys
import urllib.request
from datetime import date
from xml.sax.saxutils import escape

LOGIN = os.environ.get("GH_LOGIN", "JustPrzemek")
TOKEN = os.environ["GITHUB_TOKEN"]
TEMPLATE = os.environ.get("TEMPLATE", "assets/terminal.template.svg")
OUT = os.environ.get("OUT", "assets/terminal.svg")

LINE = 24        # gap between output lines
BLOCK = 36       # gap before the next command
STEP = 0.15      # delay between output lines
TYPE_TIME = 0.7  # time to "type" a command

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""


def fetch():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-stats"},
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        sys.exit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def top_languages(repos, limit=5):
    totals = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            color = edge["node"]["color"] or "#8b949e"
            size, _ = totals.get(name, (0, color))
            totals[name] = (size + edge["size"], color)
    grand = sum(size for size, _ in totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: kv[1][0], reverse=True)[:limit]
    return [(name, color, size / grand * 100) for name, (size, color) in ranked]


def current_streak(days):
    streak = 0
    today = date.today().isoformat()
    for day in reversed(days):
        if day["contributionCount"] > 0:
            streak += 1
        elif day["date"] != today:  # no commits yet today doesn't break the streak
            break
    return streak


def level_color(count, max_count):
    if count == 0:
        return "#161b22"
    ratio = count / max_count
    if ratio <= 0.25:
        return "#0e4429"
    if ratio <= 0.5:
        return "#006d32"
    if ratio <= 0.75:
        return "#26a641"
    return "#39d353"


PROMPT = '<tspan class="user">przemek@github</tspan>:<tspan class="path">~</tspan>$ '


def command(y, cmd, delay):
    return (f'<text x="24" y="{y}" class="c" style="animation-delay:{delay:.2f}s">'
            f'{PROMPT}<tspan class="cmd">{escape(cmd)}</tspan></text>')


def build_dynamic(user, y, delay):
    repos = user["repositories"]
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [d for w in calendar["weeks"] for d in w["contributionDays"]]

    stats = [
        [("repos", repos["totalCount"]),
         ("stars", sum(r["stargazerCount"] for r in repos["nodes"])),
         ("followers", user["followers"]["totalCount"])],
        [("commits", user["contributionsCollection"]["totalCommitContributions"]),
         ("PRs", user["pullRequests"]["totalCount"]),
         ("streak", f"{current_streak(days)}d")],
    ]

    parts = []

    # $ gh stats
    y += BLOCK
    delay += 0.4
    parts.append(command(y, f"gh stats {LOGIN}", delay))
    delay += TYPE_TIME
    for row in stats:
        y += LINE
        cells = "".join(
            f'<tspan x="{24 + i * 270}" class="muted">{label:<11}</tspan>'
            f'<tspan class="hl bold">{value}</tspan>'
            for i, (label, value) in enumerate(row)
        )
        parts.append(f'<text y="{y}" class="l" style="animation-delay:{delay:.2f}s">{cells}</text>')
        delay += STEP

    # $ gh langs
    y += BLOCK
    delay += 0.4
    parts.append(command(y, "gh langs --top 5", delay))
    delay += TYPE_TIME
    for name, color, pct in top_languages(repos["nodes"]):
        y += LINE
        bar = max(4, round(320 * pct / 100))
        parts.append(
            f'<g class="l" style="animation-delay:{delay:.2f}s">'
            f'<text x="24" y="{y}">{escape(name)}</text>'
            f'<rect x="170" y="{y - 11}" width="320" height="12" rx="2" fill="#21262d"/>'
            f'<rect x="170" y="{y - 11}" width="{bar}" height="12" rx="2" fill="{color}"/>'
            f'<text x="506" y="{y}" class="muted">{pct:5.1f}%</text></g>'
        )
        delay += STEP

    # $ gh contrib
    y += BLOCK
    delay += 0.4
    parts.append(command(y, "gh contrib --last-year", delay))
    delay += TYPE_TIME
    y += LINE
    parts.append(f'<text x="24" y="{y}" class="l" style="animation-delay:{delay:.2f}s">'
                 f'<tspan class="hl bold">{calendar["totalContributions"]}</tspan> contributions in the last year</text>')
    delay += STEP
    y += 14
    max_count = max((d["contributionCount"] for d in days), default=0) or 1
    cells = []
    for wi, week in enumerate(calendar["weeks"]):
        for day in week["contributionDays"]:
            weekday = date.fromisoformat(day["date"]).isoweekday() % 7  # Sunday = 0
            cells.append(f'<rect x="{24 + wi * 15}" y="{y + weekday * 15}" width="11" height="11" rx="2" '
                         f'fill="{level_color(day["contributionCount"], max_count)}"/>')
    parts.append(f'<g class="l" style="animation-delay:{delay:.2f}s">{"".join(cells)}</g>')
    y += 7 * 15 - 11

    # $ ./contact.sh
    y += BLOCK
    delay += 0.4
    parts.append(command(y, "./contact.sh", delay))
    delay += TYPE_TIME
    y += LINE
    parts.append(f'<text x="24" y="{y}" class="l" style="animation-delay:{delay:.2f}s">'
                 f'<tspan class="muted">→ links below</tspan> <tspan class="accent">↓</tspan></text>')
    delay += 0.4

    # final prompt + blinking cursor
    y += 26
    parts.append(f'<g class="l" style="animation-delay:{delay:.2f}s">'
                 f'<text x="24" y="{y}">{PROMPT}</text>'
                 f'<rect x="167" y="{y - 12}" width="9" height="16" fill="#c9d1d9" class="cursor"/></g>')

    return "\n  ".join(parts), y + 22


def main():
    template = open(TEMPLATE, encoding="utf-8").read()
    marker = re.search(r"<!-- DYNAMIC y=(\d+) delay=([\d.]+)", template)
    if not marker:
        sys.exit("DYNAMIC marker not found in template")

    dynamic, height = build_dynamic(fetch(), int(marker.group(1)), float(marker.group(2)))
    svg = (template
           .replace("{{DYNAMIC}}", dynamic)
           .replace("{{HEIGHT}}", str(height))
           .replace("{{INNER_HEIGHT}}", str(height - 1))
           .replace("{{UPDATED}}", date.today().isoformat()))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT} ({height}px)")


if __name__ == "__main__":
    main()
