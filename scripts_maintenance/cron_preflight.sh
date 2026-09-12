#!/bin/bash
# Preflight check for the ASCL v3 maintenance cron jobs.
#
# Run ON THE PRODUCTION HOST:
#     bash ~/repositories/ascl_app_v4/scripts_maintenance/cron_preflight.sh
#
# crontab.example is the source of truth for what should be installed. This
# script reads it, compares it against the crontab that IS installed, and
# checks every precondition a run depends on. Exits non-zero naming what failed.

set -u

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
reference="$here/crontab.example"
fails=0

ok()    { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
bad()   { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; fails=$((fails + 1)); }
warn()  { printf '  \033[33mWARN\033[0m  %s\n' "$*"; }
head_() { printf '\n== %s\n' "$*"; }

[[ -f $reference ]] || { echo "FATAL: $reference not found"; exit 1; }

PY=$(sed -n 's/^PY=//p'      "$reference" | tail -1)
SCRIPTS=$(sed -n 's/^SCRIPTS=//p' "$reference" | tail -1)

# ---------------------------------------------------------------------------
head_ "Installed crontab vs. crontab.example"
if live=$(crontab -l 2>/dev/null); then
    if diff -q <(printf '%s\n' "$live") "$reference" >/dev/null 2>&1; then
        ok "installed crontab matches crontab.example byte for byte"
    else
        warn "installed crontab DIFFERS from crontab.example:"
        diff <(printf '%s\n' "$live") "$reference" | sed 's/^/        /'
        echo "        Install the reference with:  crontab $reference"
    fi

    # The failure mode that silently kills every job: cron assigns variable
    # values literally (crontab(5) -- no variable, tilde or command
    # substitution), and the shell expands $SCRIPTS exactly once, so a $HOME
    # hiding inside the value reaches argv verbatim.
    if printf '%s\n' "$live" | grep -qE '^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=.*[$~]'; then
        bad "installed crontab has \$ or ~ inside a variable assignment:"
        printf '%s\n' "$live" \
            | grep -nE '^[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=.*[$~]' | sed 's/^/        /'
        echo "        cron will not expand these. Use absolute paths."
    else
        ok "no \$ or ~ inside installed variable assignments"
    fi

    if printf '%s\n' "$live" | grep -q 'python2'; then
        bad "installed crontab still calls python2 — these scripts are Python 3 only"
    fi

    n_mailto=$(printf '%s\n' "$live" | grep -cE '^MAILTO=')
    if [[ $n_mailto -gt 1 ]]; then
        bad "$n_mailto MAILTO lines — cron keeps only the LAST; the others get no mail"
    fi

    if ! printf '%s\n' "$live" | grep -q 'cron_wrap.sh'; then
        warn "installed crontab bypasses cron_wrap.sh — no run logging, no locking,"
        echo "        and cron will mail full output on every successful run"
    fi
else
    warn "could not read the installed crontab (crontab -l failed)"
fi

# ---------------------------------------------------------------------------
head_ "Interpreter and paths"
echo "  HOME    = $HOME"
echo "  PY      = $PY"
echo "  SCRIPTS = $SCRIPTS"

if [[ -x $PY ]]; then
    ok "python is executable: $("$PY" --version 2>&1)"
    "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)' \
        && ok "python >= 3.13 (link_checker_async.py requirement)" \
        || warn "python < 3.13; link_checker_async.py documents 3.13+"
else
    bad "python not found or not executable at: $PY"
fi

[[ -d $SCRIPTS ]] && ok "script directory exists" \
                  || bad "script directory does NOT exist: $SCRIPTS"

if [[ -x $SCRIPTS/cron_wrap.sh ]]; then
    ok "cron_wrap.sh is executable"
elif [[ -f $SCRIPTS/cron_wrap.sh ]]; then
    bad "cron_wrap.sh exists but is NOT executable — every job dies with exit 126"
    echo "        fix: chmod +x $SCRIPTS/cron_wrap.sh"
else
    bad "cron_wrap.sh missing at $SCRIPTS/cron_wrap.sh"
fi

# ---------------------------------------------------------------------------
head_ "Scheduled scripts"
targets=$(grep -oE '\$SCRIPTS/v3/[A-Za-z0-9_]+\.py' "$reference" | sed 's|\$SCRIPTS/||' | sort -u)
[[ -n $targets ]] || bad "no scheduled scripts parsed out of crontab.example"
for t in $targets; do
    [[ -f "$SCRIPTS/$t" ]] && ok "$t present" \
                           || bad "$t MISSING at $SCRIPTS/$t"
done
for helper in v3/db_config.py v3/phpserialize.py; do
    [[ -f "$SCRIPTS/$helper" ]] && ok "$helper present (imported by the v3 scripts)" \
                                || bad "$helper MISSING at $SCRIPTS/$helper"
done

# ---------------------------------------------------------------------------
head_ "Python dependencies (in $PY)"
if [[ -x $PY ]]; then
    for mod in ads peewee httpx pymysql requests; do
        "$PY" -c "import $mod" 2>/dev/null \
            && ok "import $mod" \
            || bad "import $mod  --  $PY -m pip install $mod"
    done
fi

# ---------------------------------------------------------------------------
head_ "Credentials"
cnf="$HOME/.my.cnf"
if [[ -f $cnf ]]; then
    perms=$(stat -c '%a' "$cnf" 2>/dev/null || stat -f '%Lp' "$cnf")
    ok "~/.my.cnf present (mode $perms)"
    [[ $perms == 600 ]] || warn "~/.my.cnf is mode $perms; should be 600"

    grep -q '^\[client_ascl\]' "$cnf" \
        && ok "[client_ascl] section present" \
        || warn "no [client_ascl] section; db_config.py will fall back to [client]"

    # These scripts write the v3 schema. A `database` key naming ascl_db_v4
    # would silently point them at the v4 database.
    if grep -qE '^[[:space:]]*database[[:space:]]*=[[:space:]]*ascl_db_v4' "$cnf"; then
        bad "~/.my.cnf sets database = ascl_db_v4 — the v3 scripts must NOT write there"
    else
        ok "~/.my.cnf does not point the v3 scripts at ascl_db_v4"
    fi
else
    bad "~/.my.cnf missing — all three scripts read credentials from it"
fi

[[ -f $HOME/.ads/dev_key ]] \
    && ok "~/.ads/dev_key present (ascl_citations.py)" \
    || bad "~/.ads/dev_key missing — ascl_citations.py cannot reach NASA ADS"

# citefile_metadata.py probes raw.githubusercontent.com, not api.github.com,
# so the 60 req/hr unauthenticated API limit does not apply and no token is
# required. Note that cron does not read ~/.bash_profile: if a token is ever
# wanted, it has to be set in the crontab, not the shell profile.
[[ -n ${GITHUB_TOKEN:-} ]] \
    && ok "GITHUB_TOKEN set (optional; raw.githubusercontent.com is not API-rate-limited)" \
    || ok "GITHUB_TOKEN unset — fine; citefile_metadata.py uses raw.githubusercontent.com"

# ---------------------------------------------------------------------------
head_ "Run history"
hist="$SCRIPTS/logs/cron_history.log"
if [[ -f $hist ]]; then
    ok "cron_history.log exists — last 10 entries:"
    tail -n 10 "$hist" | sed 's/^/        /'
else
    warn "no $hist — cron_wrap.sh has never completed a run on this host"
fi
if [[ -d $SCRIPTS/logs ]]; then
    [[ -w $SCRIPTS/logs ]] && ok "logs/ is writable" \
                           || bad "logs/ is NOT writable — cron_wrap.sh exits 2"
else
    warn "logs/ does not exist yet (cron_wrap.sh creates it on first run)"
fi

# ---------------------------------------------------------------------------
head_ "Mail delivery"
# A broken job writes to stderr and cron mails it. Silence therefore means
# either the jobs never fired or mail is not leaving the host.
if command -v sendmail >/dev/null 2>&1 || command -v mail >/dev/null 2>&1; then
    ok "an MTA is present (sendmail/mail on PATH)"
else
    bad "no sendmail or mail on PATH — cron cannot deliver failure mail,"
    echo "        which would explain silence even while jobs are failing"
fi

# ---------------------------------------------------------------------------
head_ "Startability under a cron-like environment"
# NOTE: --dry-run on these scripts means "skip database writes", NOT "skip the
# work". citefile_metadata.py still crawls GitHub for every code with a repo
# URL, and link_checker_async.py still fetches every URL in the database. A
# preflight must not do that: it burns the GitHub rate limit and takes as long
# as the real job. Check that each script can START instead, then exercise the
# one script that has a real limit flag against a handful of rows.
cronenv=(env -i HOME="$HOME" SHELL=/bin/bash PATH=/usr/local/bin:/usr/bin:/bin)

if [[ -x $PY && -d $SCRIPTS ]]; then
    for t in $targets; do
        [[ -f "$SCRIPTS/$t" ]] || continue
        out=$(mktemp)
        if "${cronenv[@]}" "$PY" -m py_compile "$SCRIPTS/$t" >"$out" 2>&1; then
            ok "$t compiles"
        else
            bad "$t does NOT compile:"; sed 's/^/        /' "$out" | tail -10
        fi
        rm -f "$out"
    done

    # Imports resolve only if the script's own directory is on sys.path the way
    # python puts it there for a script run by absolute path.
    out=$(mktemp)
    if "${cronenv[@]}" "$PY" -c "
import sys; sys.path.insert(0, '$SCRIPTS/v3')
import db_config, pymysql
cfg = db_config.read_db_config()
conn = pymysql.connect(**db_config.pymysql_kwargs(cfg))
cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM codes')
print(cfg['database'], cur.fetchone()[0])
" >"$out" 2>&1; then
        read -r dbname ncodes < "$out"
        ok "connected to MySQL as cron would: database=$dbname, codes=$ncodes"
        [[ $dbname == ascl_db_v4 ]] && bad "connected to ascl_db_v4 — the v3 scripts must not write there"
    else
        bad "could not connect to MySQL with db_config.py:"; sed 's/^/        /' "$out" | tail -10
    fi
    rm -f "$out"

    # citefile_metadata.py is the only one with a bounded mode.
    if [[ -f "$SCRIPTS/v3/citefile_metadata.py" ]]; then
        out=$(mktemp)
        if "${cronenv[@]}" "$PY" "$SCRIPTS/v3/citefile_metadata.py" \
               --dry-run --limit 3 >"$out" 2>&1; then
            ok "citefile_metadata.py --dry-run --limit 3 exited 0"
        else
            bad "citefile_metadata.py --dry-run --limit 3 exited $? — last 20 lines:"
            tail -20 "$out" | sed 's/^/        /'
        fi
        rm -f "$out"
    fi
else
    warn "skipped startability checks (interpreter or script directory missing)"
fi

# ---------------------------------------------------------------------------
head_ "Result"
if [[ $fails -eq 0 ]]; then
    echo "  All checks passed."
    exit 0
fi
echo "  $fails check(s) failed — see FAIL lines above."
exit 1
