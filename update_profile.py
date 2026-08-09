#!/usr/bin/env python3
"""Refresh dynamic values in the GitHub profile SVG cards."""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import os
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET


USERNAME = os.getenv("GITHUB_REPOSITORY_OWNER", "chipqp")
BIRTH_DATE = os.getenv("BIRTH_DATE", "").strip() or "2006-09-05"
TOKEN = os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN", "")).strip()
SVG_FILES = (Path("profile-dark.svg"), Path("profile-light.svg"))
REQUIRED_IDS = {
    "age_data",
    "age_data_dots",
    "repo_data",
    "repo_data_dots",
    "star_data",
    "star_data_dots",
    "follower_data",
    "follower_data_dots",
    "contrib_label",
    "contrib_data",
    "contrib_data_dots",
    "account_year",
    "updated_data",
}

ET.register_namespace("", "http://www.w3.org/2000/svg")


def request_json(url: str, *, payload: dict | None = None) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def add_months(value: dt.date, months: int) -> dt.date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def age_text(birth_date: str, today: dt.date | None = None) -> str:
    if not birth_date:
        return "set BIRTH_DATE variable"

    born = dt.date.fromisoformat(birth_date)
    current = today or dt.datetime.now(dt.timezone.utc).date()
    if born > current:
        raise ValueError("BIRTH_DATE cannot be in the future")

    months = (current.year - born.year) * 12 + current.month - born.month
    if add_months(born, months) > current:
        months -= 1
    cursor = add_months(born, months)
    years, remaining_months = divmod(months, 12)
    days = (current - cursor).days
    return f"{years}y {remaining_months}m {days}d"


def fetch_repositories() -> list[dict]:
    repositories: list[dict] = []
    page = 1
    while True:
        batch = request_json(
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?type=owner&sort=full_name&per_page=100&page={page}"
        )
        if not isinstance(batch, list):
            raise TypeError("GitHub repositories response was not a list")
        repositories.extend(batch)
        if len(batch) < 100:
            return repositories
        page += 1


def fetch_contributions(year: int) -> int | str:
    if not TOKEN:
        return "n/a"
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
        }
      }
    }
    """
    now = dt.datetime.now(dt.timezone.utc)
    start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
    result = request_json(
        "https://api.github.com/graphql",
        payload={
            "query": query,
            "variables": {
                "login": USERNAME,
                "from": start.isoformat(),
                "to": now.isoformat(),
            },
        },
    )
    if not isinstance(result, dict) or result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {result}")
    return result["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]["totalContributions"]


def collect_stats() -> dict[str, str]:
    profile = request_json(f"https://api.github.com/users/{USERNAME}")
    if not isinstance(profile, dict):
        raise TypeError("GitHub profile response was not an object")
    repositories = fetch_repositories()
    today = dt.datetime.now(dt.timezone.utc).date()
    year = today.year
    contributions = fetch_contributions(year)
    contribution_text = f"{contributions:,}" if isinstance(contributions, int) else contributions
    return {
        "age_data": age_text(BIRTH_DATE, today),
        "repo_data": f"{len(repositories):,}",
        "star_data": f"{sum(repo['stargazers_count'] for repo in repositories):,}",
        "follower_data": f"{profile['followers']:,}",
        "contrib_label": f"Contributions {year}",
        "contrib_data": contribution_text,
        "account_year": profile["created_at"][:4],
        "updated_data": today.isoformat(),
    }


def elements_by_id(root: ET.Element) -> dict[str, ET.Element]:
    return {
        element_id: element
        for element in root.iter()
        if (element_id := element.get("id"))
    }


def dot_fill(value: str, target_width: int) -> str:
    return " " + "." * max(2, target_width - len(value)) + " "


def update_svg(path: Path, values: dict[str, str]) -> None:
    tree = ET.parse(path)
    elements = elements_by_id(tree.getroot())
    missing = REQUIRED_IDS - elements.keys()
    if missing:
        raise ValueError(f"{path} is missing SVG ids: {', '.join(sorted(missing))}")

    for element_id, value in values.items():
        elements[element_id].text = value

    elements["age_data_dots"].text = dot_fill(values["age_data"], 31)
    elements["repo_data_dots"].text = dot_fill(values["repo_data"], 8)
    elements["star_data_dots"].text = dot_fill(values["star_data"], 8)
    elements["follower_data_dots"].text = dot_fill(values["follower_data"], 8)
    elements["contrib_data_dots"].text = dot_fill(values["contrib_data"], 5)

    tree.write(path, encoding="utf-8", xml_declaration=True)


def validate_svg(path: Path) -> None:
    root = ET.parse(path).getroot()
    missing = REQUIRED_IDS - elements_by_id(root).keys()
    if missing:
        raise ValueError(f"{path} is missing SVG ids: {', '.join(sorted(missing))}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--validate",
        action="store_true",
        help="validate SVG files without making network requests",
    )
    args = parser.parse_args()

    if args.validate:
        for svg_file in SVG_FILES:
            validate_svg(svg_file)
        print("SVG templates are valid")
        return

    values = collect_stats()
    for svg_file in SVG_FILES:
        update_svg(svg_file, values)
    print(f"Updated {len(SVG_FILES)} profile cards for {USERNAME}")


if __name__ == "__main__":
    main()
