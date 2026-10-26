"""Lonely Planner QA · shared references for every suite (versions, git baselines) · version 1.0.0
CHANGE 2026-10-26 QA-DEBT-01: new file (no previous version). The one place that says
  (1) which app version the CURRENT tree must carry (CURRENT_VERSION, from tests/qa_versions.json) — older suites'
      APP_VERSION / PT_VERSION pins read it instead of the version they were written for (bump the JSON once per release);
  (2) where the offline "before" references live in the repo history (git refs, no network):
      - V2152_REF: the v2.15.2 reference for the protected functions (drawMap, drawGoogleMap, drawSchematicMap,
        fallbackToSchematic, SEED_DATA, stayBlock, bookingUrl). The repo never contained v2.15.2 itself; e711542 is the first
        commit with app/ (F02, 3.0.0-alpha.2, built from v2.15.2). Its 7 protected declarations were verified byte-identical
        to v2.15.2 (orsela/Vietnam_Travel_Planner 630a8d8 'v2.15.2: … DAY-TODAY-01', APP_VERSION='2.15.2') on 2026-10-26, and
        every later app/index.html commit still matches them. So "byte-identical to e711542" == "byte-identical to v2.15.2".
      - per-feature "before" refs that the suites' static checks (duplicate ids, CHANGE hunks) compare against.
Nothing here talks to the network.
"""
import os
import re
import subprocess
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(TESTS_DIR.parent)))

# The versions the tree under test must carry come from tests/qa_versions.json (shared with the TypeScript function tests).
# Live main 1403761 = app 3.0.0-alpha.7.1. QA_EXPECTED_VERSION overrides the app version (e.g. to run on an older worktree).
import json  # noqa: E402
VERSIONS = json.loads((TESTS_DIR / "qa_versions.json").read_text(encoding="utf-8"))
CURRENT_VERSION = os.environ.get("QA_EXPECTED_VERSION", VERSIONS["app"])
FN_VERSIONS = VERSIONS["functions"]

PROTECTED = ["drawMap", "drawGoogleMap", "drawSchematicMap", "fallbackToSchematic", "SEED_DATA", "stayBlock", "bookingUrl"]

V2152_REF = os.environ.get("V2152_REF", "e711542")   # protected-function baseline (== v2.15.2, see header)
REFS = {                                             # last app commit of each version used as a "before" by a suite
    "3.0.0-alpha.2": "9b8151b",     # F03 suite ALPHA2_REF
    "3.0.0-alpha.3.4": "e591edc",   # F04 suite ALPHA3_REF
    "3.0.0-alpha.4.2": "a7c7a32",   # F20 suite MAIN_REF
    "3.0.0-alpha.5.1": "4bd04e4",   # F05 suite MAIN_REF (parent of 59ebf13, the F05 client commit)
    "3.0.0-alpha.7": "ee5c723",     # F04-HOME suite BASE_REF
}


def git_show(ref, path="app/index.html", repo=None):
    r = subprocess.run(["git", "-C", str(repo or REPO_DIR), "show", "%s:%s" % (ref, path)], capture_output=True)
    if r.returncode:
        raise AssertionError("harness: cannot read %s:%s from git: %s" % (ref, path, r.stderr.decode()[:200]))
    return r.stdout.decode("utf-8")


def v2152_html(repo=None):
    """app/index.html at V2152_REF — the offline source of the v2.15.2 protected declarations (and SEED_DATA)."""
    html = git_show(V2152_REF, "app/index.html", repo)
    assert re.search(r"const APP_VERSION='3\.0\.0-alpha\.2'", html) and "v2.15.2" in html, \
        "harness: %s is not the F02 app built from v2.15.2" % V2152_REF
    return html


def version_re(name="APP_VERSION"):
    return r"""%s\s*=\s*['"]%s['"]""" % (name, re.escape(CURRENT_VERSION))
