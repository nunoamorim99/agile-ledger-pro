"""The numbers a Product Manager steers by, computed from the ledger as it is.

Pure functions over a repo snapshot (see ``store.Repo.snapshot``), so they are
testable without a server and the dashboard and the ``/insights`` command
agree to the digit. Everything here is **derived**: nothing is written back,
and a figure the ledger cannot support is returned as ``None`` with a reason
rather than estimated — a dashboard that guessed a cycle time would be worse
than one that said it has no dates yet.

Three families, by what the ledger records:

* **Outcomes** — what shipped, when, by whom: velocity, reliability, carry-over,
  releases, bugs reported and fixed, the epic portfolio. Every ledger has these.
* **Flow** — how long things take: lead time, cycle time, blocked time, scope
  change, the ideas funnel. These need the dates Phase 0 started writing, so
  an older ledger reports them as not-yet-measurable with a count of how many
  items carry the dates so far.
* **Methodology** — velocity is a Scrum number; throughput and cycle time
  are what a Kanban team runs on, and are also what lets two projects on
  different methodologies be compared. ``transition`` derives the numbers a
  switch needs instead of inventing them.

One deliberate absence: there is no per-person ranking. ``workload`` says how
work is *distributed* — whether one person is carrying half the delivery — and
stops there. The skill promises the ledger is never a productivity leaderboard
and this module keeps that promise.
"""

from __future__ import annotations

import datetime
import re
from collections import Counter, defaultdict
from statistics import median

from . import mdutil
from .model import BOARD_COLUMNS, CONFIG_OWNERS  # noqa: F401  (owners used by callers)
from .mdutil import EMPTY

DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _date(text: str | None) -> datetime.date | None:
    m = DATE.search(str(text or ""))
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _int(value) -> int:
    text = str(value if value is not None else "").strip()
    return int(text) if text.isdigit() else 0


def _month(d: datetime.date | None) -> str:
    return d.strftime("%Y-%m") if d else ""


def _pct(part: int, whole: int) -> int | None:
    return round(100 * part / whole) if whole else None


def _name(written: str) -> str:
    """``@rita`` and ``rita`` are the same person on an item."""
    return str(written or "").strip().lstrip("@")


def _by_id(items: list[dict]) -> dict[str, dict]:
    return {i["id"]: i for i in items}


def _median_days(spans: list[int]) -> dict | None:
    if not spans:
        return None
    ordered = sorted(spans)
    p85 = ordered[min(len(ordered) - 1, int(round(0.85 * (len(ordered) - 1))))]
    return {"n": len(spans), "median": round(median(spans), 1),
            "p85": p85, "min": ordered[0], "max": ordered[-1]}


# --------------------------------------------------------------------------
# Outcomes
# --------------------------------------------------------------------------

def sprints(snapshot: dict) -> dict:
    """Velocity, commitment reliability and carry-over, per closed sprint.

    Reliability is completed ÷ committed: the honest-planning number. Carry-over
    is how much of what was promised rolled into the next sprint. Both come
    straight off Sprints-History, so every ledger has them.
    """
    history = snapshot.get("history") or {}
    rows = []
    for s in reversed(history.get("sprints") or []):          # oldest first
        committed, completed = _int(s.get("committed")), _int(s.get("completed"))
        delivered = s.get("delivered") or []
        carried = s.get("carried") or []
        start, end = _date(s.get("start")), _date(s.get("end"))
        rows.append({
            "name": s.get("name", ""),
            "start": s.get("start", ""), "end": s.get("end", ""),
            "days": (end - start).days + 1 if start and end and end >= start else None,
            "committed": committed, "completed": completed,
            "velocity": _int(s.get("velocity")) or completed,
            "reliability": _pct(completed, committed),
            "delivered": len(delivered),
            "delivered_bugs": sum(1 for i in delivered if i.startswith("BUG")),
            "carried": len(carried),
            "pulled": len(s.get("pulled") or []),
            "pulled_points": _int(s.get("pulled_points")),
        })
    velocities = [r["velocity"] for r in rows if r["velocity"]]
    last3 = velocities[-3:]
    reliabilities = [r["reliability"] for r in rows if r["reliability"] is not None]
    lengths = [r["days"] for r in rows if r["days"]]
    return {
        "sprints": rows,
        "count": len(rows),
        "rolling_velocity": round(sum(last3) / len(last3)) if last3 else None,
        "velocity_trend": (last3[-1] - last3[0]) if len(last3) >= 2 else None,
        "reliability_avg": round(sum(reliabilities) / len(reliabilities)) if reliabilities else None,
        "carry_over_rate": _pct(sum(r["carried"] for r in rows),
                                sum(r["carried"] + r["delivered"] for r in rows)),
        "typical_length_days": round(median(lengths)) if lengths else None,
    }


