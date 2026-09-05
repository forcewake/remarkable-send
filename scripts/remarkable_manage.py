#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remarkable_manage.py — reading-queue manager for a reMarkable 2 tablet via rmapi.

Subcommands:
  list          table of a folder: name, size, modified date  (options: --folder, --stat, --json)
  usage         account info + document counts per top-level folder (--json)
  plan-archive  DRY-RUN plan of mv->/Read and rm for stale queue items.
                Mutations only run with --execute (never by default).

Environment:
  RMAPI_BIN                  override rmapi binary path (used by stub tests)
  RMAPI_RETRY_SLEEP_SECONDS  wait before the single 429 retry (default 60)
  RMAPI_TIMEOUT_SECONDS      subprocess timeout (default 120)

Real rmapi v0.0.35 output formats this parser was built against (captured live):

  $ rmapi ls /Inbox                  (plain; TAB between tag and name; no dates)
    [f]\tAI Coding Agents Are Installing Unknown Untrusted Code on Corporate Networks - 2026-09-05
    [d]\tarxiv

  $ rmapi ls -l /Inbox               (long: "Mon _D YYYY  HH:MM  name", dirs end with "/",
                                       local timezone, year always shown, may be 0001 for /trash)
    Sep  5 2026  17:13  AI Coding Agents Are Installing Unknown Untrusted Code on Corporate Networks - 2026-09-05
    Feb 11 2026  13:38  arxiv/

  $ rmapi find /                     (recursive; leading "/" when arg is "/", WITHOUT it
                                       when arg is a folder like /Inbox; shows duplicates)
    [d] /
    [f] /Inbox/Deep dive context engineering for production agents - 2026-09-05
    [f] /Inbox/Stress Test Layout - 2026-09-05        <- duplicates preserved

  $ rmapi stat "/Inbox/<name>"       (JSON; ModifiedClient is ISO-8601 UTC; NO size field
                                       anywhere in v0.0.35 — the size column reports "-")
    { "ID": "…", "Name": "…", "Version": 0, "ModifiedClient": "2026-09-05T15:00:54Z",
      "Type": "DocumentType", "CurrentPage": 0, "Starred": false, "Parent": "…", "Tags": [] }

  $ rmapi account                    (single line; no storage/quota exists in this API)
    User: forcewake@gmail.com, SyncVersion: 1.5

Mutation commands (only ever run with plan-archive --execute):
  mkdir <dir> ; mv <source> <dest-folder> ; rm <path>     (rm deletes one entry per call)
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

# --------------------------------------------------------------------------- #
# rmapi invocation                                                            #
# --------------------------------------------------------------------------- #

READ_ONLY_COMMANDS = {"ls", "find", "stat", "account", "version", "help"}

DEFAULT_RETRY_SLEEP = 60  # seconds; per SKILL.md: 429 -> wait 60s, retry once, never loop


class RmapiError(Exception):
    pass


class RmapiAuthError(RmapiError):
    pass


def rmapi_bin():
    override = os.environ.get("RMAPI_BIN")
    if override:
        return override
    home_bin = os.path.join(os.path.expanduser("~"), "bin", "rmapi")
    if os.path.isfile(home_bin):
        return home_bin
    return "rmapi"


def _is_rate_limited(text):
    t = text.lower()
    return "429" in text or "too many requests" in t or "rate limit" in t


