"""User-facing release notes for one version, ready to paste into a store.

Derived from the ledger, never written to it: the version entry in
Releases.md says which items shipped, and each item's own entry says what it
does for a user. The story sentence carries that already — "As a new user, I
want to sign in with my Google account, so that I don't have to create another
password" becomes "You can now sign in with your Google account, so you don't
have to create another password." — so the notes are mostly a rephrasing the
code can do, and a starting point a PM edits rather than a blank page.

Two shapes, because the two audiences read differently:

* **store** — plain text with `•` bullets. The App Store and Google Play show
  "What's new" as plain text; Markdown would arrive as literal asterisks.
  Google Play caps it at 500 characters per language, the App Store at 4000,
  and both limits are reported so the PM knows before pasting.
* **markdown** — headed sections with item IDs, for the team, a GitHub
  release or a CHANGELOG.

Grouping: a bug is **Fixed**; a story whose epic shipped nothing before this
version is **New**; any other story is **Improved**.
"""

from __future__ import annotations

import re

from .mdutil import EMPTY

STORE_LIMITS = {"google_play": 500, "app_store": 4000}

_PRONOUNS = [
    (r"\bI am\b", "you are"), (r"\bI'm\b", "you're"), (r"\bI’m\b", "you’re"),
    (r"\bI've\b", "you've"), (r"\bI’ve\b", "you’ve"), (r"\bI\b", "you"),
    (r"\bmy\b", "your"), (r"\bMy\b", "Your"), (r"\bme\b", "you"),
    (r"\bmine\b", "yours"), (r"\bmyself\b", "yourself"), (r"\bwe\b", "you"),
    (r"\bour\b", "your"), (r"\bus\b", "you"),
]


def _you(text: str) -> str:
    for pattern, repl in _PRONOUNS:
        text = re.sub(pattern, repl, text)
    return text


def _sentence(text: str) -> str:
    text = text.strip().rstrip(".")
    return (text[:1].upper() + text[1:] + ".") if text else ""


def user_line(story: dict, title: str) -> str:
    """One user-facing sentence for a story; the title when there is no story sentence."""
    sentence = re.sub(r"[*_`]", "", story.get("story") or "").strip()
    m = re.search(r"\bI want( to)?\s+(.*?)(?:,?\s*so that\s+(.*))?$", sentence, re.IGNORECASE | re.S)
    if m and m.group(2).strip():
        want = _you(m.group(2).strip().rstrip(",."))
        why = _you(m.group(3).strip()) if m.group(3) else ""
        if "??" in why:                       # reconstructed: the value is unconfirmed
            why = ""
        # "I want to export logs" is an action; "I want the audit log as a CSV"
        # is a thing, and "You can now the audit log" is not English.
        line = f"You can now {want}" if m.group(1) else f"You now get {want}"
        if why:
            line += f", so {why}"
        return _sentence(line)
    return _sentence(title or story.get("title") or "")


def _version(snapshot: dict, version: str | None) -> dict | None:
    versions = (snapshot.get("releases") or {}).get("versions") or []
    if not versions:
        return None
    if not version:
        return versions[0]                    # newest first
    want = version.lower().lstrip("v")
    return next((v for v in versions if str(v.get("version", "")).lower().lstrip("v") == want), None)


def build(snapshot: dict, version: str | None = None) -> dict:
    """Notes for ``version`` (the newest when omitted), in both shapes."""
    v = _version(snapshot, version)
    if not v:
        return {"ok": False, "reason": f"no release {version}" if version else "no release has been cut yet"}

    stories = {s["id"]: s for s in snapshot.get("stories") or []}
    bugs = {b["id"]: b for b in snapshot.get("bugs") or []}
    index = {}                                # id -> (epic, index line) for titles and parents
    for e in snapshot.get("epics") or []:
        for st in e.get("stories") or []:
            index[st["id"]] = (e, st)

    # An epic is "new" in this version when nothing of it shipped in an older one.
    versions = (snapshot.get("releases") or {}).get("versions") or []
    position = next((i for i, x in enumerate(versions) if x is v), 0)
    earlier = {i for x in versions[position + 1:] for i in (x.get("stories") or [])}

    groups = {"New": [], "Improved": [], "Fixed": []}
    for item_id in v.get("stories") or []:
        if item_id.startswith("BUG"):
            b = bugs.get(item_id, {})
            title = b.get("title") or item_id
            # A bug's title names the fault, so on its own it reads like a
            # feature. "Fixed an issue where …" is how stores phrase it.
            fault = title[:1].lower() + title[1:] if title[1:2].islower() else title
            groups["Fixed"].append({"id": item_id, "text": _sentence(f"Fixed an issue where {fault}")})
            continue
        story = stories.get(item_id, {})
        epic, line = index.get(item_id, ({}, {}))
        title = story.get("title") or line.get("title") or item_id
        siblings = {st["id"] for st in (epic.get("stories") or [])}
        group = "Improved" if siblings & earlier else "New"
        groups[group].append({"id": item_id, "text": user_line(story, title), "epic": epic.get("id", "")})

    head = f"{v.get('version', '')}" + (f" — {v['title']}" if v.get("title") and v["title"] != EMPTY else "")
    theme = v.get("theme") if v.get("theme") and v.get("theme") != EMPTY else ""

    store = []
    if theme:
        store += [_sentence(theme), ""]
    labels = {"New": "New", "Improved": "Improved", "Fixed": "Fixed"}
    for name in ("New", "Improved", "Fixed"):
        if groups[name]:
            store.append(f"{labels[name]}:")
            store += [f"• {i['text']}" for i in groups[name]]
            store.append("")
    store_text = "\n".join(store).strip()

    md = [f"## {head}" + (f" ({v['date']})" if v.get("date") else ""), ""]
    if theme:
        md += [_sentence(theme), ""]
    for name in ("New", "Improved", "Fixed"):
        if groups[name]:
            md += [f"### {name}", ""]
            md += [f"- {i['text']} ({i['id']})" for i in groups[name]]
            md.append("")
    md_text = "\n".join(md).strip()

    length = len(store_text)
    return {
        "ok": True,
        "version": v.get("version", ""), "title": v.get("title", ""), "date": v.get("date", ""),
        "groups": groups,
        "store": store_text,
        "markdown": md_text,
        "length": length,
        "limits": {k: {"limit": n, "fits": length <= n} for k, n in STORE_LIMITS.items()},
        "empty": not any(groups.values()),
    }