def forecast(snapshot: dict, sprint_summary: dict | None = None) -> dict:
    """How long the Ready backlog lasts, and when each epic lands, at today's pace.

    Everything is in sprints of velocity; a date is given only when the history
    says how long a sprint is. No velocity means no forecast, said plainly.
    """
    summary = sprint_summary or sprints(snapshot)
    velocity = summary["rolling_velocity"]
    stories = snapshot.get("stories") or []
    ready_pts = sum(_int(s.get("estimate")) for s in stories if s.get("state") == "Ready")
    ready_n = sum(1 for s in stories if s.get("state") == "Ready")
    unestimated = sum(1 for s in stories
                      if s.get("state") in ("Ready", "In Sprint") and not _int(s.get("estimate")))
    length = summary["typical_length_days"]

    def sprints_for(points: int) -> float | None:
        return round(points / velocity, 1) if velocity else None

    def date_for(n_sprints: float | None) -> str | None:
        if n_sprints is None or not length:
            return None
        return (datetime.date.today() + datetime.timedelta(days=round(n_sprints * length))).isoformat()

    epics = []
    for e in snapshot.get("epics") or []:
        roll = e.get("rollup") or {}
        remaining = _int(roll.get("points_total")) - _int(roll.get("points_done"))
        if remaining <= 0 or e.get("state") in ("Done", "Discarded", "Paused"):
            continue
        n = sprints_for(remaining)
        epics.append({"id": e["id"], "title": e.get("title", ""), "remaining_points": remaining,
                      "sprints": n, "eta": date_for(n), "target": e.get("target", EMPTY)})
    epics.sort(key=lambda x: (x["sprints"] is None, x["sprints"] or 0))

    runway = sprints_for(ready_pts)
    return {
        "velocity": velocity,
        "ready_points": ready_pts, "ready_stories": ready_n,
        "unestimated": unestimated,
        "runway_sprints": runway,
        "runway_until": date_for(runway),
        "epics": epics,
        "reason": None if velocity else "no closed sprint with a velocity yet",
    }


def bugs(snapshot: dict) -> dict:
    """Reported vs fixed per month, what is open and how old, time to fix, escapes."""
    today = datetime.date.today()
    all_bugs = snapshot.get("bugs") or []
    stories = _by_id(snapshot.get("stories") or [])
    reported_by_month, fixed_by_month = Counter(), Counter()
    open_by_sev, open_by_pri = Counter(), Counter()
    ages, fix_days, triage_days = [], [], []
    escapes = []
    for b in all_bugs:
        reported, fixed = _date(b.get("reported_by")), _date(b.get("fixed"))
        triaged = _date(b.get("triaged"))
        if reported:
            reported_by_month[_month(reported)] += 1
        if fixed:
            fixed_by_month[_month(fixed)] += 1
            if reported and fixed >= reported:
                fix_days.append((fixed - reported).days)
        if triaged and reported and triaged >= reported:
            triage_days.append((triaged - reported).days)
        is_open = b.get("state") not in ("Fixed", "Deferred", "Won't fix", "Won’t fix")
        if is_open:
            open_by_sev[b.get("severity") or EMPTY] += 1
            open_by_pri[b.get("priority") or EMPTY] += 1
            if reported:
                ages.append((today - reported).days)
        related = b.get("relates_to")
        if related and related in stories and stories[related].get("state") == "Delivered":
            version = (re.search(r"released in (v[\d.]+)", stories[related].get("delivered", "")) or [None, None])[1]
            escapes.append({"bug": b["id"], "story": related, "version": version or EMPTY,
                            "severity": b.get("severity") or EMPTY})
    inbox = len(snapshot.get("bug_inbox") or [])
    months = sorted(set(reported_by_month) | set(fixed_by_month))
    return {
        "total": len(all_bugs), "inbox": inbox,
        "open": sum(open_by_sev.values()),
        "open_by_severity": dict(open_by_sev), "open_by_priority": dict(open_by_pri),
        "by_month": [{"month": m, "reported": reported_by_month[m], "fixed": fixed_by_month[m]}
                     for m in months],
        "open_age_days": _median_days(ages),
        "time_to_fix_days": _median_days(fix_days),
        "time_to_triage_days": _median_days(triage_days),
        "escapes": escapes,
        "escape_rate": _pct(len(escapes), sum(1 for s in stories.values() if s.get("state") == "Delivered")),
    }


