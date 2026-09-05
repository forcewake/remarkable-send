# rmapi operations (reMarkable cloud)

Transport for everything this skill sends. Binary: `~/bin/rmapi`
(ddvk/rmapi fork v0.0.35 — the original juruen/rmapi is dead: reMarkable
changed its token exchange; do not "upgrade" to it).

## Auth

- Config: `~/.config/rmapi/rmapi.conf` (device token). Already authenticated
  on deerflow-vm; tokens are long-lived.
- Re-auth when expired: user opens https://my.remarkable.com/device/browser/connect
  (8-letter code, ~5 min TTL), then:
  `echo CODE | ~/bin/rmapi ls /` — an ONLINE command is required to trigger
  the login flow (`version` is offline and does nothing).
- Requires reMarkable Connect subscription for cloud sync to the tablet.

## Command facts (verified 2026-09-05)

| Operation | Command | Note |
|---|---|---|
| List folder | `rmapi ls "/Inbox"` | refreshes tree automatically |
| Make folder | `rmapi mkdir "/Inbox"` | idempotent; engine runs it before every put |
| Upload | `rmapi put --force <local.pdf> "/Inbox"` | `--force` overwrites same name |
| Delete | `rmapi rm "/Inbox/<name>"` | glob-matches, may delete several copies |
| Delete folder | `rmapi rm -r "/Inbox"` | contents may linger at root — list and clean |

## Traps (hit every one of these already)

1. **Em-dash "—" in file names breaks name matching**: `rm` and `put --force`
   fail to match → silent duplicates pile up. File names must use plain
   hyphens. The engine slugifies; never bypass it.
2. **429 rate limiting** on bursts (several uploads/deletes in a row):
   wait 60 s, retry once. Batch loops must sleep ~20 s between files.
3. `put` without `--force` errors `entry already exists` when the name is taken.
4. After mass deletes, run `rmapi refresh` before trusting `ls` output —
   the cached tree lags.
5. There is no move between folders on the device for uploaded docs —
   pick the right folder at upload time.

## Queue manager (`scripts/remarkable_manage.py`)

stdlib-only wrapper for reading and (dry-run by default) archiving:
`list [--json]`, `usage` (per-folder doc counts — rmapi v0.0.35 exposes no
sizes/quota), `plan-archive [--older-than 7d] [--delete-older-than 30d]
[--destination /Read] [--execute] [--trust-name-dates]`. Mutations only
with `--execute`; `mkdir /Read` precedes the first `mv`; duplicates get one
command per occurrence and are flagged.

Facts baked into its parsers (live-verified): `ls` = `[f]\t<name>`, no
dates, shows duplicates; `ls -l` = `Sep  5 2026  17:13  <name>`; `stat` =
JSON with `ModifiedClient` UTC + `CurrentPage` (reading progress);
`find /` omits the leading slash for folder args, keeps it for `/`.

**Daily Intelligence trap**: the pipeline refreshes digest mtimes, so
mtime-based archiving skips stale digests — use `--trust-name-dates` (acts
on the date embedded in the file name).

## Verification on this host

```bash
~/bin/rmapi ls "/Inbox"        # file present
~/bin/rmapi version            # v0.0.35 (ddvk)
ls ~/.config/rmapi/rmapi.conf  # authenticated
```
