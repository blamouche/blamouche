#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime


README_PATH = os.environ.get("README_PATH", "README.md")
FEED_URL = os.environ.get("FEED_URL", "https://lamouche.fr/index.xml")
MAX_POSTS = int(os.environ.get("MAX_POSTS", "5"))

START_MARKER = "<!-- LAMOUCHE:POSTS_START -->"
END_MARKER = "<!-- LAMOUCHE:POSTS_END -->"


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    published: datetime | None


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "update-readme-posts/1.0 (+https://github.com/blamouche)",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _parse_rss(xml_bytes: bytes) -> list[Post]:
    root = ET.fromstring(xml_bytes)

    channel = root.find("channel")
    if channel is None:
        raise ValueError("Expected RSS feed with <channel> root child.")

    posts: list[Post] = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        pub_raw = (item.findtext("pubDate") or "").strip()

        if not title or not url:
            continue

        published = None
        if pub_raw:
            try:
                published = parsedate_to_datetime(pub_raw)
            except Exception:
                published = None

        posts.append(Post(title=title, url=url, published=published))

    posts.sort(key=lambda p: p.published or datetime.min, reverse=True)
    return posts[: max(0, MAX_POSTS)]


def _render(posts: list[Post]) -> str:
    if not posts:
        return "- _No posts found._\n"

    lines: list[str] = []
    for post in posts:
        date_suffix = ""
        if post.published is not None:
            date_suffix = f" — {post.published.date().isoformat()}"
        lines.append(f"- [{post.title}]({post.url}){date_suffix}")
    return "\n".join(lines) + "\n"


def _ensure_section(readme: str) -> str:
    if START_MARKER in readme and END_MARKER in readme:
        return readme

    suffix = (
        "\n\n### Latest posts\n\n"
        f"{START_MARKER}\n"
        "- _Loading…_\n"
        f"{END_MARKER}\n"
    )
    return readme.rstrip() + suffix + "\n"


def _replace_between_markers(readme: str, body: str) -> str:
    start_idx = readme.find(START_MARKER)
    end_idx = readme.find(END_MARKER)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        raise ValueError("Markers missing or out of order in README.")

    start_end = start_idx + len(START_MARKER)
    before = readme[:start_end]
    after = readme[end_idx:]

    if not before.endswith("\n"):
        before += "\n"
    if not body.endswith("\n"):
        body += "\n"

    return before + body + after


def main() -> int:
    try:
        with open(README_PATH, "r", encoding="utf-8") as f:
            readme = f.read()

        readme = _ensure_section(readme)
        feed_bytes = _fetch(FEED_URL)
        posts = _parse_rss(feed_bytes)
        rendered = _render(posts)
        updated = _replace_between_markers(readme, rendered)

        if updated != readme:
            with open(README_PATH, "w", encoding="utf-8", newline="\n") as f:
                f.write(updated)
            print(f"Updated {README_PATH} with {len(posts)} posts from {FEED_URL}")
        else:
            print(f"No changes needed in {README_PATH}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