def portfolio(snapshot: dict) -> dict:
    """The epics: how many, in what state, how far along; releases and their cadence."""
    epics = snapshot.get("epics") or []
    by_state = Counter((e.get("state") or "Proposed") for e in epics)
    rows = []
    for e in epics:
        roll = e.get("rollup") or {}
        rows.append({"id": e["id"], "title": e.get("title", ""), "state": e.get("state", ""),
                     "target": e.get("target", EMPTY), "created": e.get("created", ""),
                     "stories_done": _int(roll.get("stories_done")),
                     "stories_total": _int(roll.get("stories_total")),
                     "points_done": _int(roll.get("points_done")),
                     "points_total": _int(roll.get("points_total")),
                     "progress": _pct(_int(roll.get("points_done")), _int(roll.get("points_total")))})
    versions = list(reversed((snapshot.get("releases") or {}).get("versions") or []))  # oldest first
    dated = [(v, _date(v.get("date"))) for v in versions]
    gaps = [(b[1] - a[1]).days for a, b in zip(dated, dated[1:]) if a[1] and b[1] and b[1] >= a[1]]
    releases = [{"version": v.get("version", ""), "title": v.get("title", ""), "date": v.get("date", ""),
                 "stories": len(v.get("stories") or []), "epics": len(v.get("epics") or [])}
                for v in versions]
    last = dated[-1][1] if dated and dated[-1][1] else None
    return {
        "epics": rows, "by_state": dict(by_state), "count": len(epics),
        "releases": releases,
        "release_gap_days": _median_days(gaps),
        "days_since_release": (datetime.date.today() - last).days if last else None,
        "unreleased": len((snapshot.get("releases") or {}).get("increment") or []),
    }


def workload(snapshot: dict) -> dict:
    """Who is carrying what: WIP now, and the share of delivery over the history.

    A distribution, not a ranking. The question it answers is "is one person
    carrying half of this" — a bus-factor and burnout signal — and it says so
    when the answer is yes. It never orders people by output.
    """
    board = (snapshot.get("sprint") or {}).get("board") or {}
    stories, all_bugs = _by_id(snapshot.get("stories") or []), _by_id(snapshot.get("bugs") or [])
    wip = defaultdict(lambda: {"in_progress": 0, "in_review": 0, "in_pr": 0, "points": 0})
    for column, key in (("In Progress", "in_progress"), ("In Review", "in_review"), ("In PR", "in_pr")):
        for item in board.get(column) or []:
            who = _name(item.get("assignee")) or EMPTY
            wip[who][key] += 1
            wip[who]["points"] += _int(item.get("points"))
    delivered_pts = Counter()
    for s in stories.values():
        if s.get("state") == "Delivered":
            delivered_pts[_name(s.get("assignee")) or EMPTY] += _int(s.get("estimate"))
    for b in all_bugs.values():
        if b.get("state") == "Fixed":
            delivered_pts[_name(b.get("assignee")) or EMPTY] += _int(b.get("estimate"))
    total = sum(delivered_pts.values())
    people = sorted(set(wip) | set(delivered_pts))
    rows = [{"person": p, **wip[p], "delivered_points": delivered_pts[p],
             "share": _pct(delivered_pts[p], total)} for p in people]
    rows.sort(key=lambda r: r["person"].lower())          # alphabetical, deliberately
    heavy = [r["person"] for r in rows if r["share"] is not None and r["share"] >= 50 and r["person"] != EMPTY]
    return {"people": rows, "total_delivered_points": total,
            "concentrated_on": heavy,
            "wip_total": sum(r["in_progress"] + r["in_review"] + r["in_pr"] for r in rows)}


