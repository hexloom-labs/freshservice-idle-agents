#!/usr/bin/env python3
"""List Freshservice full-time agents with no activity or login for N days. Read-only.

Needs Python 3.9 or newer and no packages. Run it and paste an admin API key at the hidden prompt:

    python3 freshservice_idle_agents.py acme.freshservice.com --days 30 --price 49 --csv idle.csv

To skip the prompt, set FRESHSERVICE_API_KEY in the environment instead.
"""
import argparse
import base64
import csv
import getpass
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

PAGE_SIZE = 100
MAX_PAGES = 50
HOST_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}\.freshservice\.com$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def parse_time(value):
    if not value:
        return None
    try:
        t = datetime.fromisoformat(re.sub(r"(\d:\d\d)\.\d+", r"\1", str(value)).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def whole_days(later, earlier):
    return int((later - earlier).total_seconds() // 86400)


def find_idle(agents, now, days):
    counts = {"agents": len(agents), "deactivated": 0, "occasional": 0, "full_time": 0, "unassessed": 0}
    idle = []
    for a in agents:
        if a.get("active") is False:
            counts["deactivated"] += 1
            continue
        if a.get("occasional") is True:
            counts["occasional"] += 1
            continue
        counts["full_time"] += 1
        name = " ".join(p for p in (a.get("first_name"), a.get("last_name")) if p).strip() or a.get("email") or "Agent %s" % a.get("id")
        row = {"id": a.get("id"), "name": name, "email": a.get("email") or ""}
        times = [t for t in (parse_time(a.get("last_active_at")), parse_time(a.get("last_login_at"))) if t]
        if times:
            last = max(times)
            idle_days = max(0, whole_days(now, last))
            if idle_days >= days:
                idle.append({**row, "last_seen": last.astimezone(timezone.utc).date().isoformat(), "days_idle": idle_days, "never_seen": False})
            continue
        created = parse_time(a.get("created_at"))
        if created is None:
            counts["unassessed"] += 1
        elif whole_days(now, created) >= days:
            idle.append({**row, "last_seen": "", "days_idle": None, "never_seen": True})
    idle.sort(key=lambda r: (not r["never_seen"], -(r["days_idle"] or 0)))
    return idle, counts


def fetch_page(host, key, page):
    token = base64.b64encode((key + ":X").encode()).decode()
    request = urllib.request.Request(
        "https://%s/api/v2/agents?per_page=%d&page=%d" % (host, PAGE_SIZE, page),
        headers={"Authorization": "Basic " + token, "Content-Type": "application/json"},
    )
    with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        raise ValueError("unexpected reply")
    return data["agents"]


def list_agents(host, key, fetch=fetch_page):
    agents = []
    for page in range(1, MAX_PAGES + 1):
        batch = fetch(host, key, page)
        agents.extend(batch)
        if len(batch) < PAGE_SIZE:
            return agents, False
    return agents, True


def csv_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def http_message(status):
    if status in (401, 403):
        return "Freshservice rejected the API key. Use the key of an admin."
    if status == 404:
        return "Freshservice did not recognise that address."
    if status == 429:
        return "Freshservice is rate limiting this account. Try again in a few minutes."
    return "Freshservice answered with status %d." % status


def main(argv=None):
    parser = argparse.ArgumentParser(description="List Freshservice agents with no activity or login for N days.")
    parser.add_argument("domain", help="your Freshservice address, for example acme.freshservice.com")
    parser.add_argument("--days", type=int, default=30, help="idle threshold in days, 1 to 365 (default 30)")
    parser.add_argument("--price", type=float, default=0, help="what you pay per full-time agent per month, to total the cost")
    parser.add_argument("--csv", metavar="FILE", help="also write the list to FILE as a CSV that opens in Excel")
    args = parser.parse_args(argv)

    host = args.domain.strip().lower().replace("https://", "").split("/")[0]
    if re.match(r"^[a-z0-9][a-z0-9-]{0,62}$", host):
        host += ".freshservice.com"
    if not HOST_RE.match(host):
        parser.error("the address must end in .freshservice.com; the key is only ever sent there")
    if not 1 <= args.days <= 365:
        parser.error("--days must be between 1 and 365")
    key = os.environ.get("FRESHSERVICE_API_KEY", "").strip()
    if not key:
        try:
            if sys.stdin.isatty():
                key = getpass.getpass("Freshservice API key (typing is hidden): ").strip()
            else:
                sys.stderr.write("Freshservice API key (this window may show what you paste; use cmd or PowerShell on Windows): ")
                sys.stderr.flush()
                key = sys.stdin.readline().strip()
        except (EOFError, KeyboardInterrupt):
            key = ""
    if not key:
        parser.error("no API key given. Run again and paste it at the prompt, or set FRESHSERVICE_API_KEY")

    try:
        agents, truncated = list_agents(host, key)
    except urllib.error.HTTPError as e:
        sys.exit(http_message(e.code))
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        sys.exit("Could not read the agent list from Freshservice. Check the address and your connection.")

    idle, counts = find_idle(agents, datetime.now(timezone.utc), args.days)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    print("%d of %d full-time agents have shown no activity for %d days or more." % (len(idle), counts["full_time"], args.days))
    for r in idle:
        print("  %-28s %-34s %s" % (r["name"][:28], r["email"][:34], "never seen" if r["never_seen"] else "%s (%d days ago)" % (r["last_seen"], r["days_idle"])))
    if args.price > 0 and idle:
        monthly = len(idle) * args.price
        print("At %.2f per agent per month these seats cost %.2f a month (%.2f a year)." % (args.price, monthly, monthly * 12))
    print("Not counted: %d occasional, %d deactivated." % (counts["occasional"], counts["deactivated"]))
    if counts["unassessed"]:
        print("%d full-time agent(s) have no activity or creation date in the data and could not be assessed." % counts["unassessed"])
    if truncated:
        print("Stopped after %d agents; the rest were not read." % (MAX_PAGES * PAGE_SIZE))
    if args.csv:
        try:
            with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
                out = csv.writer(f)
                out.writerow(["name", "email", "last_seen", "days_idle"])
                for r in idle:
                    out.writerow([csv_cell(r["name"]), csv_cell(r["email"]), r["last_seen"] or "never seen", "" if r["days_idle"] is None else r["days_idle"]])
        except OSError as e:
            sys.exit("Could not write %s: %s" % (args.csv, e.strerror or "unknown error"))
        print("Saved the list to %s." % args.csv)


if __name__ == "__main__":
    main()