def run_rmapi(args, allow_write=False):
    """Run rmapi with args (argv list). Returns stdout.

    - Refuses mutation commands unless allow_write=True (defense in depth:
      nothing outside plan-archive --execute ever passes allow_write).
    - On non-zero exit: auth errors get a friendly message; 429/rate-limit is
      retried exactly once after RMAPI_RETRY_SLEEP_SECONDS (default 60s);
      anything else raises RmapiError.
    """
    if not args:
        raise RmapiError("empty rmapi command")
    if args[0] not in READ_ONLY_COMMANDS and not allow_write:
        raise RmapiError(
            "refusing to run mutating rmapi command %r outside --execute"
            % (args[0],)
        )

    binary = rmapi_bin()
    timeout = float(os.environ.get("RMAPI_TIMEOUT_SECONDS", "120"))
    retry_sleep = float(os.environ.get("RMAPI_RETRY_SLEEP_SECONDS", DEFAULT_RETRY_SLEEP))

    for attempt in (1, 2):  # at most one retry
        try:
            proc = subprocess.run(
                [binary] + list(args),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            raise RmapiError("rmapi binary not found: %s" % binary)
        except subprocess.TimeoutExpired:
            raise RmapiError("rmapi %s timed out after %ss" % (args[0], timeout))

        if proc.returncode == 0:
            return proc.stdout

        combined = (proc.stderr or "") + "\n" + (proc.stdout or "")
        if "NOT_AUTHENTICATED" in combined:
            raise RmapiAuthError(
                "rmapi is not authenticated. The tablet link needs a one-time code "
                "from https://my.remarkable.com/device/browser/connect — do not "
                "attempt to fix auth automatically."
            )
        if _is_rate_limited(combined) and attempt == 1:
            # reMarkable cloud rate-limits bursts: wait, retry ONCE, never hammer.
            sys.stderr.write(
                "[warn] rmapi rate-limited (429); retrying once in %.0fs\n" % retry_sleep
            )
            time.sleep(retry_sleep)
            continue
        tail = combined.strip().splitlines()[-1] if combined.strip() else "(no output)"
        raise RmapiError(
            "rmapi %s failed (exit %d): %s"
            % (" ".join(map(shlex.quote, args)), proc.returncode, tail)
        )
    raise RmapiError("rmapi failed after retry")  # unreachable


# --------------------------------------------------------------------------- #
# parsers (whitespace-tolerant; tested against the real formats above)        #
# --------------------------------------------------------------------------- #

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class Entry(object):
    __slots__ = ("name", "is_dir", "modified", "stat")

    def __init__(self, name, is_dir, modified=None, stat=None):
        self.name = name
        self.is_dir = is_dir
        self.modified = modified  # naive local datetime or None
        self.stat = stat          # parsed stat JSON dict or None


def parse_ls_plain(text):
    """Parse `rmapi ls` output: '[f]\\tname' / '[d]\\tname' (tab or spaces)."""
    entries = []
    for line in (text or "").splitlines():
        line = line.rstrip("\n")
        if not line.strip():
            continue
        m = re.match(r"^\[(d|f)\][\t ]+(.*)$", line)
        if not m:
            continue  # tolerate stray lines
        name = m.group(2).strip()
        if name.endswith("/"):
            name = name[:-1]
        entries.append(Entry(name, m.group(1) == "d"))
    return entries


def parse_ls_long(text):
    """Parse `rmapi ls -l` output: 'Sep  5 2026  17:13  name' (dirs end '/').

    Whitespace between fields is 1-2 spaces (Go layout 'Jan _2 2006  15:04  ');
    names may contain any number of spaces, so we maxsplit on the first 4 runs.
    """
    entries = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        parts = line.split(None, 4)
        if len(parts) < 5 or not re.match(r"^[A-Za-z]{3}$", parts[0]):
            # not a long-format line; fall back to plain parsing of this line
            plain = parse_ls_plain(line)
            if plain:
                entries.extend(plain)
            continue
        mon, day, year, hhmm, rest = parts
        month = MONTHS.get(mon.lower())
        modified = None
        try:
            hh, mm = hhmm.split(":")
            if month:
                modified = datetime(
                    int(year), month, int(day), int(hh), int(mm)
                )  # year 0001 (never-synced /trash) parses fine
        except ValueError:
            modified = None
        is_dir = rest.endswith("/")
        name = rest[:-1].strip() if is_dir else rest.strip()
        entries.append(Entry(name, is_dir, modified))
    return entries


def parse_find(text):
    """Parse `rmapi find` output: '[f] /a/b' or '[f] a/b' (leading slash
    present when the dir arg was '/', absent otherwise) -> normalized
    (is_dir, absolute_path_with_leading_slash)."""
    out = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        m = re.match(r"^\[(d|f)\]\s+(.+?)\s*/?\s*$", line)
        if not m:
            continue
        path = "/" + m.group(2).lstrip("/")
        out.append((m.group(1) == "d", path.rstrip("/")))
    return out


def parse_stat(text):
    """Parse `rmapi stat` JSON; return dict with modified_local added."""
    try:
        data = json.loads(text)
    except ValueError:
        raise RmapiError("cannot parse rmapi stat output: %r" % (text or "")[:120])
    modified_local = None
    mc = data.get("ModifiedClient")
    if mc:
        try:
            dt = datetime.strptime(mc, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            modified_local = dt.astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    data["modified_local"] = modified_local
    return data


def parse_account(text):
    """Parse 'User: forcewake@gmail.com, SyncVersion: 1.5' -> dict."""
    m = re.search(r"User:\s*(.+?),\s*SyncVersion:\s*([0-9.]+)", text or "")
    if not m:
        return {"user": (text or "").strip(), "sync_version": None}
    return {"user": m.group(1).strip(), "sync_version": m.group(2)}


# --------------------------------------------------------------------------- #
# higher-level operations (read-only)                                         #
# --------------------------------------------------------------------------- #

def normalize_folder(path):
    path = (path or "").strip() or "/Inbox"
    path = "/" + path.lstrip("/")
    path = re.sub(r"/+", "/", path)
    if len(path) > 1:
        path = path.rstrip("/")
    if path == "":
        path = "/"
    return path


def list_folder(folder, with_stat=False):
    """Return (entries, warnings). One `ls -l` call; optional per-file `stat`."""
    out = run_rmapi(["ls", "-l", folder])
    entries = parse_ls_long(out)
    if not entries:  # plain fallback for odd rmapi builds
        entries = parse_ls_plain(run_rmapi(["ls", folder]))

    names = [e.name for e in entries if not e.is_dir]
    dup_counts = {}
    for n in names:
        dup_counts[n] = dup_counts.get(n, 0) + 1

    warnings = []
    for n, c in dup_counts.items():
        if c > 1:
            warnings.append(
                'duplicate name %d x: "%s" (rmapi resolves only one entry per call)' % (c, n)
            )

    if with_stat:
        # stat enriches with ID / CurrentPage (reading progress) / Starred.
        # Small pause to stay polite to the cloud API.
        delay = float(os.environ.get("RMAPI_STAT_DELAY", "0.2"))
        for e in entries:
            if e.is_dir:
                continue
            try:
                e.stat = parse_stat(run_rmapi(["stat", folder + "/" + e.name]))
                if e.stat.get("modified_local"):
                    e.modified = e.stat["modified_local"]
                time.sleep(delay)
            except RmapiError as exc:
                warnings.append("stat failed for %r: %s" % (e.name, exc))
    return entries, warnings


def folder_exists(folder):
    """Check folder exists by listing its parent (read-only)."""
    parent = os.path.dirname(folder.rstrip("/")) or "/"
    name = folder.rstrip("/").rsplit("/", 1)[-1]
    try:
        entries = parse_ls_plain(run_rmapi(["ls", parent]))
    except RmapiError as exc:
        sys.stderr.write("[warn] cannot verify %s exists: %s\n" % (folder, exc))
        return True  # do not block the plan on a listing hiccup
    return any(e.is_dir and e.name == name for e in entries)


def parse_duration(spec):
    """'7d' -> 7 days, '2w' -> 14 days, '10' -> 10 days."""
    m = re.match(r"^(\d+)\s*([dw]?)$", (spec or "").strip().lower())
    if not m:
        raise ValueError("invalid duration %r (expected e.g. 7d or 2w)" % spec)
    n, unit = int(m.group(1)), m.group(2)
    return n * (7 if unit == "w" else 1)


# --------------------------------------------------------------------------- #
# subcommands                                                                 #
# --------------------------------------------------------------------------- #

def cmd_list(args):
    folder = normalize_folder(args.folder)
    entries, warnings = list_folder(folder, with_stat=args.stat)

    if args.json:
        payload = {
            "folder": folder,
            "count": len([e for e in entries if not e.is_dir]),
            "note": "rmapi v0.0.35 exposes no file size; size is null",
            "entries": [
                {
                    "name": e.name,
                    "type": "dir" if e.is_dir else "file",
                    "size": None,
                    "modified": e.modified.strftime("%Y-%m-%d %H:%M") if e.modified else None,
                    "duplicate": sum(1 for x in entries if x.name == e.name) > 1,
                    "current_page": (e.stat or {}).get("CurrentPage"),
                    "id": (e.stat or {}).get("ID"),
                }
                for e in sorted(
                    entries,
                    key=lambda e: (e.is_dir, e.modified or datetime.min, e.name),
                    reverse=True,
                )
            ],
            "warnings": warnings,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not entries:
        print("No entries in %s." % folder)
        return 0

    rows = [("Name", "Type", "Size", "Modified")]
    for e in sorted(entries, key=lambda e: (e.is_dir, e.modified or datetime.min, e.name), reverse=True):
        disp = e.name + ("/" if e.is_dir else "")
        if sum(1 for x in entries if x.name == e.name) > 1:
            disp += "  [duplicate]"
        page = ""
        if e.stat is not None and "CurrentPage" in e.stat:
            page = "  (page %s)" % e.stat["CurrentPage"]
        rows.append((
            disp + page,
            "dir" if e.is_dir else "file",
            "-",
            e.modified.strftime("%Y-%m-%d %H:%M") if e.modified else "unknown",
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    for i, r in enumerate(rows):
        print("  ".join(c.ljust(widths[j]) for j, c in enumerate(r)).rstrip())
        if i == 0:
            print("  ".join("-" * w for w in widths))
    for w in warnings:
        sys.stderr.write("[warn] %s\n" % w)
    return 0


def cmd_usage(args):
    account = parse_account(run_rmapi(["account"]))
    found = [p for d, p in parse_find(run_rmapi(["find", "/"])) if not d]

    counts = {}
    root_files = 0
    for path in found:
        parts = path.strip("/").split("/")
        top = parts[0] if len(parts) > 1 else None  # file directly in /
        if top is None:
            root_files += 1
        else:
            counts["/" + top] = counts.get("/" + top, 0) + 1

    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if args.json:
        print(json.dumps({
            "account": account,
            "note": "rmapi/account exposes no storage quota; counts are document counts",
            "documents_per_folder": [{"folder": k, "files": v} for k, v in ordered],
            "root_level_files": root_files,
            "total_documents": sum(counts.values()) + root_files,
        }, ensure_ascii=False, indent=2))
        return 0

    print("Account:")
    print("  User:         %s" % account["user"])
    print("  SyncVersion:  %s" % account["sync_version"])
    print("  (rmapi v0.0.35 exposes no storage quota — showing document counts)")
    print("Documents per top-level folder:")
    width = max([len(k) for k, _ in ordered] + [12])
    for k, v in ordered:
        print("  %s  %4d" % (k.ljust(width), v))
    print("  %s  %4d" % ("(root files)".ljust(width), root_files))
    print("Total documents: %d in %d folders (+%d root files)"
          % (sum(counts.values()), len(counts), root_files))
    return 0


NAME_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def effective_date(entry, trust_name_dates):
    """mtime, or the name-embedded date when it is OLDER than mtime and
    --trust-name-dates is set (upload pipelines refresh mtimes, e.g. the
    Daily Intelligence re-upload makes stale digests look fresh)."""
    if not trust_name_dates or entry.modified is None:
        return entry.modified, False
    dates = NAME_DATE_RE.findall(entry.name)
    if not dates:
        return entry.modified, False
    try:
        named = datetime.strptime(dates[-1], "%Y-%m-%d")
    except ValueError:
        return entry.modified, False
    if named.date() < entry.modified.date():
        return named, True
    return entry.modified, False


def build_plan(folder, older_than, delete_after, destination, trust_name_dates=False):
    """Build the archive/delete plan. Pure read-only listing + date math."""
    entries, warnings = list_folder(folder, with_stat=False)
    files = [e for e in entries if not e.is_dir]
    now = datetime.now()
    cutoff_archive = now - timedelta(days=older_than)
    cutoff_delete = now - timedelta(days=delete_after) if delete_after else None

    dup_counts = {}
    for e in files:
        dup_counts[e.name] = dup_counts.get(e.name, 0) + 1

    archive, delete, keep, unknown = [], [], [], []
    for e in files:
        eff, by_name = effective_date(e, trust_name_dates)
        if eff is None:
            unknown.append(e)
        elif cutoff_delete is not None and eff < cutoff_delete:
            delete.append(e)
        elif eff < cutoff_archive:
            archive.append(e)
        else:
            keep.append(e)

    # Real-world trap (observed on /Daily Intelligence): the upload pipeline
    # refreshes mtimes, so a stale digest looks "new". If the NAME embeds a
    # date older than the cutoff but mtime kept it in `keep`, warn loudly.
    for e in keep:
        dates = NAME_DATE_RE.findall(e.name)
        if not dates:
            continue
        try:
            named = datetime.strptime(dates[-1], "%Y-%m-%d")
        except ValueError:
            continue
        if named.date() < cutoff_archive.date():
            warnings.append(
                '"%s": mtime is %s but name says %s (older than cutoff) — '
                "skipped because mtime looked fresh; mtime may have been "
                "refreshed by a re-upload. Use --trust-name-dates to act on "
                "the name date." % (e.name, e.modified.date(), named.date())
            )

    for n, c in dup_counts.items():
        if c > 1:
            warnings.append(
                'name occurs %dx: "%s" — mv/rm act on one entry per invocation; '
                "a command is emitted per occurrence" % (c, n)
            )

    dest_missing = archive and not folder_exists(destination)

    commands = []
    if dest_missing:
        commands.append(["mkdir", destination])  # BEFORE the first mv
    commands.extend(["mv", folder + "/" + e.name, destination] for e in archive)
    commands.extend(["rm", folder + "/" + e.name] for e in delete)

    return {
        "folder": folder,
        "destination": destination,
        "older_than_days": older_than,
        "delete_after_days": delete_after,
        "archive": archive,
        "delete": delete,
        "keep": keep,
        "unknown": unknown,
        "warnings": warnings,
        "dup_counts": dup_counts,
        "dest_missing": dest_missing,
        "commands": commands,
    }


def cmd_plan_archive(args):
    folder = normalize_folder(args.folder)
    destination = normalize_folder(args.destination)
    if destination == folder:
        sys.stderr.write("error: destination must differ from folder\n")
        return 1
    try:
        older_than = parse_duration(args.older_than)
        delete_after = parse_duration(args.delete_older_than) if args.delete_older_than else None
    except ValueError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1

    plan = build_plan(folder, older_than, delete_after, destination,
                      trust_name_dates=args.trust_name_dates)
    pretty_cmds = [shlex.join(c) for c in plan["commands"]] if plan["commands"] else []

    if args.json:
        print(json.dumps({
            "folder": folder,
            "destination": destination,
            "older_than_days": older_than,
            "delete_after_days": delete_after,
            "archive": [
                {"name": e.name, "modified": e.modified.strftime("%Y-%m-%d %H:%M"),
                 "path": folder + "/" + e.name}
                for e in plan["archive"]
            ],
            "delete": [
                {"name": e.name, "modified": e.modified.strftime("%Y-%m-%d %H:%M"),
                 "path": folder + "/" + e.name}
                for e in plan["delete"]
            ],
            "keep": len(plan["keep"]),
            "unknown_date_skipped": [e.name for e in plan["unknown"]],
            "warnings": plan["warnings"],
            "mkdir_destination": plan["dest_missing"],
            "commands": pretty_cmds,
            "trust_name_dates": bool(args.trust_name_dates),
            "dry_run": not args.execute,
        }, ensure_ascii=False, indent=2))

    if not args.json:
        mode = "EXECUTE" if args.execute else "DRY RUN — nothing will be executed"
        print("Reading-queue archive plan (%s)" % mode)
        print("Folder: %s   older-than: %dd   delete-after: %s   destination: %s"
              % (folder, older_than,
                 ("%dd" % delete_after) if delete_after else "none",
                 destination))
        print()
        print("Would MOVE to %s (%d):" % (destination, len(plan["archive"])))
        for e in sorted(plan["archive"], key=lambda e: e.modified or datetime.min):
            tag = "  [duplicate]" if plan["dup_counts"].get(e.name, 1) > 1 else ""
            print("  %s  %s%s" % (e.modified.strftime("%Y-%m-%d %H:%M"), e.name, tag))
        print("Would DELETE (%d):" % len(plan["delete"]))
        for e in sorted(plan["delete"], key=lambda e: e.modified or datetime.min):
            tag = "  [duplicate]" if plan["dup_counts"].get(e.name, 1) > 1 else ""
            print("  %s  %s%s" % (e.modified.strftime("%Y-%m-%d %H:%M"), e.name, tag))
        print("Keep (%d), unknown-date skipped (%d)"
              % (len(plan["keep"]), len(plan["unknown"])))
        for w in plan["warnings"]:
            sys.stderr.write("[warn] %s\n" % w)
        print()
        if plan["commands"]:
            print("Exact rmapi commands (in order):")
            for i, c in enumerate(pretty_cmds, 1):
                print("  %d. %s" % (i, c))
        else:
            print("No rmapi commands needed (nothing to move or delete).")
        if not args.execute:
            print()
            print("DRY RUN: no changes were made. Re-run with --execute to apply.")

    if args.execute:
        return execute_plan(plan)
    return 0


def execute_plan(plan):
    """Run the planned mkdir/mv/rm commands. Abort on first failure."""
    ok, failed = 0, None
    for cmd in plan["commands"]:
        print("RUN: %s" % shlex.join(cmd))
        try:
            run_rmapi(cmd, allow_write=True)
            print("  OK")
            ok += 1
        except RmapiError as exc:
            sys.stderr.write("  FAIL: %s\n" % exc)
            failed = cmd
            break
    print("Executed %d/%d commands%s."
          % (ok, len(plan["commands"]),
             " — stopped at first failure" if failed else ""))
    if failed is not None:
        sys.stderr.write("error: aborting; remaining commands were not run\n")
        return 1
    return 0


# --------------------------------------------------------------------------- #
# cli                                                                         #
# --------------------------------------------------------------------------- #

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="remarkable_manage.py",
        description="reMarkable reading-queue manager (rmapi wrapper). "
                    "Mutations require plan-archive --execute.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="list a folder: name, size, modified")
    p_list.add_argument("--folder", default="/Inbox")
    p_list.add_argument("--stat", action="store_true",
                        help="enrich files with rmapi stat (ID, reading page)")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_usage = sub.add_parser("usage", help="account + per-folder document counts")
    p_usage.add_argument("--json", action="store_true")
    p_usage.set_defaults(func=cmd_usage)

    p_plan = sub.add_parser("plan-archive",
                            help="plan moving stale read items to /Read (dry-run by default)")
    p_plan.add_argument("--folder", default="/Inbox")
    p_plan.add_argument("--older-than", default="7d",
                        help="items older than this move to destination (default 7d)")
    p_plan.add_argument("--delete-older-than", default=None,
                        help="items older than this are deleted instead (e.g. 30d)")
    p_plan.add_argument("--destination", default="/Read")
    p_plan.add_argument("--trust-name-dates", action="store_true",
                        help="when a name embeds a date (YYYY-MM-DD) older than "
                             "mtime (re-upload refreshes mtimes, e.g. Daily "
                             "Intelligence), use the name date for staleness")
    p_plan.add_argument("--execute", action="store_true",
                        help="ACTUALLY run mkdir/mv/rm on the tablet (default: dry-run)")
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=cmd_plan_archive)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except RmapiAuthError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    except RmapiError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