def backlog_health(snapshot: dict) -> dict:
    """Slicing and readiness smells: what will hurt planning next."""
    from .actions import _dor_warnings
    stories = snapshot.get("stories") or []
    epics = snapshot.get("epics") or []
    big = [{"id": s["id"], "points": _int(s.get("estimate"))}
           for s in stories if s.get("state") in ("Ready", "In Sprint") and _int(s.get("estimate")) >= 8]
    failing = []
    for s in stories:
        if s.get("state") == "Ready":
            why = _dor_warnings(s)
            if why:
                failing.append({"id": s["id"], "why": why})
    drafts = [st for e in epics for st in (e.get("stories") or []) if "Draft" in (st.get("state") or "")]
    ideas = snapshot.get("ideas") or []
    today = datetime.date.today()
    idea_ages = [(today - d).days for d in (_date(i.get("date")) for i in ideas) if d]
    board = (snapshot.get("sprint") or {}).get("board") or {}
    on_board = [i for col in BOARD_COLUMNS for i in (board.get(col) or [])]
    bug_pts = sum(_int(i.get("points")) for i in on_board if i["id"].startswith("BUG"))
    story_pts = sum(_int(i.get("points")) for i in on_board if not i["id"].startswith("BUG"))
    return {
        "oversized": big,
        "failing_dor": failing,
        "drafts": len(drafts),
        "ideas_in_inbox": len(ideas),
        "idea_age_days": _median_days(idea_ages),
        "unplanned_share": _pct(bug_pts, bug_pts + story_pts),
        "blocked": len((snapshot.get("sprint") or {}).get("blocked") or []),
    }


# --------------------------------------------------------------------------
# Flow — needs the Phase 0 dates
# --------------------------------------------------------------------------

def flow(snapshot: dict) -> dict:
    """Lead time, cycle time, blocked time, scope change and the ideas funnel.

    Reported only from items that carry the dates; the counts say how much of
    the ledger is measurable yet, so a young number is read as young.
    """
    today = datetime.date.today()
    stories = snapshot.get("stories") or []
    all_bugs = snapshot.get("bugs") or []
    lead, cycle, dated = [], [], 0
    per_story = []
    for s in stories:
        ready, started, delivered = _date(s.get("ready")), _date(s.get("started")), _date(s.get("delivered"))
        if ready or started:
            dated += 1
        row = {"id": s["id"], "lead": None, "cycle": None}
        if delivered and ready and delivered >= ready:
            row["lead"] = (delivered - ready).days
            lead.append(row["lead"])
        if delivered and started and delivered >= started:
            row["cycle"] = (delivered - started).days
            cycle.append(row["cycle"])
        if row["lead"] is not None or row["cycle"] is not None:
            per_story.append(row)
    bug_cycle = []
    for b in all_bugs:
        started, fixed = _date(b.get("started")), _date(b.get("fixed"))
        if started and fixed and fixed >= started:
            bug_cycle.append((fixed - started).days)

    # Work in flight right now, with its age — the live half of cycle time.
    in_flight = []
    board = (snapshot.get("sprint") or {}).get("board") or {}
    by_id = {**_by_id(stories), **_by_id(all_bugs)}
    for column in ("In Progress", "In Review", "In PR"):
        for item in board.get(column) or []:
            started = _date((by_id.get(item["id"]) or {}).get("started"))
            in_flight.append({"id": item["id"], "column": column,
                              "days": (today - started).days if started else None})

    blocked = []
    for b in (snapshot.get("sprint") or {}).get("blocked") or []:
        since = _date(b.get("since"))
        blocked.append({"id": b["id"], "reason": b.get("reason", ""),
                        "days": (today - since).days if since else None})

    pulled = [i for col in BOARD_COLUMNS for i in (board.get(col) or []) if i.get("pulled")]
    on_board = [i for col in BOARD_COLUMNS for i in (board.get(col) or [])]
    scope = {"pulled": len(pulled), "pulled_points": sum(_int(i.get("points")) for i in pulled),
             "board_points": sum(_int(i.get("points")) for i in on_board)}
    scope["share"] = _pct(scope["pulled_points"], scope["board_points"])

    # Throughput: delivered items and points per week over the last 12 weeks,
    # from Delivered/Fixed dates. Methodology-neutral, which is the point.
    weeks = Counter()
    week_pts = Counter()
    cutoff = today - datetime.timedelta(weeks=12)
    for s in stories:
        d = _date(s.get("delivered"))
        if d and d >= cutoff:
            wk = d.isocalendar()
            weeks[f"{wk[0]}-W{wk[1]:02d}"] += 1
            week_pts[f"{wk[0]}-W{wk[1]:02d}"] += _int(s.get("estimate"))
    for b in all_bugs:
        d = _date(b.get("fixed"))
        if d and d >= cutoff:
            wk = d.isocalendar()
            weeks[f"{wk[0]}-W{wk[1]:02d}"] += 1
            week_pts[f"{wk[0]}-W{wk[1]:02d}"] += _int(b.get("estimate"))
    throughput = [{"week": w, "items": weeks[w], "points": week_pts[w]} for w in sorted(weeks)]

    return {
        "measurable": dated, "of": len(stories),
        "lead_time_days": _median_days(lead),
        "cycle_time_days": _median_days(cycle),
        "bug_cycle_time_days": _median_days(bug_cycle),
        "per_story": per_story,
        "in_flight": in_flight,
        "blocked": blocked,
        "scope_change": scope,
        "throughput": throughput,
        "throughput_weekly": {
            "items": round(sum(weeks.values()) / 12, 1),
            "points": round(sum(week_pts.values()) / 12, 1),
        },
        "ideas": ideas_funnel(snapshot),
        "reason": None if dated else "no story carries Ready or Started yet — they are written from now on",
    }


