#!/usr/bin/env python3
"""Rebuild the "Recently" section of README.md from public GitHub data.

Standard library only. Dates are absolute, so the file changes only when
something on GitHub actually changed.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

USER = "Ryuu-x"
README = Path(__file__).resolve().parent.parent / "README.md"
START = "<!-- recent:start -->"
END = "<!-- recent:end -->"
MAX_REPOS = 5
MAX_EVENTS = 5


def api(path):
    """GET an API path. Returns parsed JSON, or None on a 404."""
    request = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "profile-readme-updater",
        },
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def day(timestamp):
    parsed = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
    return f"{parsed.day} {parsed:%b %Y}"


def repo_link(full_name):
    return f"[{full_name.split('/')[-1]}](https://github.com/{full_name})"


def repo_table(repos):
    """Render the most recently pushed original public repositories."""
    chosen = [
        repo
        for repo in repos
        if not (repo["fork"] or repo["archived"] or repo["private"])
        and repo["name"] != USER
    ][:MAX_REPOS]

    rows = [
        "| Repository | Language | Last push | Latest release |",
        "| :-- | :-- | :-- | :-- |",
    ]
    for repo in chosen:
        full_name = repo["full_name"]
        release = api(f"repos/{full_name}/releases/latest")
        release_text = (
            f"[{release['tag_name']}]({release['html_url']})" if release else "None"
        )
        rows.append(
            f"| {repo_link(full_name)} | {repo['language'] or 'None'} "
            f"| {day(repo['pushed_at'])} | {release_text} |"
        )
    return rows


def describe(event):
    """One line for a noteworthy event, or None. Pushes are in the table."""
    kind = event["type"]
    name = event["repo"]["name"]
    link = repo_link(name)
    payload = event["payload"]
    action = payload.get("action")

    if kind == "ReleaseEvent" and action == "published":
        release = payload["release"]
        return f"Released [{release['tag_name']}]({release['html_url']}) of {link}"
    if kind == "PublicEvent":
        return f"Made {link} public"
    if kind == "CreateEvent" and payload.get("ref_type") == "repository":
        return f"Created {link}"
    if kind == "PullRequestEvent" and action in ("opened", "merged"):
        number = payload.get("number") or payload["pull_request"]["number"]
        url = f"https://github.com/{name}/pull/{number}"
        return f"{action.capitalize()} [pull request #{number}]({url}) in {link}"
    return None


def event_list(events):
    lines = []
    for event in events:
        if not event.get("public", True) or event["repo"]["name"] == f"{USER}/{USER}":
            continue
        text = describe(event)
        line = text and f"- {day(event['created_at'])}: {text}"
        if line and line not in lines:
            lines.append(line)
    return lines[:MAX_EVENTS] or ["- No releases or new projects in the last 90 days."]


def main():
    repos = api(f"users/{USER}/repos?type=owner&sort=pushed&per_page=30")
    events = api(f"users/{USER}/events/public?per_page=100")
    if repos is None or events is None:
        sys.exit(f"GitHub returned 404 for user {USER}")

    body = "\n".join(repo_table(repos) + [""] + event_list(events))
    original = README.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + ".*?" + re.escape(END), re.DOTALL)
    if len(pattern.findall(original)) != 1:
        sys.exit(f"Expected exactly one {START} ... {END} block in {README}")

    updated = pattern.sub(lambda _: f"{START}\n{body}\n{END}", original)
    if updated == original:
        print("README already up to date")
        return
    README.write_text(updated, encoding="utf-8", newline="\n")
    print("README updated")


if __name__ == "__main__":
    main()