def ideas_funnel(snapshot: dict) -> dict:
    """Captured, promoted and discarded per month, and how long triage takes."""
    inbox = snapshot.get("ideas") or []
    done = snapshot.get("triaged_ideas") or []
    captured, promoted, discarded = Counter(), Counter(), Counter()
    wait = []
    for i in inbox:
        captured[_month(_date(i.get("date")))] += 1
    for t in done:
        d, when = _date(t.get("date")), _date(t.get("triaged"))
        captured[_month(d)] += 1
        (promoted if t.get("outcome") == "promoted" else discarded)[_month(when or d)] += 1
        if d and when and when >= d:
            wait.append((when - d).days)
    months = sorted(m for m in set(captured) | set(promoted) | set(discarded) if m)
    total = len(inbox) + len(done)
    return {
        "by_month": [{"month": m, "captured": captured[m], "promoted": promoted[m],
                      "discarded": discarded[m]} for m in months],
        "captured": total, "promoted": sum(promoted.values()), "discarded": sum(discarded.values()),
        "waiting": len(inbox),
        "promotion_rate": _pct(sum(promoted.values()), sum(promoted.values()) + sum(discarded.values())),
        "days_to_triage": _median_days(wait),
    }


# --------------------------------------------------------------------------
# Methodology
# --------------------------------------------------------------------------

METHODOLOGIES = ("scrum", "kanban")


def methodology(snapshot: dict) -> str:
    """``scrum`` unless the project's Definitions.md says ``kanban``."""
    config = (snapshot.get("definitions") or {}).get("config") or {}
    value = str(config.get("methodology", "")).strip().lower()
    return value if value in METHODOLOGIES else "scrum"


def wip_limits(snapshot: dict) -> dict[str, int]:
    """``wip_limits: In Progress 3 · In Review 2`` from Definitions.md, by column."""
    config = (snapshot.get("definitions") or {}).get("config") or {}
    text = str(config.get("wip_limits", ""))
    out = {}
    for part in re.split(r"[·,;|]", text):
        m = re.match(r"\s*(.+?)\s*[:=]?\s*(\d+)\s*$", part)
        if not m:
            continue
        column = next((c for c in BOARD_COLUMNS if c.lower() == m.group(1).strip().lower()), None)
        if column:
            out[column] = int(m.group(2))
    return out


def wip_status(snapshot: dict) -> list[dict]:
    """Each column against its limit, for the Kanban board header."""
    limits = wip_limits(snapshot)
    board = (snapshot.get("sprint") or {}).get("board") or {}
    return [{"column": c, "count": len(board.get(c) or []), "limit": limits.get(c),
             "over": limits.get(c) is not None and len(board.get(c) or []) > limits[c]}
            for c in BOARD_COLUMNS if c not in ("Done",)]


def transition(snapshot: dict, to: str) -> dict:
    """What a switch of methodology needs, derived from the ledger — not guessed.

    Nothing here writes. It returns the numbers and the gaps so the command and
    the Settings screen can show a person exactly what they would be agreeing
    to, with the arithmetic behind every suggested value.
    """
    to = (to or "").strip().lower()
    current = methodology(snapshot)
    if to not in METHODOLOGIES:
        return {"ok": False, "reason": f"unknown methodology {to!r}"}
    if to == current:
        return {"ok": False, "reason": f"this project already runs {current}"}

    stories = snapshot.get("stories") or []
    all_bugs = snapshot.get("bugs") or []
    keeps = ["every epic, story and bug, with its state", "the board and whatever is on it",
             "Sprints-History.md, untouched — history is never deleted",
             "Releases.md and the Increment", "the roster, the rules and every date"]
    out = {"ok": True, "from": current, "to": to, "keeps": keeps, "needs": [], "suggests": {}, "gaps": []}

    if to == "kanban":
        board = (snapshot.get("sprint") or {}).get("board") or {}
        observed = {c: len(board.get(c) or []) for c in ("In Progress", "In Review", "In PR")}
        people = len({_name(i.get("assignee")) for col in board.values() for i in col if _name(i.get("assignee"))})
        # A limit of one per person in progress is the textbook start; the
        # observed maximum says what the team actually does today.
        out["suggests"]["wip_limits"] = {c: max(n, people or 1) if c == "In Progress" else max(n, 1)
                                         for c, n in observed.items()}
        out["suggests"]["why"] = (f"In Progress: {people or 1} person(s) on the board, {observed['In Progress']} "
                                  f"item(s) there now; the others from today's counts")
        sprint = snapshot.get("sprint") or {}
        if not mdutil.is_empty(sprint.get("name")):
            out["needs"].append(f"the open sprint {sprint['name']} is closed first, so its velocity is recorded; "
                                "the board itself stays as it is")
        out["needs"].append("WIP limits agreed per column (suggested below)")
        out["gaps"].append("velocity stops being the headline; throughput and cycle time take over, from "
                           "the dates the ledger already carries")
        return out

    # kanban -> scrum
    summary = sprints(snapshot)
    estimated = [s for s in stories if s.get("state") == "Ready" and _int(s.get("estimate"))]
    ready = [s for s in stories if s.get("state") == "Ready"]
    length = summary["typical_length_days"] or 14
    out["suggests"]["sprint_length_days"] = length
    # Velocity from throughput: points delivered per sprint-length window,
    # over the last six windows, from Delivered/Fixed dates. Shown with the
    # windows so the number can be argued with.
    today = datetime.date.today()
    windows = []
    for k in range(6):
        hi = today - datetime.timedelta(days=length * k)
        lo = hi - datetime.timedelta(days=length)
        pts = sum(_int(s.get("estimate")) for s in stories
                  if (d := _date(s.get("delivered"))) and lo < d <= hi)
        pts += sum(_int(b.get("estimate")) for b in all_bugs
                   if (d := _date(b.get("fixed"))) and lo < d <= hi)
        items = sum(1 for s in stories if (d := _date(s.get("delivered"))) and lo < d <= hi)
        items += sum(1 for b in all_bugs if (d := _date(b.get("fixed"))) and lo < d <= hi)
        windows.append({"from": (lo + datetime.timedelta(days=1)).isoformat(), "to": hi.isoformat(),
                        "points": pts, "items": items})
    windows.reverse()
    with_work = [w for w in windows if w["items"]]
    if with_work:
        out["suggests"]["velocity"] = round(sum(w["points"] for w in with_work) / len(with_work))
        out["suggests"]["items_per_sprint"] = round(sum(w["items"] for w in with_work) / len(with_work), 1)
        out["suggests"]["windows"] = windows
        out["suggests"]["why"] = (f"points delivered per {length}-day window over the last "
                                  f"{len(with_work)} window(s) with work in them")
    else:
        out["gaps"].append("nothing delivered in the last six windows, so no velocity can be derived; "
                           "plan the first sprint by count and record the real velocity at close")
    if ready and len(estimated) < len(ready):
        out["gaps"].append(f"{len(ready) - len(estimated)} of {len(ready)} Ready stories have no estimate — "
                           "Scrum planning needs points; estimate them, or plan the first sprint by count")
    if summary["rolling_velocity"] is None and with_work and all(w["points"] == 0 for w in with_work):
        out["gaps"].append("delivered work carries no points, so the derived velocity is 0 — the team "
                           "did not estimate under Kanban; a velocity will only exist after one estimated sprint")
    out["needs"].append("a sprint length and a start day")
    out["needs"].append("a first sprint planned with /plan-sprint, using the derived velocity as capacity")
    return out


# --------------------------------------------------------------------------
# The whole report
# --------------------------------------------------------------------------

def report(snapshot: dict) -> dict:
    """Everything, keyed by family; what the dashboard and ``/insights`` both read."""
    summary = sprints(snapshot)
    way = methodology(snapshot)
    return {
        "methodology": way,
        "sprints": summary,
        "forecast": forecast(snapshot, summary),
        "bugs": bugs(snapshot),
        "portfolio": portfolio(snapshot),
        "workload": workload(snapshot),
        "backlog": backlog_health(snapshot),
        "flow": flow(snapshot),
        "wip": wip_status(snapshot) if way == "kanban" else [],
        "generated": datetime.date.today().isoformat(),
    }
