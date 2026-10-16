"""Plan_Travel F04 QA · Playwright black-box suite · version 1.4.0
CHANGE 2026-10-12 F04-QA: first version (no previous version).
CHANGE 2026-10-12 F04-QA-03: 1.0.0 → 1.1.0, follows the two spec changes approved by Or after the first run:
  - F04-DB-02: the fake create-trip (F04Backend.create_trip_from_invite) now also writes trip_kv `tripname` = the trimmed
    trip name (spec §2 step 5). New test_c11_tripname_shown_home_and_settings[v1|v2] (criterion 11): the v1 home header
    #tripName and ניהול → הגדרות מסע show the entered name, never the fallback "מסע של חלומות".
  - F04-INV-02: TXT["inv_note"] is the new /invite/ note ('…ולבחור "כניסה עם הזמנה".'); test_c16_invite_page_button_opens_app
    also asserts the old wording "קיבלתי הזמנה לנהל טיול" is gone (criterion 16).
CHANGE 2026-10-12 F04-QA-04: 1.1.0 → 1.2.0, follows alpha.4.1 (spec §1.8 F04-HOME-04, dev notes §8):
  - VERSION pin 3.0.0-alpha.4 → 3.0.0-alpha.4.1 (APP_VERSION / PT_VERSION / <title>, test_c21_static).
  - TXT["to_route"] "למסלול" → "הוספת נקודה" (#ptFsRoute); test_c13_enter_trip_home now expects day 1 + the
    "הוספת נקודת עניין" modal (#waypointModal.open, title "· יום 1") and home after closing it, instead of the route tab;
    test_c20_layout_390_rtl_touch[home] anchors the card on the new button text.
  - New: test_c13_fs_row3_opens_add_point[tap|enter|space], test_c13_fs_row3_without_device_user,
    test_c13_fs_row2_tap_marks_shared, test_c13_fs_rows_tappable_only_when_open (role/tabindex/‹/≥44px at 390px).
CHANGE 2026-10-12 F04-QA-05: 1.2.0 → 1.3.0, follows alpha.4.2 (spec §8 app name "Lonely Planner", §8.1 new address):
  - f02.APP_PATH is now /Lonely_Planner/; JOIN_BASE → https://orsela.github.io/Lonely_Planner/join/; VERSION → alpha.4.2;
    test_c21_static[title_version] now asserts <title> == "Lonely Planner" exactly (the version is no longer in it);
    test_c16_join_page… expects the brand "Lonely Planner" (was "Plan_Travel").
  - New: test_n01_no_old_name_rendered[<screen>] (no "Plan_Travel" / "Vietnam Travel Planner" / app-name "ויאטנם 2026" on
    the landing, gate, wizard, done, first-steps card, עוד sheet, admin, /invite/, /join/; brand present where the spec
    puts it), test_n02_static_names[…] (manifest name/short_name, apple-mobile-web-app-title, /invite/ + /join/ <title>),
    test_n03_whatsapp_text_name_and_url[done|card|sheet], test_n04_old_address_redirects[…] (ops/old_address_redirect
    served at /Plan_Travel/, https://orsela.github.io/Lonely_Planner/** intercepted locally).
CHANGE 2026-10-13 F20-QA-02: 1.3.0 → 1.4.0, follows F20 (app 3.0.0-alpha.5, docs/F20_spec.md) only where F20 changes
  behaviour on purpose: VERSION pin → 3.0.0-alpha.5; test_c19_boot_prefers_cached_trip_only_when_on[off] expects the CACHED
  trip when the served app has SWITCH_FEATURE='on' (architect decision 2026-10-13, F20 dev notes §6.6: with
  WIZARD_FEATURE='off' + SWITCH_FEATURE='on' a non-admin boots the still-active cached trip so a switch sticks); with
  SWITCH_FEATURE='off' it still expects alpha.3 (the newest membership). The admin path of test_n01[admin] goes through
  the F03 harness helpers (F03 suite 1.0.3: chooser / switcher entry).

Black-box acceptance tests for docs/F04_spec.md §5 (criteria 1–16, 19, 20 from the browser side, plus the static part
of 21), written from the spec and the approved mockup artboards F04_* only. NOT read: app/index.html, invite/index.html,
join/index.html, docs/F04_dev_notes.md, migrations 0010/0011, supabase/functions/create-trip/index.ts. The alpha.3 app
(git ref ALPHA3_REF) is the "before" reference for protected functions.

Layout (reuses the F03 harness, imported as a module from ../f03/test_f03.py, which itself imports the F02 harness):
- f02.Server serves APP_DIR under /Plan_Travel/; /invite/ and /join/ are served from REPO_DIR through Server.overrides;
  flag-flipped copies (WIZARD_FEATURE='off') are served through Server.overrides too.
- The supabase-js CDN request is fulfilled with tests/f04/fake_supabase.js (F03 fake + verifyOtp / signInWithOtp /
  resend / auth trace / trip_join_codes).
- F04Backend (below) extends F03Backend with: email OTP (updateUser email_change → verifyOtp, email_exists when the
  address belongs to another account, signInWithOtp {shouldCreateUser:false} → verifyOtp type 'email' that switches the
  session to that account), scripted rate limits, `trip_join_codes` / `trip_currencies` / `trip_countries` under RLS-like
  rules, invite-manager `check` returning `email`, and a fake `create-trip` function implementing spec §2/§3.1 in memory
  (lookup / create, validation, cap 10, idempotency, invite re-check, rate limits, days generation, join codes). It is
  reachable through a route-intercepted POST <PT_URL>/functions/v1/create-trip and through
  supabase.functions.invoke('create-trip'). Counters: be.ct_calls, be.trips_created, be.auth_sends(), be.traces.
- Clocks: the browser clock is INSTALLED at FIXED_NOW (time flows; tests advance it with run_for / fast_forward for the
  45 s resend cooldown and the 1 h code validity). The fake backend's clock is fixed at FIXED_NOW.
- OTP errors are realistic: GoTrue answers a wrong code and an expired code with the SAME error
  (403 otp_expired "Token has expired or is invalid"); the app has to tell them apart by time since sending (open
  question in the QA report).

Selectors: UI is located by visible Hebrew text from the spec / mockups. Everything that may need adjusting after the
dev notes is in the SEL / TXT blocks right below.

Env: APP_DIR (default <repo>/app), REPO_DIR (default: two levels up), ALPHA3_REF (default e591edc = app 3.0.0-alpha.3.4),
QA_HEADFUL=1 to watch.
"""
import copy
import datetime as dt
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pytest

HERE = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("REPO_DIR", str(HERE.parent.parent)))
os.environ.setdefault("APP_DIR", str(REPO_DIR / "app"))
os.environ.setdefault("PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS", "1")

_spec = importlib.util.spec_from_file_location("f03_harness", str(REPO_DIR / "tests" / "f03" / "test_f03.py"))
f03 = importlib.util.module_from_spec(_spec)
sys.modules["f03_harness"] = f03
_spec.loader.exec_module(f03)
f02 = f03.f02

from playwright.sync_api import Error as PWError  # noqa: E402

FAKE_JS = (HERE / "fake_supabase.js").read_text(encoding="utf-8")
APP_DIR = Path(os.environ["APP_DIR"])
APP_PATH = f02.APP_PATH
PT_URL, PT_KEY = f02.PT_URL, f02.PT_KEY
IM_URL = PT_URL + "/functions/v1/invite-manager"
CT_URL = PT_URL + "/functions/v1/create-trip"
JOIN_BASE = "https://orsela.github.io/Lonely_Planner/join/"  # CHANGE 2026-10-12 F04-QA-05: was /Plan_Travel/join/
VERSION = "3.0.0-alpha.5"  # CHANGE 2026-10-13 F20-QA-02: was 3.0.0-alpha.4.2 (F04-QA-05: was 3.0.0-alpha.4.1; F04-QA-04: was 3.0.0-alpha.4)
APP_NAME = "Lonely Planner"  # CHANGE 2026-10-12 F04-QA-05: spec §8
OLD_NAMES = ["Plan_Travel", "Vietnam Travel Planner"]  # CHANGE 2026-10-12 F04-QA-05: never rendered as the app name
ALPHA3_REF = os.environ.get("ALPHA3_REF", "e591edc")
PROTECTED = f02.PROTECTED
VIEWPORT = f02.VIEWPORT
SEED_MARKERS = ["טיסה להאנוי", "נחיתה והרובע העתיק", "כפר הקטורת ובובות מים"]  # SEED_DATA day titles (alpha.3)

FIXED_NOW = dt.datetime(2026, 10, 12, 6, 0, 0, tzinfo=dt.timezone.utc)  # 09:00 Jerusalem
DAY = dt.timedelta(days=1)
INVITE_EMAIL = "dana@example.com"
DRAFT = "יפן 2027"
OTP = "482913"
JOIN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
BASES = ("ILS", "USD", "EUR")
POPULAR_ORDER = ["TH", "GR", "US", "IT", "ES", "FR", "GB", "DE", "PT", "CY", "GE", "VN", "JP", "IN", "NL", "CZ", "HU",
                 "AT", "MX", "AE"]

# =====================================================================================================
# Selectors and texts — ADJUST HERE after reading the F04 dev notes (everything else uses these names)
# =====================================================================================================
SEL = {
    "otp": 'input[inputmode="numeric"]',                           # §1.3: 6 single-digit inputs
    "email_input": 'input[type="email"]',                          # §1.3 email state (LTR)
    "date_inputs": 'input[type="date"]',                           # §1.4: native date inputs, יציאה then חזרה
    "country_search": 'input[placeholder*="חיפוש"], input[type="search"]',  # §1.5 search (mockup placeholder)
    "currency_select": "select",                                   # §1.4 מטבע הבית
    "remove_aria": "הסרת {he}",                                     # §1.5 × button aria-label (mockup)
    "trip_chrome": [".tabs", "#chatFab", "#globalFxBtn"],          # same as F03
}
TXT = {
    # gate (§1.2)
    "gate_title": "קיבלת הזמנה לנהל טיול?",
    "gate_text": "נאמת את המייל שאליו נשלחה ההזמנה, ותקים את הטיול מכאן.",
    "gate_btn": "כניסה עם הזמנה",
    "gate_badge": "חדש · F04",
    # email + code (§1.3)
    "email_label": "המייל שאליו נשלחה ההזמנה",
    "send_code": "שליחת קוד",
    "code_title": "הקוד נשלח למייל",
    "code_expl": "שלחנו קוד בן 6 ספרות. מקלידים אותו כאן, בטלפון הזה – לא צריך ללחוץ על קישור במייל.",
    "code_help": "הקוד בתוקף שעה. הדבקה מהמייל ממלאת את כל התיבות.",
    "resend_wait": "שליחה חוזרת בעוד",
    "resend": "שליחה חוזרת",
    "spam": "לא הגיע? בדקו בספאם",
    "verify_btn": "אימות והמשך להקמה",
    "change_email": "שינוי מייל",
    "privacy": "המייל לא מוצג לחברי הקבוצה",   # mockup wording of "the green privacy note"
    # errors (§1 table)
    "err_wrong": "הקוד שגוי. בדקו את המייל האחרון ונסו שוב.",
    "err_expired": "הקוד פג. שלחו קוד חדש.",
    "err_rate": "יותר מדי ניסיונות. נסו שוב בעוד כמה דקות.",
    "err_offline": "אין חיבור. נסו שוב כשהרשת תחזור.",
    "no_invite": "לא מצאנו הזמנה פעילה למייל הזה",
    "no_invite2": "בקשו ממי שהזמין אותכם לשלוח הזמנה חדשה.",
    "back": "חזרה",
    "d6": "המכשיר הזה כבר מקושר למייל אחר",
    "d6_full": "המכשיר הזה כבר מקושר למייל אחר ({masked}).",
    "d6b": "פתחו את ההזמנה במכשיר אחר, או בקשו לשלוח אותה למייל שמקושר כאן.",
    "other_acct": "המייל הזה כבר משויך לחשבון אחר. כדי לא לאבד את הטיול שכבר במכשיר, פתחו את ההזמנה במכשיר אחר.",
    # step 1 (§1.4)
    "s1_sub": "המייל אומת. נקים את הקבוצה בשלושה צעדים.",
    "progress": ["פרטי הטיול", "יעדים", "אישור וקישור"],
    "s1_name": "שם הטיול",
    "s1_name_help": "מולא מההזמנה, אפשר לשנות",
    "s1_me": "השם שלך בקבוצה",
    "s1_days_re": r"(\d+)\s*ימים\s*·\s*ייווצר יום ריק לכל תאריך",
    "lang_he": "עברית", "lang_en": "English", "soon": "בקרוב",
    "next": "המשך",
    # step 2 (§1.5)
    "popular": "נפוצות",
    "selected_re": r"נבחרו\s*·\s*(\d+)",
    "s2_cur": "מטבעות בטיול",
    "s2_count_re": r"(\d+)\s*מתוך\s*10",
    "home_mark": "בית",
    "add_cur": "הוספה",
    "s2_help": "שקל, דולר ויורו קבועים. מטבע של מדינה נוסף כשבוחרים אותה ויוצא כשמסירים אותה.",
    "full_note": "המטבע {code} לא נכנס – הממיר מלא (10/10). אפשר להסיר מטבע אחר.",
    # step 3 (§1.6)
    "s3_title": "הכול נכון?",
    "s3_sub": "אחרי היצירה אפשר לשנות הכול מהגדרות הטיול.",
    "edit": "עריכה",
    "role_card": "הרשאה למצטרפים חדשים",
    "role_editor": "עורך", "role_viewer": "צופה",
    "me_row": "{name} · מנהל/ת",
    "create": "יצירת הטיול",
    # done (§1.7)
    "done_title": "הטיול נוצר",
    "join_card": "קישור הצטרפות לקבוצה",
    "wa": "שליחה בווטסאפ",
    "copy": "העתקה",
    "copied": "הקישור הועתק",
    "saved_line": "הקישור נשמר גם בהגדרות הטיול, אין צורך לשמור אותו עכשיו.",
    "enter": "כניסה לטיול",
    # home (§1.8) and "עוד" (§1.9)
    "first_steps": "צעדים ראשונים",
    "fs_items": ["הקמת הטיול", "שליחת קישור לקבוצה", "הוספת היעד הראשון ליום 1"],
    "to_route": "הוספת נקודה",  # CHANGE 2026-10-12 F04-QA-04: button #ptFsRoute, was "למסלול"
    "wp_modal": "הוספת נקודת עניין",  # CHANGE 2026-10-12 F04-QA-04: existing add-point modal (#waypointModal)
    "empty_day": "עוד לא נוספו נקודות",
    "no_days": "אין ימים בטיול",
    "more_row": "קישור הצטרפות לקבוצה",
    # /join/ (§1.10) and /invite/ (§1.1)
    "join_title": "ההצטרפות לטיול תיפתח בקרוב",
    "join_text": "הקישור תקין לשמירה – פתחו אותו שוב בעוד כמה ימים.",
    "inv_ok": "ההזמנה שלך אומתה",
    "inv_btn": "פתיחה באפליקציה והקמת הטיול",
    "inv_copy": "ההקמה לוקחת כ-3 דקות.",
    "inv_step1": "האפליקציה נפתחת ושולחת קוד בן 6 ספרות למייל שלך",
    # CHANGE 2026-10-12 F04-QA-03: new note text (F04-INV-02); was '…ולבחור "קיבלתי הזמנה לנהל טיול".'
    "inv_note": 'האפליקציה כבר מותקנת אצלך במסך הבית? אפשר לפתוח אותה משם ולבחור "כניסה עם הזמנה".',
    "inv_note_old": "קיבלתי הזמנה לנהל טיול",
    # CHANGE 2026-10-12 F04-QA-03: criterion 11 (F04-DB-02) — v2.15.2 fallback trip name and the management screen texts
    "tripname_fallback": "מסע של חלומות",
    "mgmt_row": "ניהול",
    "trip_settings": "הגדרות מסע",
    "inv_bad": "הקישור כבר לא בתוקף",
    # F03 landing (WIZARD_FEATURE='off')
    "f03_land_btn": "התחלת הקמה · בקרוב",
}

# =====================================================================================================
# Reference data (spec §4: app/countries.json, app/currencies.json)
# =====================================================================================================
def _load_json(name):
    try:
        return json.loads((APP_DIR / name).read_text(encoding="utf-8"))
    except Exception:
        return []


COUNTRIES = {c["code"]: c for c in _load_json("countries.json") if isinstance(c, dict) and "code" in c}
CURRENCIES = {c["code"]: c for c in _load_json("currencies.json") if isinstance(c, dict) and "code" in c}


def flag(code):
    return "".join(chr(0x1F1E6 + ord(ch) - 65) for ch in code)


def he(code):
    return COUNTRIES[code]["he"] if code in COUNTRIES else code


# =====================================================================================================
# Fake backend
# =====================================================================================================
f02.TABLES.setdefault("trip_join_codes", {"cols": ["trip_id", "code", "version", "rotated_at"], "pk": ("trip_id",),
                                          "uuid": {"trip_id"}})
f02.TABLES.setdefault("trip_currencies", {"cols": ["trip_id", "currency_code", "kind", "sort"],
                                          "pk": ("trip_id", "currency_code"), "uuid": {"trip_id"}})
EMAIL_RE = f03.EMAIL_RE
AUTH_ERR = {
    "email_exists": {"name": "AuthApiError", "message": "A user with this email address has already been registered",
                     "status": 422, "code": "email_exists"},
    "send_rate": {"name": "AuthApiError", "message": "email rate limit exceeded", "status": 429,
                  "code": "over_email_send_rate_limit"},
    "otp": {"name": "AuthApiError", "message": "Token has expired or is invalid", "status": 403, "code": "otp_expired"},
    "verify_rate": {"name": "AuthApiError", "message": "Request rate limit reached", "status": 429,
                    "code": "over_request_rate_limit"},
    "no_signup": {"name": "AuthApiError", "message": "Signups not allowed for otp", "status": 422, "code": "otp_disabled"},
    "offline": {"name": "AuthRetryableFetchError", "message": "Failed to fetch", "status": 0},
}
AUTH_SEND_OPS = ("auth.updateUser", "auth.signInWithOtp", "auth.verifyOtp", "auth.resend")
CT_FIELDS = ["name", "display_name", "start_date", "end_date", "home_currency", "default_lang", "default_role",
             "countries", "currencies", "center"]


def iso(t):
    return t.astimezone(dt.timezone.utc).isoformat()


def ddmmyyyy(d):
    return d.strftime("%d/%m/%Y")


def empty_days(start, n, center=(35.68, 139.69), country="JP"):
    return [{"day": i + 1, "date": ddmmyyyy(start + DAY * i), "region": "", "title": "", "activities": "", "hotel": "",
             "cost": 0, "notes": "", "lat": center[0], "lng": center[1], "zoom": 5, "waypoints": [], "country": country}
            for i in range(n)]


class PayloadError(Exception):
    def __init__(self, code, field=None):
        super().__init__(code)
        self.code, self.field = code, field


def validate_payload(p):
    """spec §2 step 4 (the DB validation the fake create-trip mirrors)."""
    def need(cond, field):
        if not cond:
            raise PayloadError("invalid_payload", field)
    name = p.get("name")
    need(isinstance(name, str) and 1 <= len(name.strip()) <= 80, "name")
    dn = p.get("display_name")
    need(isinstance(dn, str) and 1 <= len(dn.strip()) <= 40, "display_name")
    ds = {}
    for f in ("start_date", "end_date"):
        v = p.get(f)
        need(isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", v), f)
        try:
            ds[f] = dt.date.fromisoformat(v)
        except ValueError:
            need(False, f)
    n = (ds["end_date"] - ds["start_date"]).days + 1
    need(1 <= n <= 120, "end_date")
    need(p.get("home_currency") in BASES, "home_currency")
    need(p.get("default_lang") == "he", "default_lang")
    need(p.get("default_role") in ("editor", "viewer"), "default_role")
    cs = p.get("countries")
    need(isinstance(cs, list) and 1 <= len(cs) <= 15 and len(set(cs)) == len(cs)
         and all(isinstance(c, str) and re.match(r"^[A-Z]{2}$", c) for c in cs), "countries")
    cur = p.get("currencies")
    need(isinstance(cur, list), "currencies")
    seen = set()
    for c in cur:
        need(isinstance(c, dict) and isinstance(c.get("code"), str) and re.match(r"^[A-Z]{3}$", c["code"])
             and c.get("kind") in ("destination", "added") and c["code"] not in seen and c["code"] not in BASES, "currencies")
        seen.add(c["code"])
    if len(cur) + 3 > 10:
        raise PayloadError("too_many_currencies")
    ce = p.get("center")
    need(isinstance(ce, dict) and isinstance(ce.get("lat"), (int, float)) and isinstance(ce.get("lng"), (int, float))
         and -90 <= ce["lat"] <= 90 and -180 <= ce["lng"] <= 180, "center")
    return ds["start_date"], n


class F04Backend(f03.F03Backend):
    def __init__(self):
        super().__init__()
        self.now = FIXED_NOW
        self._t0 = FIXED_NOW - dt.timedelta(days=30)
        self.otp_code = OTP
        self.otps = []                 # {email, type, uid, code, expired}
        self.send_outcome = None       # None | 'rate'  (updateUser / signInWithOtp / resend)
        self.verify_outcome = None     # None | 'rate'
        self.auto_confirmed_email = None
        self.traces = []               # every auth.* call reported by the fake library (incl. ones that never reach us)
        self.otp_calls = []            # {op, device, params}
        self.ct_calls = []             # create-trip calls {via, device, action, body, bearer, status, resp, dropped}
        self.ct_down = False
        self.ct_drop_next = 0          # process the next N create calls, then drop the response (network error)
        self.trips_created = []
        self.ct_rate = {}

    # ---------- setup helpers ----------
    def user_by_email(self, email):
        email = str(email or "").strip().lower()
        for uid, u in self.users.items():
            if str(u.get("email") or "").lower() == email and u.get("email_confirmed_at"):
                return uid
        return None

    def add_account(self, email):
        uid = str(uuid.uuid4())
        self.users[uid] = {"id": uid, "aud": "authenticated", "role": "authenticated", "email": email, "phone": "",
                           "is_anonymous": False, "email_confirmed_at": iso(self.now - 10 * DAY),
                           "app_metadata": {"provider": "email", "providers": ["email"]}, "user_metadata": {},
                           "identities": [], "created_at": iso(self.now - 10 * DAY), "updated_at": iso(self.now - 10 * DAY)}
        return uid

    def expire_otps(self):
        for o in self.otps:
            o["expired"] = True

    def seed_trip(self, name="יפן 2027", n_days=18, start=dt.date(2027, 4, 3), countries=("JP",), days=None,
                  code=None, home="ILS"):
        """A trip exactly as create_trip_from_invite leaves it (spec §2), without a member."""
        tid = self.add_trip(name)
        end = start + DAY * max(n_days - 1, 0)
        self.rows["trips"][(tid,)].update({"start_date": start.isoformat(), "end_date": end.isoformat(),
                                            "home_currency": home})
        for i, c in enumerate(countries):
            self.rows["trip_countries"][(tid, c)] = {"trip_id": tid, "country_code": c, "sort": i}
        for i, c in enumerate([home] + [b for b in BASES if b != home]):
            self.rows["trip_currencies"][(tid, c)] = {"trip_id": tid, "currency_code": c, "kind": "base", "sort": i}
        cap = COUNTRIES.get(countries[0], {}).get("capital", {"lat": 35.68, "lng": 139.69})
        dd = days if days is not None else empty_days(start, n_days, (cap["lat"], cap["lng"]), countries[0])
        self.set_kv(tid, "trip", json.dumps(dd, ensure_ascii=False))
        code = code or self.new_join_code()
        self.rows["trip_join_codes"][(tid,)] = {"trip_id": tid, "code": code, "version": 1, "rotated_at": iso(self.now)}
        return tid, code

    def new_join_code(self):
        used = {r["code"] for r in self.rows["trip_join_codes"].values()}
        while True:
            c = "".join(random.choice(JOIN_ALPHABET) for _ in range(8))
            if c not in used:
                return c

    def auth_sends(self, device=None):
        return [c for c in self.calls if c.get("op") in AUTH_SEND_OPS and (device is None or c["device"] == device)]

    def traced(self, kinds=AUTH_SEND_OPS, device=None):
        return [t for t in self.traces if t["kind"] in kinds and (device is None or t["device"] == device)]

    def ct(self, action=None):
        return [c for c in self.ct_calls if action is None or c["action"] == action]

    # ---------- binding entry ----------
    def sign_in(self):
        res = super().sign_in()
        s = res.get("session")
        if s and self.auto_confirmed_email:
            uid = s["user"]["id"]
            self.users[uid].update({"email": self.auto_confirmed_email, "email_confirmed_at": iso(self.now - DAY),
                                    "is_anonymous": False})
            s["user"] = copy.deepcopy(self.users[uid])
        return res

    def handle(self, device, msg):
        msg = msg or {}
        op = msg.get("op")
        if op == "auth.trace":
            with self.lock:
                self.traces.append({"device": device, "kind": msg.get("kind"), "page": msg.get("page")})
            return {"ok": True}
        if op == "functions.invoke" and msg.get("name") != "create-trip":
            return super().handle(device, msg)
        if op not in ("auth.verifyOtp", "auth.signInWithOtp", "auth.resend", "functions.invoke"):
            return super().handle(device, msg)
        with self.lock:
            url = str(msg.get("url") or "")
            entry = {"device": device, "t": time.time(), "op": op, "page": msg.get("page"), "online": msg.get("online"),
                     "url": url, "msg": copy.deepcopy(msg)}
            self.calls.append(entry)
            if f02.LIVE_REF in url:
                self.violations.append({"device": device, "where": op, "url": url})
            offline = msg.get("online") is False or self.mode == "down" or (op == "functions.invoke" and self.ct_down)
            if offline:
                entry["result"] = {"offline": True}
                return {"offline": True} if op == "functions.invoke" else {"error": dict(AUTH_ERR["offline"])}
            if self.mode == "hang":
                return {"hang": True}
            if url.rstrip("/") != PT_URL or msg.get("key") != PT_KEY:
                return {"error": {"code": "FAKE_WRONG_PROJECT", "message": "fake: wrong project/key"}, "status": 0}
            if op == "auth.verifyOtp":
                res = self.verify_otp(device, msg.get("token"), msg.get("params") or {})
            elif op == "auth.signInWithOtp":
                res = self.sign_in_with_otp(device, msg.get("token"), msg.get("creds") or {})
            elif op == "auth.resend":
                res = self.resend(device, msg.get("token"), msg.get("creds") or {})
            else:
                bearer = msg.get("token") or msg.get("key")
                status, body, drop = self.create_trip_call(device, "invoke", bearer, msg.get("key"), msg.get("body") or {})
                res = {"offline": True} if drop else {"httpStatus": status, "json": body}
            entry["result"] = copy.deepcopy(res)
            return res

    # ---------- email OTP ----------
    def update_user(self, token, attrs, options):
        uid = self.tokens.get(token)
        if "email" not in (attrs or {}) or self.update_outcome != "ok":
            return super().update_user(token, attrs, options)
        self.update_calls.append({"uid": uid, "attrs": attrs, "options": options})
        if not uid:
            return {"error": {"name": "AuthApiError", "message": "invalid JWT", "status": 401}}
        if self.send_outcome == "rate":
            return {"error": dict(AUTH_ERR["send_rate"])}
        email = str(attrs.get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            return {"error": dict(f03.AUTH_ERRORS["invalid"])}
        owner = self.user_by_email(email)
        if owner and owner != uid:
            return {"error": dict(AUTH_ERR["email_exists"])}
        u = self.users[uid]
        u.update({"new_email": email, "email_change_sent_at": iso(self.now)})
        self.otps.append({"email": email, "type": "email_change", "uid": uid, "code": self.otp_code, "expired": False})
        return {"user": copy.deepcopy(u)}

    def sign_in_with_otp(self, device, token, creds):
        self.otp_calls.append({"op": "signInWithOtp", "device": device, "params": copy.deepcopy(creds)})
        if self.send_outcome == "rate":
            return {"error": dict(AUTH_ERR["send_rate"])}
        email = str(creds.get("email") or "").strip().lower()
        opts = creds.get("options") or {}
        owner = self.user_by_email(email)
        if not owner:
            if opts.get("shouldCreateUser") is False:
                return {"error": dict(AUTH_ERR["no_signup"])}
            return {"error": {"name": "AuthApiError", "message": "fake: account creation not modelled", "status": 400}}
        self.otps.append({"email": email, "type": "email", "uid": owner, "code": self.otp_code, "expired": False})
        return {"messageId": "fake-" + uuid.uuid4().hex[:8]}

    def resend(self, device, token, creds):
        self.otp_calls.append({"op": "resend", "device": device, "params": copy.deepcopy(creds)})
        if self.send_outcome == "rate":
            return {"error": dict(AUTH_ERR["send_rate"])}
        email = str(creds.get("email") or "").strip().lower()
        typ = creds.get("type")
        prev = [o for o in self.otps if o["email"] == email and (o["type"] == typ or typ in ("signup",))]
        if not prev:
            return {"error": dict(AUTH_ERR["otp"])}
        self.otps.append({**prev[-1], "expired": False})
        return {}

    def verify_otp(self, device, token, params):
        self.otp_calls.append({"op": "verifyOtp", "device": device, "params": copy.deepcopy(params)})
        if self.verify_outcome == "rate":
            return {"error": dict(AUTH_ERR["verify_rate"])}
        email = str(params.get("email") or "").strip().lower()
        typ = params.get("type")
        code = str(params.get("token") or "")
        kinds = ("email", "magiclink") if typ in ("email", "magiclink") else (typ,)
        cands = [o for o in self.otps if o["email"] == email and o["type"] in kinds]
        if not cands or cands[-1]["expired"] or code != cands[-1]["code"]:
            return {"error": dict(AUTH_ERR["otp"])}   # GoTrue: wrong and expired codes give the same error
        o = cands[-1]
        if typ == "email_change":
            uid = self.tokens.get(token)
            if uid != o["uid"]:
                return {"error": dict(AUTH_ERR["otp"])}
            self.confirm_email(uid, email)
            self.otps = [x for x in self.otps if x is not o]
            return {"user": copy.deepcopy(self.users[uid])}
        uid = o["uid"]
        tok = "fake-at." + uid + "." + uuid.uuid4().hex[:8]
        self.tokens[tok] = uid
        self.otps = [x for x in self.otps if x is not o]
        session = {"access_token": tok, "refresh_token": "fake-rt-" + uuid.uuid4().hex, "token_type": "bearer",
                   "expires_in": 3600, "expires_at": int(time.time()) + 3600, "user": copy.deepcopy(self.users[uid])}
        return {"session": session}

    # ---------- RLS for the F04 tables ----------
    def query(self, token, req, legacy):
        table = str(req.get("table"))
        if table not in ("trip_join_codes", "trip_currencies", "trip_countries"):
            return super().query(token, req, legacy)
        if token and token not in self.tokens:
            return f02._err("PGRST301", "JWT is invalid", 401)
        uid = self.tokens.get(token) if token else None
        if uid is None:
            return f02._err("42501", "permission denied for table %s" % table, 401)
        if table == "trip_join_codes":
            mgr = self.active_trips(uid, ("manager",))
            if req.get("action") != "select":
                return f02._err("42501", "permission denied for table trip_join_codes", 403)
            return self.exec(table, req, uid, lambda r: r["trip_id"] in mgr, None)
        readable = self.active_trips(uid)
        mgr = self.active_trips(uid, ("manager",))
        if table == "trip_countries" and req.get("action") != "select":
            return f02._err("42501", "permission denied for table trip_countries", 403)
        return self.exec(table, req, uid, lambda r: r["trip_id"] in readable, lambda r: r["trip_id"] in mgr)

    # ---------- invite-manager: check returns email (§3.2) ----------
    def _invite_manager(self, bearer, body):
        status, resp = super()._invite_manager(bearer, body)
        if body.get("action") == "check" and resp.get("valid"):
            h = f03.sha256_hex(str(body.get("token")))
            r = next((x for x in self.invites.values() if x["token_hash"] == h), None)
            resp = dict(resp, email=r["email"] if r else None)
        return status, resp

    # ---------- fake create-trip (§3.1 + §2) ----------
    def ct_http(self, device, headers, body):
        auth = headers.get("authorization") or ""
        bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else None
        return self.create_trip_call(device, "fetch", bearer, headers.get("apikey"), body, raw_auth=auth)

    def create_trip_call(self, device, via, bearer, apikey, body, raw_auth=None):
        with self.lock:
            body = body if isinstance(body, dict) else {}
            status, resp = self._create_trip(bearer, body)
            drop = False
            if body.get("action") == "create" and self.ct_drop_next > 0:
                self.ct_drop_next -= 1
                drop = True
            self.ct_calls.append({"via": via, "device": device, "action": body.get("action"), "body": copy.deepcopy(body),
                                  "bearer": bearer, "apikey": apikey, "status": status, "resp": copy.deepcopy(resp),
                                  "dropped": drop})
            return status, resp, drop

    def find_invite_for_email(self, email):
        email = str(email or "").strip().lower()
        rows = sorted([r for r in self.invites.values() if r["email"] == email and not r["used_at"] and not r["revoked_at"]
                       and f03.parse(r["expires_at"]) > self.now], key=lambda r: r["created_at"], reverse=True)
        return rows[0] if rows else None

    def _create_trip(self, bearer, body):
        uid = self.tokens.get(bearer) if bearer else None
        if not uid:
            return 401, {"error": "unauthorized"}
        u = self.users.get(uid) or {}
        if u.get("is_anonymous") or not u.get("email") or not u.get("email_confirmed_at"):
            return 403, {"error": "email_not_verified"}
        action = body.get("action")
        if action not in ("lookup", "create"):
            return 400, {"error": "invalid_request"}
        hist = self.ct_rate.setdefault((uid, action), [])
        if len(hist) >= (30 if action == "lookup" else 10):
            return 429, {"error": "rate_limited"}
        hist.append(self.now)
        email = u["email"].strip().lower()
        if action == "lookup":
            r = self.find_invite_for_email(email)
            if not r:
                return 200, {"found": False}
            return 200, {"found": True, "draft_name": r["draft_name"], "inviter_name": r["inviter_name"],
                         "expires_at": r["expires_at"]}
        payload = {k: copy.deepcopy(body.get(k)) for k in CT_FIELDS}
        try:
            res = self.create_trip_from_invite(uid, email, payload)
        except PayloadError as e:
            if e.code == "invite_invalid":
                return 409, {"error": "invite_invalid"}
            if e.code == "too_many_currencies":
                return 400, {"error": "too_many_currencies"}
            return 400, {"error": "invalid_payload", "field": e.field}
        return 200, dict(res, join_url=JOIN_BASE + "#code=" + res["join_code"])

    def create_trip_from_invite(self, uid, email, p):
        cands = sorted([r for r in self.invites.values() if r["email"] == email and not r["revoked_at"]],
                       key=lambda r: r["created_at"], reverse=True)
        inv = cands[0] if cands else None
        if inv and inv["used_at"] and inv.get("trip_id"):
            tid = inv["trip_id"]
            if tid in self.active_trips(uid, ("manager",)):
                return {"trip_id": tid, "join_code": self.rows["trip_join_codes"][(tid,)]["code"], "created": False}
        if not inv or inv["used_at"] or f03.parse(inv["expires_at"]) <= self.now:
            raise PayloadError("invite_invalid")
        start, n = validate_payload(p)
        tid = str(uuid.uuid4())
        self.rows["trips"][(tid,)] = {"id": tid, "name": p["name"].strip(), "start_date": p["start_date"],
                                      "end_date": p["end_date"], "home_currency": p["home_currency"], "default_lang": "he",
                                      "default_role": p["default_role"], "status": "active", "created_by": uid,
                                      "created_at": self.ts(), "updated_at": self.ts()}
        for i, c in enumerate(p["countries"]):
            self.rows["trip_countries"][(tid, c)] = {"trip_id": tid, "country_code": c, "sort": i}
        home = p["home_currency"]
        for i, c in enumerate([home] + [b for b in BASES if b != home]):
            self.rows["trip_currencies"][(tid, c)] = {"trip_id": tid, "currency_code": c, "kind": "base", "sort": i}
        for i, c in enumerate(p["currencies"]):
            self.rows["trip_currencies"][(tid, c["code"])] = {"trip_id": tid, "currency_code": c["code"],
                                                              "kind": c["kind"], "sort": 3 + i}
        self.add_member(tid, uid, "manager", "active", p["display_name"].strip())
        code = self.new_join_code()
        self.rows["trip_join_codes"][(tid,)] = {"trip_id": tid, "code": code, "version": 1, "rotated_at": iso(self.now)}
        days = empty_days(start, n, (p["center"]["lat"], p["center"]["lng"]), p["countries"][0])
        self.set_kv(tid, "trip", json.dumps(days, ensure_ascii=False), updated_by=uid)
        # CHANGE 2026-10-12 F04-QA-03: spec §2 step 5 (F04-DB-02) — also trip_kv `tripname` = trimmed name, plain text
        self.set_kv(tid, "tripname", p["name"].strip(), updated_by=uid)
        inv["used_at"] = iso(self.now)
        inv["trip_id"] = tid
        self.trips_created.append(tid)
        return {"trip_id": tid, "join_code": code, "created": True}


# =====================================================================================================
# Browser environment
# =====================================================================================================
OPEN_JS = """(()=>{if(window.__qaOpened)return;window.__qaOpened=[];const o=window.open;
 window.open=function(u){try{window.__qaOpened.push(String(u))}catch(e){}return null};})();"""


class Env(f03.Env):
    def __init__(self, browser, server):
        f02.Env.__init__(self, browser, server)
        self.backend = F04Backend()

    def new_device(self, name="A", service_workers="block", clock="install", **_):
        conf = {"legacy_fake": False}
        ctx = self.browser.new_context(viewport=VIEWPORT, locale="he-IL", timezone_id="Asia/Jerusalem",
                                       service_workers=service_workers,
                                       permissions=["geolocation", "clipboard-read", "clipboard-write"],
                                       geolocation={"latitude": 21.0285, "longitude": 105.8542, "accuracy": 20})
        if clock == "install":
            ctx.clock.install(time=FIXED_NOW)
        elif clock == "fixed":
            ctx.clock.set_fixed_time(FIXED_NOW)
        ctx.expose_binding("__fakeBackend", lambda source, msg, _n=name: self.backend.handle(_n, msg))
        ctx.add_init_script(f02.WATCH_JS)
        ctx.add_init_script(OPEN_JS)
        ctx.add_init_script("try{Object.defineProperty(window,'launchQueue',{configurable:true,value:{setConsumer:function(c){window.__qaLaunchConsumer=c}}})}catch(e){}")
        page = ctx.new_page()
        d = f03.F03Device(self, name, ctx, page, conf)
        ctx.route("**/*", lambda route, request, _d=d: self._route4(_d, route, request))
        self.devices.append(d)
        return d

    def _route4(self, dev, route, request):
        url = request.url
        p = urlparse(url)
        rec = {"device": dev.name, "url": url, "method": request.method, "type": request.resource_type}
        self.net.append(rec)
        be = self.backend
        try:
            if p.hostname in ("127.0.0.1", "localhost"):
                rec["action"] = "same-origin"
                return route.continue_()
            if p.hostname == "cdn.jsdelivr.net" and "@supabase/supabase-js" in p.path:
                rec["action"] = "fake-lib"
                return route.fulfill(status=200, content_type="application/javascript; charset=utf-8", body=FAKE_JS,
                                     headers={"Access-Control-Allow-Origin": "*"})
            base = url.split("#")[0].split("?")[0].rstrip("/")
            if base in (IM_URL, CT_URL):
                origin = request.headers.get("origin") or "*"
                cors = {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS",
                        "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type", "Vary": "Origin"}
                down = dev.is_offline or be.mode == "down" or (base == IM_URL and be.fn_down) or (base == CT_URL and be.ct_down)
                if down:
                    rec["action"] = "fn-offline"
                    return route.abort("internetdisconnected")
                if request.method == "OPTIONS":
                    rec["action"] = "fn-preflight"
                    return route.fulfill(status=204, headers=cors, body="")
                try:
                    body = json.loads(request.post_data or "{}")
                except ValueError:
                    body = {"__unparsable": request.post_data}
                rec["body"] = body
                hdrs = {k.lower(): v for k, v in request.headers.items()}
                if base == IM_URL:
                    rec["action"] = "fn"
                    status, resp = be.fn_http(dev.name, hdrs, body)
                    return route.fulfill(status=status, headers=cors, content_type="application/json", body=json.dumps(resp))
                rec["action"] = "ct"
                status, resp, drop = be.ct_http(dev.name, hdrs, body)
                if drop:
                    rec["action"] = "ct-dropped"
                    return route.abort("failed")
                return route.fulfill(status=status, headers=cors, content_type="application/json", body=json.dumps(resp))
            rec["action"] = "aborted"
            return route.abort()
        except PWError:
            pass


@pytest.fixture(scope="session")
def server():
    s = f02.Server()
    yield s
    s.stop()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=os.environ.get("QA_HEADFUL") != "1")
        yield b
        b.close()


@pytest.fixture
def env(browser, server):
    server.overrides.clear()
    e = Env(browser, server)
    yield e
    e.close()
    server.overrides.clear()


# =====================================================================================================
# Source helpers (alpha.3 reference + flag flips + static pages)
# =====================================================================================================
def app_html():
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


def alpha3_html():
    r = subprocess.run(["git", "-C", str(REPO_DIR), "show", "%s:app/index.html" % ALPHA3_REF], capture_output=True)
    assert r.returncode == 0, "harness: cannot read alpha.3 (%s:app/index.html): %s" % (ALPHA3_REF, r.stderr.decode()[:200])
    html = r.stdout.decode("utf-8")
    assert re.search(r"const APP_VERSION='3\.0\.0-alpha\.3", html), "harness: %s is not alpha.3" % ALPHA3_REF
    return html


WIZ_RE = re.compile(r"""(const\s+WIZARD_FEATURE\s*=\s*)(['"])on\2""")


def serve_wizard_off(env):
    src = app_html()
    assert WIZ_RE.search(src), "const WIZARD_FEATURE='on' not found in app/index.html (spec §1: top-level flag)"
    env.server.overrides[APP_PATH] = WIZ_RE.sub(r"\1'off'", src, count=1).encode("utf-8")


def serve_pages(env):
    for d in ("invite", "join"):
        f = REPO_DIR / d / "index.html"
        if f.is_file():
            b = f.read_bytes()
            env.server.overrides["/%s/" % d] = b
            env.server.overrides["/%s/index.html" % d] = b


# =====================================================================================================
# UI helpers
# =====================================================================================================
find, click_text, visible, wait_text, gone = f03.find, f03.click_text, f03.visible, f03.wait_text, f03.gone
body_text, is_disabled, chrome_visible = f03.body_text, f03.is_disabled, f03.chrome_visible


def norm(s):
    s = re.sub(r"[‎‏‪-‮⁦-⁩]", "", str(s or ""))
    s = re.sub(r"[–—‒−]", "-", s)
    s = re.sub(r"[״“”„]", '"', s)
    s = s.replace("’", "'").replace("׳", "'")
    return re.sub(r"\s+", " ", s).strip()


def btext(page):
    return norm(body_text(page))


def has(page, s):
    return norm(s) in btext(page)


def wait_has(page, s, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        if has(page, s):
            return True
        page.wait_for_timeout(150)
    return False


SCREENS = [  # order matters: the first marker found wins
    ("done", TXT["done_title"]), ("step3", TXT["s3_title"]), ("step2", TXT["s2_cur"]), ("step1", TXT["s1_sub"]),
    ("d6", TXT["d6"]), ("other_acct", "המייל הזה כבר משויך לחשבון אחר"), ("no_invite", TXT["no_invite"]),
    ("code", TXT["code_title"]), ("email", TXT["send_code"]), ("f03_landing", TXT["f03_land_btn"]),
    ("land_bad", TXT["inv_bad"]), ("nc", f02.NC_TITLE),
]


def screen(page):
    try:
        if page.evaluate("()=>{const h=document.getElementById('homeV2');return !!h&&h.classList.contains('active')&&getComputedStyle(h).display!=='none'}"):
            return "home"
    except PWError:
        return None
    t = btext(page)
    for k, marker in SCREENS:
        if norm(marker) in t:
            return k
    return None


def wait_screen(page, want=None, timeout=15.0):
    end = time.time() + timeout
    s = None
    while time.time() < end:
        s = screen(page)
        if s and (want is None or s == want or (isinstance(want, (list, tuple)) and s in want)):
            page.wait_for_timeout(250)
            return s
        page.wait_for_timeout(200)
    return s


def otp_boxes(page):
    return page.locator(SEL["otp"]).filter(visible=True)


def otp_values(page):
    return page.evaluate("(s)=>[...document.querySelectorAll(s)].filter(e=>e.offsetParent!==null).map(e=>e.value)", SEL["otp"])


def otp_focus(page):
    return page.evaluate("(s)=>[...document.querySelectorAll(s)].filter(e=>e.offsetParent!==null).indexOf(document.activeElement)", SEL["otp"])


def type_code(page, code):
    """Each digit into its own box (independent of auto-advance); then, if still on the code screen, tap verify."""
    boxes = otp_boxes(page)
    assert boxes.count() == 6, "expected 6 visible code inputs (%s), found %d" % (SEL["otp"], boxes.count())
    for i, d in enumerate(code):
        boxes.nth(i).click()
        page.keyboard.press(d)
        page.wait_for_timeout(40)
    page.wait_for_timeout(700)
    if screen(page) == "code" and visible(page, TXT["verify_btn"]) and not is_disabled(page, TXT["verify_btn"]):
        click_text(page, TXT["verify_btn"])


def field(page, label):
    """The input labelled `label` (label[for], aria-label, or a wrapping/preceding label)."""
    loc = page.get_by_label(label, exact=False).filter(visible=True)
    try:
        if loc.count():
            return loc.first
    except PWError:
        pass
    key = "f" + uuid.uuid4().hex[:6]
    ok = page.evaluate("""([t,key])=>{const N=s=>String(s||'').replace(/\\s+/g,' ').trim();
      const labs=[...document.querySelectorAll('label,span,div,b')].filter(e=>e.offsetParent!==null&&N(e.textContent)===t);
      for(const l of labs){let n=l;for(let i=0;i<3&&n;i++){const inp=n.querySelector&&n.querySelector('input,select,textarea');
        if(inp&&inp.offsetParent!==null){inp.setAttribute('data-qa-f',key);return true}n=n.parentElement}}return false}""", [label, key])
    assert ok, "input labelled %r not found" % label
    return page.locator('[data-qa-f="%s"]' % key)


def set_value(loc, value):
    loc.fill(value)
    loc.dispatch_event("change")


def dates(page):
    loc = page.locator(SEL["date_inputs"]).filter(visible=True)
    assert loc.count() >= 2, "expected two date inputs (%s) on step 1, found %d" % (SEL["date_inputs"], loc.count())
    return loc.nth(0), loc.nth(1)


def select_home(page, code):
    ok = page.evaluate("""([s,c])=>{const sel=[...document.querySelectorAll(s)].filter(e=>e.offsetParent!==null)[0];if(!sel)return 'no select';
      const i=[...sel.options].findIndex(o=>o.value===c||o.textContent.includes(c));if(i<0)return 'no option '+c;
      sel.selectedIndex=i;sel.dispatchEvent(new Event('input',{bubbles:true}));sel.dispatchEvent(new Event('change',{bubbles:true}));return true}""",
                       [SEL["currency_select"], code])
    assert ok is True, "home currency select: %s" % ok


def home_value(page):
    return page.evaluate("""(s)=>{const sel=[...document.querySelectorAll(s)].filter(e=>e.offsetParent!==null)[0];
      return sel?(sel.value+'|'+(sel.options[sel.selectedIndex]||{}).textContent):null}""", SEL["currency_select"])


def day_count(page):
    t = btext(page)
    m = re.search(TXT["s1_days_re"], t)
    if m:
        return int(m.group(1))
    # CHANGE 2026-10-12 F04-QA: Hebrew singular "יום אחד · …" accepted for N=1 (same rule as F03-QA-FIX-01 "חבר אחד").
    return 1 if re.search(r"(יום אחד|1 יום)\s*·\s*ייווצר יום ריק לכל תאריך", t) else None


def press_next(page):
    click_text(page, TXT["next"])
    page.wait_for_timeout(500)


def fill_step1(page, name=None, me=None, start=None, end=None, home=None):
    if name is not None:
        set_value(field(page, TXT["s1_name"]), name)
    if me is not None:
        set_value(field(page, TXT["s1_me"]), me)
    if start is not None or end is not None:
        a, b = dates(page)
        if start is not None:
            set_value(a, start)
        if end is not None:
            set_value(b, end)
    if home is not None:
        select_home(page, home)
    page.wait_for_timeout(250)


# ---------- step 2 ----------
SEARCH_RESULTS_JS = r"""([q,inpSel])=>{const N=s=>String(s||'').replace(/[‎‏‪-‮⁦-⁩]/g,'').replace(/\s+/g,' ').trim();
  const vis=e=>{const r=e.getBoundingClientRect();if(r.width<1||r.height<1)return false;for(let a=e;a;a=a.parentElement){const s=getComputedStyle(a);if(s.display==='none'||s.visibility==='hidden'||+s.opacity===0)return false}return true};
  const inp=[...document.querySelectorAll(inpSel)].filter(vis)[0];
  const lab=[...document.querySelectorAll('body *')].filter(e=>vis(e)&&N(e.textContent)==='נפוצות')[0];
  let pop=lab?lab.parentElement:null;if(pop&&inp&&pop.contains(inp))pop=lab.nextElementSibling;
  const C='button,a[href],[role=option],[role=button],li,label,[onclick],[data-code],[tabindex]';
  let els=[...document.querySelectorAll(C)].filter(e=>vis(e)&&N(e.innerText).includes(q)&&!(pop&&pop.contains(e))&&!e.querySelector('[aria-label^="הסרת"]')&&!(e.getAttribute('aria-label')||'').startsWith('הסרת'));
  els=els.filter(e=>!els.some(o=>o!==e&&e.contains(o)));
  const key='r'+Math.random().toString(36).slice(2,7);
  return els.map((e,i)=>{e.setAttribute('data-qa-res',key+i);const r=e.getBoundingClientRect();return{sel:'[data-qa-res="'+key+i+'"]',text:N(e.innerText),h:r.height}})}"""


def search_input(page):
    loc = page.locator(SEL["country_search"]).filter(visible=True)
    assert loc.count(), "country search input not found (%s)" % SEL["country_search"]
    return loc.first


def search(page, q):
    inp = search_input(page)
    inp.fill("")
    inp.type(q, delay=20)
    page.wait_for_timeout(500)


def results(page, contains):
    return page.evaluate(SEARCH_RESULTS_JS, [contains, SEL["country_search"]])


def selected_count(page):
    m = re.search(TXT["selected_re"], btext(page))
    return int(m.group(1)) if m else 0


def pick(page, query, code):
    """Search `query`, click the result for country `code`, clear the search."""
    name = he(code)
    before = selected_count(page)
    search(page, query)
    res = [r for r in results(page, name)]
    assert res, "no search result showing %r for query %r" % (name, query)
    res.sort(key=lambda r: len(r["text"]))
    page.locator(res[0]["sel"]).first.click()
    page.wait_for_timeout(400)
    try:
        search_input(page).fill("")
    except (AssertionError, PWError):
        pass
    page.wait_for_timeout(300)
    assert selected_count(page) == before + 1, "selecting %s did not raise 'נבחרו · N' (%d → %d)" % (name, before, selected_count(page))


def remove_country(page, code):
    name = he(code)
    c = find(page, SEL["remove_aria"].format(he=name))
    if c:
        page.mouse.click(c[0]["x"], c[0]["y"])
    else:
        ok = page.evaluate("""(n)=>{const N=s=>String(s||'').replace(/\\s+/g,' ').trim();
          const cards=[...document.querySelectorAll('body *')].filter(e=>e.offsetParent!==null&&N(e.innerText).includes(n)&&[...e.querySelectorAll('button')].some(b=>N(b.textContent)==='×'));
          const card=cards.filter(e=>!cards.some(o=>o!==e&&e.contains(o)))[0];if(!card)return false;
          [...card.querySelectorAll('button')].find(b=>N(b.textContent)==='×').click();return true}""", name)
        assert ok, "no × (remove) button for %s" % name
    page.wait_for_timeout(400)


def popular_container_text(page):
    return page.evaluate(r"""(inpSel)=>{const N=s=>String(s||'').replace(/\s+/g,' ').trim();
      const lab=[...document.querySelectorAll('body *')].filter(e=>e.offsetParent!==null&&N(e.textContent)==='נפוצות')[0];if(!lab)return null;
      let pop=lab.parentElement;const inp=document.querySelector(inpSel);if(inp&&pop.contains(inp))pop=lab.nextElementSibling;
      return pop?pop.textContent:null}""", SEL["country_search"])


def currency_segment(page):
    t = btext(page)
    i = t.find(norm(TXT["s2_cur"]))
    if i < 0:
        return ""
    seg = t[i:]
    j = seg.find(norm(TXT["s2_help"])[:20])
    seg = seg[: j if j > 0 else 600]
    return re.sub(r"המטבע [A-Z]{3} לא נכנס.*?(אחר\.?|$)", " ", seg)


def currency_codes(page):
    """Codes in chip order. A chip shows '<symbol> <CODE>' and some symbols ARE the code (CHF, AED) → adjacent duplicates
    collapse; a real duplicate chip is caught by the 'K מתוך 10' count checks."""
    out = []
    for c in re.findall(r"(?<![A-Z])[A-Z]{3}(?![A-Z])", currency_segment(page)):
        if not out or out[-1] != c:
            out.append(c)
    return out


def currency_count(page):
    m = re.search(TXT["s2_count_re"], currency_segment(page))
    return int(m.group(1)) if m else None


def home_marked(page, code):
    seg = currency_segment(page)
    return bool(re.search(r"%s\W{0,4}%s|%s\W{0,4}%s" % (code, TXT["home_mark"], TXT["home_mark"], code), seg))


# ---------- flows ----------
def token_link(env, name="A", email=INVITE_EMAIL, draft=DRAFT, iid_token=None, path_variant="?invite=1#invite={t}"):
    be = env.backend
    iid, token = iid_token or be.add_invite(email, draft, sent_days_ago=0, expires_in_days=7)
    dev = env.new_device(name)
    dev.goto(APP_PATH + path_variant.format(t=token), ready=False)
    return dev, iid, token


def gate_device(env, name="A"):
    dev = env.new_device(name)
    st = dev.goto(APP_PATH)
    assert st == "nc", "fresh device did not reach the not-connected card (state=%s)" % st
    return dev


def gate_to_email(dev):
    page = dev.page
    assert wait_text(page, TXT["gate_btn"]), "gate button %r not on the not-connected card" % TXT["gate_btn"]
    click_text(page, TXT["gate_btn"])
    assert wait_screen(page, "email") == "email", "gate button did not open the email state (screen=%s)" % screen(page)


def send_email(dev, email):
    page = dev.page
    loc = page.locator(SEL["email_input"]).filter(visible=True)
    assert loc.count(), "email input (%s) not visible" % SEL["email_input"]
    loc.first.fill(email)
    click_text(page, TXT["send_code"])
    page.wait_for_timeout(600)


def to_step1(env, name="A", via="token", email=INVITE_EMAIL, draft=DRAFT):
    """Fresh anonymous device → (token link | gate button) → code → step 1. Returns (dev, iid, token)."""
    be = env.backend
    iid, token = be.add_invite(email, draft, sent_days_ago=0, expires_in_days=7)
    if via == "token":
        dev, _, _ = token_link(env, name, iid_token=(iid, token))
    else:
        dev = gate_device(env, name)
        gate_to_email(dev)
        send_email(dev, email)
    page = dev.page
    st = wait_screen(page, ["code", "step1"])
    assert st in ("code", "step1"), "code screen not reached (screen=%s, text=%r)" % (st, btext(page)[:200])
    if st == "code":
        type_code(page, be.otp_code)
    st = wait_screen(page, "step1")
    assert st == "step1", "step 1 not reached after the code (screen=%s, text=%r)" % (st, btext(page)[:200])
    return dev, iid, token


def to_step2(env, name="A", start="2027-04-03", end="2027-04-20", me="דנה", home=None, **kw):
    dev, iid, token = to_step1(env, name, **kw)
    fill_step1(dev.page, me=me, start=start, end=end, home=home)
    press_next(dev.page)
    assert wait_screen(dev.page, "step2") == "step2", "step 2 not reached (screen=%s)" % screen(dev.page)
    return dev, iid, token


def to_step3(env, name="A", codes=(("יפ", "JP"), ("דרום קור", "KR")), **kw):
    dev, iid, token = to_step2(env, name, **kw)
    for q, c in codes:
        pick(dev.page, q, c)
    press_next(dev.page)
    assert wait_screen(dev.page, "step3") == "step3", "step 3 not reached (screen=%s)" % screen(dev.page)
    return dev, iid, token


def create_and_done(dev):
    click_text(dev.page, TXT["create"])
    st = wait_screen(dev.page, "done", 12)
    assert st == "done", "done screen not reached (screen=%s, text=%r)" % (st, btext(dev.page)[:300])


def enter_trip(dev):
    page = dev.page
    click_text(page, TXT["enter"])
    page.wait_for_timeout(800)
    page.wait_for_load_state("domcontentloaded")
    assert f02.wait_ready(page) == "app", "'%s' did not open the trip" % TXT["enter"]
    f02.ensure_user(page)


def boot_trip(env, role="manager", n_days=18, name="A", days=None, display="דנה", pre_ls=None):
    be = env.backend
    tid, code = be.seed_trip("יפן 2027", n_days=n_days, days=days)
    be.auto_link = {"trip_id": tid, "role": role, "status": "active", "display_name": display}
    dev = env.new_device(name)
    if pre_ls:
        dev.seed_ls({k.format(tid=tid): v for k, v in pre_ls.items()})
    st = dev.goto(APP_PATH)
    assert st == "app", "app did not start for a %s of a new trip (state=%s)" % (role, st)
    f02.ensure_user(dev.page)
    return tid, code, dev


def page_errors(dev):
    noise = ("Failed to load resource", "net::ERR_", "favicon")
    return dev.errors + [c for c in dev.console if c.startswith("error:") and not any(n in c for n in noise)]


WA_GUARD_JS = """()=>{window.__qaOpened=window.__qaOpened||[];if(window.__qaWaGuard)return;window.__qaWaGuard=1;
  window.addEventListener('click',e=>{const a=e.target&&e.target.closest&&e.target.closest('a[href]');
    if(a&&/wa\\.me|whatsapp/.test(a.href)){window.__qaOpened.push(a.href);e.preventDefault()}},true)}"""


def wa_url(dev):
    """Tap the visible 'שליחה בווטסאפ' control (exact text) like a user and return its WhatsApp target: the <a href>, or
    what window.open / a navigation received. Navigation to wa.me is suppressed so the page survives the tap."""
    page = dev.page
    c = [x for x in find(page, TXT["wa"], exact=True) if x["top"]] or find(page, TXT["wa"], exact=True)
    assert c, "%r not found" % TXT["wa"]
    href = page.evaluate("(i)=>{const e=(window.__qaLast||[])[i];const a=e&&e.closest('a');return a?a.href:null}", c[0]["i"])
    n = len(env_net(dev))
    page.evaluate(WA_GUARD_JS)
    page.evaluate("()=>{window.__qaOpened=[]}")
    page.mouse.click(c[0]["x"], c[0]["y"])
    page.wait_for_timeout(600)
    for u in page.evaluate("()=>window.__qaOpened||[]"):
        if "wa.me" in u:
            return u
    for r in env_net(dev)[n:]:
        if "wa.me" in r["url"]:
            return r["url"]
    return href


def env_net(dev):
    return dev.env.net


def wa_text(url):
    q = parse_qs(urlparse(url).query)
    return (q.get("text") or [""])[0]


def layout_problems(page, scope=None, label=""):
    """390px: page-level horizontal scroll, RTL, touch ≥44px (hit-tested). Elements inside a horizontally scrolling
    container (the 'נפוצות' chips row, spec §1.5) are not flagged as 'outside the viewport'."""
    r = page.evaluate("""(scope)=>{const root=scope?document.querySelector(scope):document.body;
      const out={sw:document.scrollingElement.scrollWidth,iw:innerWidth,dir:document.documentElement.getAttribute('dir'),
        rootDir:root?getComputedStyle(root).direction:null,small:[],wide:[]};if(!root)return out;
      const inScroller=e=>{for(let a=e.parentElement;a&&a!==document.body;a=a.parentElement){const s=getComputedStyle(a);if(/(auto|scroll)/.test(s.overflowX)&&a.scrollWidth>a.clientWidth+1)return true}return false};
      const C='button,a[href],[role=button],[role=tab],input:not([type=hidden]),select,textarea,summary,[onclick],[data-go]';
      for(const e of root.querySelectorAll(C)){const r=e.getBoundingClientRect();if(r.width<1||r.height<1)continue;
        const s=getComputedStyle(e);if(s.visibility==='hidden'||+s.opacity===0)continue;
        if(r.top>=innerHeight||r.bottom<=0){e.scrollIntoView({block:'center',inline:'nearest'})}
        const q=e.getBoundingClientRect(),h=document.elementFromPoint(Math.min(Math.max(q.left+q.width/2,0),innerWidth-1),Math.min(Math.max(q.top+q.height/2,0),innerHeight-1));
        if(!h||!(h===e||e.contains(h)||h.contains(e)))continue;
        const lab=(e.innerText||e.value||e.getAttribute('aria-label')||e.tagName).trim().slice(0,30);
        if(q.width<44-0.5||q.height<44-0.5)out.small.push(lab+' '+Math.round(q.width)+'x'+Math.round(q.height));
        if((q.left<-0.5||q.right>innerWidth+0.5)&&!inScroller(e))out.wide.push(lab)}
      return out}""", scope)
    p = []
    if r["sw"] > r["iw"] + 1:
        p.append("%s: horizontal scroll (%d > %d)" % (label, r["sw"], r["iw"]))
    if r["dir"] != "rtl" or (r["rootDir"] and r["rootDir"] != "rtl"):
        p.append("%s: not RTL (html dir=%r, container direction=%r)" % (label, r["dir"], r["rootDir"]))
    p += ["%s: touch target < 44px: %s" % (label, s) for s in r["small"]]
    p += ["%s: element outside the 390px viewport: %s" % (label, s) for s in r["wide"]]
    return p


# =====================================================================================================
# 1–4 · Auth and invite (client side; function side: function_test.ts; DB side: sql/qa_f04_cases.md)
# =====================================================================================================
def test_c01_token_link_code_screen_email_locked(env):
    """C1 + §1.3/§4: token link → check → code screen with the invite email prefilled and read-only; the code was sent
    with updateUser({email}) (email_change) on the device's own anonymous identity; texts of the code state; no 'שינוי
    מייל' (email came from the token); token removed from the address bar."""
    be = env.backend
    dev, iid, token = token_link(env)
    page = dev.page
    st = wait_screen(page, "code")
    assert st == "code", "code screen not shown for a valid token link (screen=%s, text=%r)" % (st, btext(page)[:200])
    P = []
    if not be.fn("check") or be.fn("check")[0]["body"].get("token") != token:
        P.append("invite-manager check not called with the token")
    ups = [c for c in be.update_calls if (c["attrs"] or {}).get("email")]
    if len(ups) != 1 or ups[0]["attrs"].get("email", "").lower() != INVITE_EMAIL:
        P.append("code not sent with exactly one updateUser({email:%s}): %r" % (INVITE_EMAIL, [c["attrs"] for c in ups]))
    elif ups[0]["uid"] != dev.uid():
        P.append("updateUser was not made by the device's own identity")
    em = page.locator(SEL["email_input"]).filter(visible=True)
    if not em.count():
        if not has(page, INVITE_EMAIL):
            P.append("invite email not shown on the code screen")
    else:
        if em.first.input_value().strip().lower() != INVITE_EMAIL:
            P.append("email field value %r != invite email" % em.first.input_value())
        if not em.first.evaluate("e=>e.readOnly||e.disabled"):
            P.append("email field is editable (spec: prefilled and locked)")
    for k in ("code_expl", "code_help", "spam", "verify_btn", "privacy"):
        if not has(page, TXT[k]):
            P.append("code screen lacks %r" % TXT[k])
    if not re.search(norm(TXT["resend_wait"]) + r"\s*0:4[45]", btext(page)):
        P.append("resend countdown 'שליחה חוזרת בעוד 0:45' missing")
    if visible(page, TXT["change_email"]):
        P.append("'%s' shown although the email came from the token" % TXT["change_email"])
    if token in page.url or "#invite" in page.url:
        P.append("token left in the address bar: %s" % page.url)
    boxes = otp_boxes(page)
    if boxes.count() != 6:
        P.append("%d code inputs (expected 6)" % boxes.count())
    else:
        attrs = page.evaluate("(s)=>[...document.querySelectorAll(s)].filter(e=>e.offsetParent!==null).map(e=>[e.getAttribute('inputmode'),e.getAttribute('autocomplete'),getComputedStyle(e.parentElement).direction,e.getBoundingClientRect().left])", SEL["otp"])
        if attrs[0][1] != "one-time-code":
            P.append("first code input lacks autocomplete=one-time-code")
        if [a[3] for a in attrs] != sorted(a[3] for a in attrs):
            P.append("code inputs are not in LTR order (box 1 leftmost)")
    if chrome_visible(page):
        P.append("trip chrome on the code screen: %r" % chrome_visible(page))
    assert not P, "\n".join(P)


TOKEN_VARIANTS = ["plain", "query", "encoded", "hash_change_while_open", "launch_queue"]


@pytest.mark.parametrize("variant", TOKEN_VARIANTS)
def test_c01_token_entry_variants_reach_code_screen(env, variant):
    """§4 'Token entry' (replaces the F03 landing cases deselected in the 'on' regression run): #invite=<t>,
    ?invite=1#invite=<t>, percent-encoded #invite%3D<t>, a hash-only change while the app is open, and a launchQueue
    launch of the installed app all reach the code screen with the invite email; the address bar is cleaned."""
    be = env.backend
    iid, token = be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    if variant in ("plain", "query", "encoded"):
        path = {"plain": "#invite={t}", "query": "?invite=1#invite={t}", "encoded": "#invite%3D{t}"}[variant]
        dev, _, _ = token_link(env, iid_token=(iid, token), path_variant=path)
    else:
        tid = be.add_trip_full("טיול קיים", "2026-09-15", "2026-10-06")
        be.set_kv(tid, "tripname", "טיול קיים")
        be.auto_link = {"trip_id": tid, "role": "editor", "status": "active", "display_name": "QA"}
        dev = env.new_device("A")
        assert dev.goto(APP_PATH) == "app"
        f02.ensure_user(dev.page)
        try:
            if variant == "hash_change_while_open":
                dev.page.evaluate("(t)=>{location.hash='#invite='+t}", token)
            else:
                url = dev.page.url.split("#")[0].split("?")[0] + "?invite=1#invite=" + token
                dev.page.evaluate("(u)=>{window.__qaLaunchConsumer&&window.__qaLaunchConsumer({targetURL:u})}", url)
        except PWError:
            pass  # the page reloads itself
        dev.page.wait_for_timeout(1500)
        dev.page.wait_for_load_state("load")
    page = dev.page
    st = wait_screen(page, ["code", "other_acct"])
    assert st == "code", "%s: code screen not reached (screen=%s, text=%r)" % (variant, st, btext(page)[:200])
    assert has(page, INVITE_EMAIL) or page.locator(SEL["email_input"]).filter(visible=True).first.input_value().lower() == INVITE_EMAIL, \
        "%s: invite email not on the code screen" % variant
    assert "invite" not in page.url, "%s: address bar not cleaned: %r" % (variant, page.url)


def test_c01_token_and_code_never_stored_or_logged(env):
    """§4 + F03 C12 carried over to the 'on' flow: after the token link, the code and the create, the token and the
    6-digit code are not in localStorage / sessionStorage / console / any request URL / the DOM; the email is not in
    localStorage beyond supabase-js's own session."""
    be = env.backend
    dev, iid, token = to_step1(env)
    page = dev.page
    P = []
    ls = dev.ls()
    ss = page.evaluate("()=>{const o={};for(let i=0;i<sessionStorage.length;i++){const k=sessionStorage.key(i);o[k]=sessionStorage.getItem(k)}return JSON.stringify(o)}")
    for label, secret in (("token", token), ("code", be.otp_code)):
        if any(secret in (k + str(v)) for k, v in ls.items()):
            P.append("%s in localStorage" % label)
        if secret in ss:
            P.append("%s in sessionStorage" % label)
        if [m for m in dev.console + dev.errors if secret in m]:
            P.append("%s written to the console" % label)
        if [r["url"] for r in env.net if secret in r["url"]]:
            P.append("%s in a request URL" % label)
        if secret in page.content():
            P.append("%s in the DOM" % label)
    leak = [k for k, v in ls.items() if INVITE_EMAIL in str(v) and k != dev.auth_raw_key()]
    if leak:
        P.append("invite email stored in localStorage keys %r" % leak)
    assert not P, "\n".join(P)


def test_c01_gate_button_email_entry(env):
    """C1 + §1.2/§1.3: the not-connected card gets a second card ('קיבלת הזמנה לנהל טיול?', text, 'כניסה עם הזמנה'; no
    'חדש · F04' badge) → email state (label, LTR input, 'שליחת קוד') → code state with 'שינוי מייל' back to the email
    state."""
    be = env.backend
    be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = gate_device(env)
    page = dev.page
    P = []
    for k in ("gate_title", "gate_text", "gate_btn"):
        if not has(page, TXT[k]):
            P.append("gate lacks %r" % TXT[k])
    if has(page, TXT["gate_badge"]):
        P.append("mockup annotation %r shown in production" % TXT["gate_badge"])
    if not has(page, f02.NC_BODY):
        P.append("original not-connected card content changed (no %r)" % f02.NC_BODY)
    assert not P, "\n".join(P)
    gate_to_email(dev)
    if not has(page, TXT["email_label"]):
        P.append("email state lacks %r" % TXT["email_label"])
    em = page.locator(SEL["email_input"]).filter(visible=True)
    if not em.count() or em.first.evaluate("e=>getComputedStyle(e).direction") != "ltr":
        P.append("email input missing or not LTR")
    if be.auth_sends():
        P.append("an auth call was made before 'שליחת קוד'")
    send_email(dev, "  Dana@Example.com ")
    if wait_screen(page, "code") != "code":
        P.append("'שליחת קוד' did not reach the code state (screen=%s)" % screen(page))
    ups = [c for c in be.update_calls if (c["attrs"] or {}).get("email")]
    if not ups or ups[-1]["attrs"]["email"].strip().lower() != INVITE_EMAIL:
        P.append("updateUser not called with the typed email: %r" % [c["attrs"] for c in ups])
    if not visible(page, TXT["change_email"]):
        P.append("'%s' missing in email-entry mode" % TXT["change_email"])
    else:
        click_text(page, TXT["change_email"])
        if wait_screen(page, "email") != "email":
            P.append("'%s' did not return to the email state" % TXT["change_email"])
    assert not P, "\n".join(P)


def test_c01_same_uid_and_memberships_kept_then_d5(env):
    """C1 + C13 + D5: an anonymous device that already belongs to another trip verifies the invite email → SAME auth.uid()
    (email_change), old membership kept; step 1 prefills the display name from that membership; after create + enter,
    the new trip is shown (not the other trip, whose membership is 'newer'); reload keeps the new trip (cached trip_id)."""
    be = env.backend
    old = be.add_trip_full("טיול ישן", "2026-09-15", "2026-10-06", countries=["VN"])
    be.set_kv(old, "tripname", "טיול ישן")
    be.auto_link = {"trip_id": old, "role": "editor", "status": "active", "display_name": "אור"}
    iid, token = be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = env.new_device("A")
    assert dev.goto(APP_PATH) == "app"
    f02.ensure_user(dev.page)
    uid = dev.uid()
    be.set_member(old, uid, joined_at="2099-01-01T00:00:00+00:00")  # newest joined_at → only the cache can pick the new trip
    f03.fresh_load(dev, APP_PATH + "?invite=1#invite=" + token, ready=False)
    page = dev.page
    st = wait_screen(page, ["code", "step1"])
    assert st == "code", "code screen not reached from the token link on a linked device (screen=%s)" % st
    type_code(page, be.otp_code)
    assert wait_screen(page, "step1") == "step1", "step 1 not reached"
    P = []
    if dev.uid() != uid:
        P.append("auth.uid() changed (email must be linked to the same identity)")
    if len(be.ops("auth.signInAnonymously")) != 1:
        P.append("a new anonymous identity was created")
    if be.users[uid].get("email") != INVITE_EMAIL or not be.users[uid].get("email_confirmed_at"):
        P.append("email not confirmed on the device's uid")
    vo = [c for c in be.otp_calls if c["op"] == "verifyOtp"]
    if not vo or vo[-1]["params"].get("type") != "email_change":
        P.append("verifyOtp not called with type 'email_change': %r" % [c["params"].get("type") for c in vo])
    me = field(page, TXT["s1_me"]).input_value()
    if me != "אור":
        P.append("display name not prefilled from the existing membership (got %r)" % me)
    assert not P, "\n".join(P)
    fill_step1(page, start="2027-04-03", end="2027-04-20")
    press_next(page)
    assert wait_screen(page, "step2") == "step2"
    pick(page, "יפ", "JP")
    press_next(page)
    assert wait_screen(page, "step3") == "step3"
    create_and_done(dev)
    tid = be.trips_created[-1]
    enter_trip(dev)
    if not has(page, DRAFT):
        P.append("new trip name not shown after 'כניסה לטיול'")
    if f02.trip_name_is(page, "טיול ישן") or has(page, "טיול ישן"):
        P.append("the other trip of the same user is shown")
    page.reload(wait_until="domcontentloaded")
    assert f02.wait_ready(page) == "app"
    f02.ensure_user(page)
    page.wait_for_timeout(800)
    if not has(page, DRAFT) or has(page, "טיול ישן"):
        P.append("reload did not keep the new trip (D5)")
    cached = dev.ls().get("pt:_device:active_trip")
    if not cached or json.loads(cached).get("trip_id") != tid:
        P.append("pt:_device:active_trip is not the new trip: %r" % cached)
    m = [r for r in be.members_of(uid) if r["trip_id"] == old]
    if not m or m[0]["status"] != "active":
        P.append("the old trip membership was lost")
    assert not P, "\n".join(P)


def test_c02_code_inputs_typing_backspace_autosubmit(env):
    """§1.3: digits auto-advance, backspace on an empty box goes back, the verify button is enabled only at 6 digits,
    and the 6th digit auto-submits (verifyOtp without tapping the button)."""
    be = env.backend
    dev, iid, token = token_link(env)
    page = dev.page
    assert wait_screen(page, "code") == "code"
    P = []
    boxes = otp_boxes(page)
    assert boxes.count() == 6, "expected 6 code inputs"
    boxes.nth(0).click()
    page.keyboard.press("4")
    page.wait_for_timeout(100)
    if otp_focus(page) != 1:
        P.append("auto-advance: focus after 1st digit is box %d (expected 1)" % otp_focus(page))
    page.keyboard.press("8")
    page.wait_for_timeout(100)
    if otp_values(page)[:2] != ["4", "8"]:
        P.append("digits not in boxes 1-2: %r" % otp_values(page))
    if not is_disabled(page, TXT["verify_btn"]):
        P.append("verify button enabled with 2 digits")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(100)
    page.keyboard.press("Backspace")
    page.wait_for_timeout(100)
    if otp_focus(page) not in (0, 1) or otp_values(page)[1] != "":
        P.append("backspace did not go back / clear (focus %d, values %r)" % (otp_focus(page), otp_values(page)))
    boxes.nth(0).click()
    for b in range(6):
        boxes.nth(b).fill("")
    boxes.nth(0).click()
    page.keyboard.type("4829", delay=60)
    page.wait_for_timeout(150)
    if otp_values(page)[:4] != list("4829"):
        P.append("typing across boxes failed: %r" % otp_values(page))
    page.keyboard.press("x")
    page.wait_for_timeout(80)
    if any(v and not v.isdigit() for v in otp_values(page)):
        P.append("a non-digit was accepted: %r" % otp_values(page))
    n = len([c for c in be.otp_calls if c["op"] == "verifyOtp"])
    page.keyboard.type(be.otp_code[4:], delay=60)
    page.wait_for_timeout(1200)
    vo = [c for c in be.otp_calls if c["op"] == "verifyOtp"][n:]
    if not vo:
        P.append("6th digit did not auto-submit")
    elif vo[0]["params"].get("token") != be.otp_code:
        P.append("verifyOtp token %r != typed code" % vo[0]["params"].get("token"))
    if wait_screen(page, "step1") != "step1":
        P.append("auto-submit did not continue to step 1 (screen=%s)" % screen(page))
    assert not P, "\n".join(P)


def test_c02_code_paste_fills_all(env):
    """§1.3: pasting 6 digits into the first box fills all six and submits."""
    be = env.backend
    dev, iid, token = token_link(env)
    page = dev.page
    assert wait_screen(page, "code") == "code"
    boxes = otp_boxes(page)
    boxes.nth(0).click()
    page.evaluate("(c)=>{const e=document.activeElement;const dt=new DataTransfer();dt.setData('text/plain',c);"
                  "const ev=new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true});"
                  "if(e.dispatchEvent(ev)){e.value=c;e.dispatchEvent(new InputEvent('input',{bubbles:true,data:c,inputType:'insertFromPaste'}))}}",
                  " %s " % be.otp_code)
    page.wait_for_timeout(1200)
    vals = otp_values(page) if screen(page) == "code" else list(be.otp_code)
    vo = [c for c in be.otp_calls if c["op"] == "verifyOtp"]
    assert vals == list(be.otp_code) or vo, "paste did not fill the 6 boxes: %r" % vals
    if not vo:
        if visible(page, TXT["verify_btn"]) and not is_disabled(page, TXT["verify_btn"]):
            click_text(page, TXT["verify_btn"])
    assert wait_screen(page, "step1") == "step1", "pasted code did not verify (screen=%s)" % screen(page)


def test_c02_resend_cooldown_45s_and_spam_hint(env):
    """§1.3: 'שליחה חוזרת בעוד m:ss' disabled for 45 s (controlled clock), then 'שליחה חוזרת' repeats the same send call
    and restarts the cooldown; 'לא הגיע? בדקו בספאם' opens a one-line hint."""
    be = env.backend
    dev, iid, token = token_link(env)
    page = dev.page
    assert wait_screen(page, "code") == "code"
    P = []
    sends = lambda: [c for c in be.calls if c["op"] in ("auth.updateUser", "auth.resend", "auth.signInWithOtp")]
    n0 = len(sends())
    c = find(page, TXT["resend_wait"])
    if not c or not all(x["disabled"] for x in c):
        P.append("countdown control missing or not disabled")
    page.clock.run_for(20000)
    page.wait_for_timeout(300)
    m = re.search(norm(TXT["resend_wait"]) + r"\s*(\d):(\d\d)", btext(page))
    if not m or not (20 <= int(m.group(1)) * 60 + int(m.group(2)) <= 26):
        P.append("countdown after 20 s shows %r (expected ~0:25)" % (m.group(0) if m else None))
    page.clock.run_for(26000)
    page.wait_for_timeout(400)
    if visible(page, TXT["resend_wait"]):
        P.append("still counting down after 46 s")
    r = [x for x in find(page, TXT["resend"]) if TXT["resend_wait"] not in x["text"]]
    if not r or r[0]["disabled"]:
        P.append("'%s' not enabled after 45 s" % TXT["resend"])
    else:
        page.mouse.click(r[0]["x"], r[0]["y"])
        page.wait_for_timeout(600)
        if len(sends()) != n0 + 1:
            P.append("resend did not repeat the send call once (%d calls)" % (len(sends()) - n0))
        else:
            last = sends()[-1]["msg"]
            em = ((last.get("attrs") or {}).get("email") or (last.get("creds") or {}).get("email") or "").lower()
            if em != INVITE_EMAIL:
                P.append("resend sent to %r" % em)
        if not re.search(norm(TXT["resend_wait"]) + r"\s*0:4[45]", btext(page)):
            P.append("cooldown did not restart after resend")
    before = btext(page)
    click_text(page, TXT["spam"])
    page.wait_for_timeout(400)
    after = btext(page)
    if len(after) <= len(before) or not re.search(r"[֐-׿]", after.replace(before, "")):
        P.append("'%s' did not open a hint" % TXT["spam"])
    assert not P, "\n".join(P)


@pytest.mark.parametrize("case", ["wrong", "expired", "rate_verify", "rate_send", "offline"])
def test_c02_code_errors_mapped(env, case):
    """C2 + §1 error table: wrong code (inputs cleared, focus first), expired (code older than 1 h; GoTrue gives the same
    otp_expired error for both), rate limit on verify and on send, offline → the mapped Hebrew line; no navigation; never
    the raw English error."""
    be = env.backend
    if case == "rate_send":
        be.send_outcome = "rate"
    dev, iid, token = token_link(env)
    page = dev.page
    st = wait_screen(page, ["code", "email"])
    assert st in ("code", "email"), "code screen not reached (screen=%s)" % st
    P = []
    want = {"wrong": "err_wrong", "expired": "err_expired", "rate_verify": "err_rate", "rate_send": "err_rate",
            "offline": "err_offline"}[case]
    if case == "rate_send":
        if not wait_has(page, TXT[want], 5):
            P.append("send rate limit: %r not shown" % TXT[want])
    else:
        code = be.otp_code
        if case == "wrong":
            code = "000000"
        elif case == "expired":
            be.expire_otps()
            page.clock.fast_forward(61 * 60 * 1000)
            page.wait_for_timeout(300)
        elif case == "rate_verify":
            be.verify_outcome = "rate"
        elif case == "offline":
            dev.offline(True)
            page.wait_for_timeout(400)
        type_code(page, code)
        if case == "offline" and visible(page, TXT["verify_btn"]) and not is_disabled(page, TXT["verify_btn"]):
            P.append("verify button enabled while offline")
        if not wait_has(page, TXT[want], 5):
            P.append("%s: %r not shown (text: %r)" % (case, TXT[want], btext(page)[-250:]))
        if case == "wrong":
            if any(otp_values(page)):
                P.append("wrong code: inputs not cleared: %r" % otp_values(page))
            if otp_focus(page) != 0:
                P.append("wrong code: focus not on the first box (%d)" % otp_focus(page))
            if has(page, TXT["err_expired"]):
                P.append("wrong code shown as expired")
        if case == "expired" and has(page, TXT["err_wrong"]):
            P.append("expired code shown as wrong")
        if case == "offline":
            vals = otp_values(page)
            dev.offline(False)
            page.wait_for_timeout(600)
    if screen(page) not in ("code", "email"):
        P.append("navigated away from the code screen (screen=%s)" % screen(page))
    for e in AUTH_ERR.values():
        if e["message"] in btext(page):
            P.append("raw error text shown: %r" % e["message"])
    if be.trips_created or be.ct("lookup"):
        P.append("continued to lookup after a failed verification")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("via", ["token", "gate"])
def test_c03_d6_other_confirmed_email_no_auth_call(env, via):
    """C3 + D6: the device's user already has a DIFFERENT confirmed email → card 'המכשיר הזה כבר מקושר למייל אחר (o•••@x)'
    + second line; no auth send call at all (updateUser / signInWithOtp / verifyOtp / resend); nothing changes."""
    be = env.backend
    be.auto_confirmed_email = "orsela.other@gmail.com"
    iid, token = be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    if via == "token":
        dev, _, _ = token_link(env, iid_token=(iid, token))
    else:
        dev = gate_device(env)
        assert wait_text(dev.page, TXT["gate_btn"]), "gate button missing"
        click_text(dev.page, TXT["gate_btn"])
        # §1.3 'email state only when no email is known': a device with a confirmed email may skip the email state and look
        # up ITS OWN email → the 'no active invite' card is accepted here (open question in the QA report); typing the
        # invite email instead must lead to the D6 card. Either way: no auth call.
        if wait_screen(dev.page, ["email", "no_invite", "d6"]) == "no_invite":
            P = [("auth call(s) made: %r" % [c.get("op") for c in be.auth_sends()])] if (be.auth_sends() or be.traced()) else []
            assert not be.ct("create") and not P, "\n".join(P)
            return
        send_email(dev, INVITE_EMAIL)
    page = dev.page
    st = wait_screen(page, "d6")
    P = []
    if st != "d6":
        P.append("D6 card not shown (screen=%s, text=%r)" % (st, btext(page)[:200]))
    masked = "o•••@gmail.com"
    if not has(page, TXT["d6_full"].format(masked=masked)):
        P.append("D6 text with the masked email %r missing" % masked)
    if "orsela.other" in btext(page):
        P.append("current email shown unmasked")
    if not has(page, TXT["d6b"]):
        P.append("D6 second line missing")
    sends = be.traced() + be.auth_sends()
    if sends:
        P.append("auth call(s) made: %r" % sorted({(s.get("kind") or s.get("op")) for s in sends}))
    uid = dev.uid()
    if uid and be.users[uid].get("email") != "orsela.other@gmail.com":
        P.append("the device's email changed")
    if be.ct_calls:
        P.append("create-trip called")
    assert not P, "\n".join(P)


def test_c03_same_confirmed_email_skips_code(env):
    """C3 + §1.3: the device's user already has the invite email confirmed → no code screen, no updateUser; lookup →
    step 1 with the draft name."""
    be = env.backend
    be.auto_confirmed_email = INVITE_EMAIL
    dev, iid, token = token_link(env)
    page = dev.page
    st = wait_screen(page, ["step1", "code", "d6"])
    P = []
    if st != "step1":
        P.append("did not go straight to step 1 (screen=%s)" % st)
    if be.auth_sends() or be.traced():
        P.append("auth call made although the email is already verified: %r" % [c.get("op") or c.get("kind") for c in be.auth_sends() + be.traced()])
    if not be.ct("lookup"):
        P.append("create-trip lookup not called")
    elif not be.ct("lookup")[0]["bearer"] in be.tokens:
        P.append("lookup not sent with the session JWT")
    assert not P, "\n".join(P)


def test_c04_email_owned_by_other_account_no_trip_signs_in(env):
    """C4: invite email belongs to another existing account and this anonymous device has NO active trip →
    signInWithOtp({email, options:{shouldCreateUser:false}}) → verifyOtp(type 'email') → the device switches to that
    account (uid changes) and continues to step 1; lookup/create carry the new JWT."""
    be = env.backend
    other = be.add_account(INVITE_EMAIL)
    dev, iid, token = token_link(env)
    page = dev.page
    anon_uid = None
    st = wait_screen(page, ["code", "other_acct", "email"])
    P = []
    if st != "code":
        P.append("code screen not reached (screen=%s)" % st)
    si = [c for c in be.otp_calls if c["op"] == "signInWithOtp"]
    if not si:
        P.append("signInWithOtp not called after email_exists")
    else:
        if (si[0]["params"].get("email") or "").lower() != INVITE_EMAIL:
            P.append("signInWithOtp email %r" % si[0]["params"].get("email"))
        if (si[0]["params"].get("options") or {}).get("shouldCreateUser") is not False:
            P.append("signInWithOtp without options.shouldCreateUser=false: %r" % si[0]["params"].get("options"))
    assert not P, "\n".join(P)
    anon_uid = dev.uid()
    type_code(page, be.otp_code)
    st = wait_screen(page, "step1")
    if st != "step1":
        P.append("step 1 not reached after the email OTP (screen=%s, text=%r)" % (st, btext(page)[-200:]))
    vo = [c for c in be.otp_calls if c["op"] == "verifyOtp"]
    if not vo or vo[-1]["params"].get("type") not in ("email", "magiclink"):
        P.append("verifyOtp not type 'email': %r" % [c["params"].get("type") for c in vo])
    if dev.uid() != other:
        P.append("device did not switch to the account that owns the email (uid %s, expected %s, was %s)" % (dev.uid(), other, anon_uid))
    lk = be.ct("lookup")
    if not lk or be.tokens.get(lk[-1]["bearer"]) != other:
        P.append("lookup not sent with the other account's JWT")
    assert not P, "\n".join(P)


def test_c04_email_owned_by_other_account_with_trip_card(env):
    """C4: same, but the device already has an active trip membership → card 'המייל הזה כבר משויך לחשבון אחר…'; no
    signInWithOtp / verifyOtp (the failed updateUser that detected email_exists is the only auth call); identity and
    membership unchanged."""
    be = env.backend
    be.add_account(INVITE_EMAIL)
    tid = be.add_trip_full("טיול קיים", "2026-09-15", "2026-10-06")
    be.set_kv(tid, "tripname", "טיול קיים")
    be.auto_link = {"trip_id": tid, "role": "editor", "status": "active", "display_name": "QA"}
    iid, token = be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    dev = env.new_device("A")
    assert dev.goto(APP_PATH) == "app"
    f02.ensure_user(dev.page)
    uid = dev.uid()
    f03.fresh_load(dev, APP_PATH + "?invite=1#invite=" + token, ready=False)
    page = dev.page
    st = wait_screen(page, "other_acct")
    P = []
    if st != "other_acct" or not has(page, TXT["other_acct"]):
        P.append("'already linked to another account' card not shown (screen=%s, text=%r)" % (st, btext(page)[:200]))
    bad = [c for c in be.otp_calls if c["op"] in ("signInWithOtp", "verifyOtp", "resend")]
    if bad:
        P.append("auth call(s) beyond the failed updateUser: %r" % [c["op"] for c in bad])
    ups = [c for c in be.update_calls if (c["attrs"] or {}).get("email")]
    if len(ups) > 1:
        P.append("updateUser called %d times" % len(ups))
    if dev.uid() != uid:
        P.append("device identity changed")
    if not any(m["trip_id"] == tid and m["status"] == "active" for m in be.members_of(uid)):
        P.append("membership lost")
    assert not P, "\n".join(P)


def test_no_active_invite_for_verified_email(env):
    """§1 table: the verified email has no active invite → full card 'לא מצאנו הזמנה פעילה למייל הזה' + second line +
    'חזרה'; nothing created."""
    be = env.backend
    dev = gate_device(env)
    gate_to_email(dev)
    send_email(dev, "nobody@example.com")
    page = dev.page
    assert wait_screen(page, "code") == "code", "code screen not reached (screen=%s)" % screen(page)
    type_code(page, be.otp_code)
    st = wait_screen(page, "no_invite")
    P = []
    if st != "no_invite":
        P.append("no-invite card not shown (screen=%s)" % st)
    for k in ("no_invite", "no_invite2"):
        if not has(page, TXT[k]):
            P.append("missing %r" % TXT[k])
    if not find(page, TXT["back"]):
        P.append("button %r missing" % TXT["back"])
    if not be.ct("lookup"):
        P.append("lookup not called after verify")
    if be.ct("create"):
        P.append("create called")
    assert not P, "\n".join(P)


# =====================================================================================================
# 7–10 · Wizard
# =====================================================================================================
def test_c07_step1_prefill_lang_daycount(env):
    """C7 + §1.4: progress labels; name prefilled from draft_name with its help line; English disabled with 'בקרוב';
    home currency select defaults to ILS and offers USD/EUR; '<N> ימים · ייווצר יום ריק לכל תאריך' follows the dates;
    native date inputs."""
    dev, iid, token = to_step1(env)
    page = dev.page
    P = []
    for t in TXT["progress"]:
        if not has(page, t):
            P.append("progress label %r missing" % t)
    nm = field(page, TXT["s1_name"])
    if nm.input_value() != DRAFT:
        P.append("trip name not prefilled from draft_name (%r)" % nm.input_value())
    if nm.get_attribute("dir") != "auto":
        P.append("trip name input lacks dir=auto")
    if not has(page, TXT["s1_name_help"]):
        P.append("help %r missing" % TXT["s1_name_help"])
    en = find(page, TXT["lang_en"])
    if not en or not all(x["disabled"] for x in en):
        P.append("English not disabled")
    if not has(page, TXT["soon"]):
        P.append("'בקרוב' next to English missing")
    hv = home_value(page) or ""
    if "ILS" not in hv:
        P.append("home currency default is not ILS (%r)" % hv)
    opts = page.evaluate("(s)=>{const e=[...document.querySelectorAll(s)].filter(x=>x.offsetParent!==null)[0];return e?[...e.options].map(o=>o.value+' '+o.textContent):[]}", SEL["currency_select"])
    for c in BASES:
        if not any(c in o for o in opts):
            P.append("home currency option %s missing" % c)
    a, b = dates(page)
    fill_step1(page, start="2027-04-03", end="2027-04-20")
    if day_count(page) != 18:
        P.append("day count for 03/04–20/04/2027 is %r (expected 18)" % day_count(page))
    fill_step1(page, end="2027-04-03")
    if day_count(page) != 1:
        P.append("day count for a single day is %r (expected 1)" % day_count(page))
    fill_step1(page, start="2028-02-28", end="2028-03-01")
    if day_count(page) != 3:
        P.append("day count across the leap day is %r (expected 3)" % day_count(page))
    assert not P, "\n".join(P)


STEP1_INVALID = [
    ("empty trip name", dict(name="")),
    ("blank trip name", dict(name="   ")),
    ("empty display name", dict(me="")),
    ("end before start", dict(start="2027-04-20", end="2027-04-03")),
    ("121 days", dict(start="2027-01-01", end="2027-05-01")),
    ("missing end date", dict(end="")),
]


def test_c07_step1_validation(env):
    """C7 + §1.4: 'המשך' refuses empty/blank names, end < start, > 120 days, a missing date; accepts 1 day and 120 days;
    names longer than 80 / 40 characters are never accepted (refused or capped)."""
    dev, iid, token = to_step1(env)
    page = dev.page
    good = dict(name="יפן 2027", me="דנה", start="2027-04-03", end="2027-04-20")
    P = []
    for label, bad in STEP1_INVALID:
        fill_step1(page, **dict(good, **bad))
        press_next(page)
        if screen(page) != "step1":
            P.append("%s: 'המשך' advanced (screen=%s)" % (label, screen(page)))
            click_text(page, TXT["back"])
            wait_screen(page, "step1")
    for label, nm, me in (("81-char trip name", "א" * 81, "דנה"), ("41-char display name", "יפן", "ב" * 41)):
        fill_step1(page, **dict(good, name=nm, me=me))
        got_n, got_m = field(page, TXT["s1_name"]).input_value(), field(page, TXT["s1_me"]).input_value()
        press_next(page)
        if screen(page) != "step1" and (len(got_n) > 80 or len(got_m) > 40):
            P.append("%s accepted (%d / %d chars)" % (label, len(got_n), len(got_m)))
        if screen(page) != "step1":
            click_text(page, TXT["back"])
            wait_screen(page, "step1")
    for label, ok in (("1 day", dict(start="2027-04-03", end="2027-04-03")), ("120 days", dict(start="2027-01-01", end="2027-04-30"))):
        fill_step1(page, **dict(good, **ok))
        press_next(page)
        if wait_screen(page, "step2", 4) != "step2":
            P.append("%s refused" % label)
        else:
            click_text(page, TXT["back"])
            if wait_screen(page, "step1") != "step1":
                P.append("'חזרה' on step 2 did not return to step 1")
                break
    assert not P, "\n".join(P)


SEARCHES = [("יפ", ["JP"], ["TH"]), ("jap", ["JP"], ["TH"]), ("JAPAN", ["JP"], []), ("קור", ["KR", "KP"], ["JP"]),
            ("פן", ["JP"], []), ("curacao", ["CW"], []), ("turkiye", ["TR"], []), ("cote", ["CI"], []),
            ("korea", ["KR", "KP"], [])]


def test_c08_search_hebrew_english_prefix_contains_diacritics(env):
    """C8 + §1.5: search by Hebrew and English names, prefix and contains, case- and diacritic-insensitive
    ("יפ"→יפן, "jap"→Japan, "קור"→both Koreas, "curacao"→Curaçao, "turkiye"→Türkiye, "cote"→Côte d’Ivoire)."""
    dev, iid, token = to_step2(env)
    page = dev.page
    if not COUNTRIES:
        pytest.fail("app/countries.json missing or unreadable")
    P = []
    for q, want, not_want in SEARCHES:
        search(page, q)
        for c in want:
            if not results(page, he(c)) and not results(page, COUNTRIES[c]["en"]):
                P.append("search %r: %s (%s) not in the results" % (q, c, he(c)))
        for c in not_want:
            if results(page, he(c)):
                P.append("search %r: unrelated %s (%s) listed" % (q, c, he(c)))
    search(page, "")
    assert not P, "\n".join(P)


def test_c08_popular_chips_order_and_add(env):
    """C8 + §1.5: 'נפוצות' chips in the spec order (TH, GR, US, IT, ES, FR, GB, DE, PT, CY, GE, VN, JP, IN, NL, CZ, HU, AT,
    MX, AE); a chip adds its country; selected row shows '<symbol> <currency> · <CODE> · UTC±h <capital>'; × removes."""
    dev, iid, token = to_step2(env)
    page = dev.page
    P = []
    txt = popular_container_text(page)
    if not txt:
        pytest.fail("'נפוצות' row not found")
    flags = re.findall(r"[\U0001F1E6-\U0001F1FF]{2}", txt)
    codes = ["".join(chr(ord(ch) - 0x1F1E6 + 65) for ch in f) for f in flags]
    if codes != POPULAR_ORDER:
        P.append("popular chips order %r, expected %r" % (codes, POPULAR_ORDER))
    chip = find(page, flag("TH"))
    chip = [c for c in chip if c["clk"]] or chip
    if not chip:
        P.append("TH chip not clickable")
    else:
        page.mouse.click(chip[0]["x"], chip[0]["y"])
        page.wait_for_timeout(400)
        if selected_count(page) != 1 or not has(page, he("TH")):
            P.append("chip did not add תאילנד (נבחרו · %d)" % selected_count(page))
        if not re.search(r"฿\s*באט\s*·\s*THB\s*·\s*UTC\+7\s*בנגקוק", btext(page)):
            P.append("selected row for TH lacks '฿ באט · THB · UTC+7 בנגקוק'")
    pick(page, "יפ", "JP")
    if not re.search(r"¥\s*ין\s*·\s*JPY\s*·\s*UTC\+9\s*טוקיו", btext(page)):
        P.append("selected row for JP lacks '¥ ין · JPY · UTC+9 טוקיו'")
    pick(page, "united states", "US")
    if not re.search(r"\$\s*דולר\s*·\s*USD\s*·\s*UTC-4\s*וושינגטון", btext(page)):
        P.append("selected row for US lacks '$ דולר · USD · UTC-4 וושינגטון' (offset at the trip start date, April = EDT)")
    t = btext(page)
    i_th, i_jp = t.find(he("TH")), t.rfind(he("JP"))
    if not (0 <= i_th < i_jp):
        P.append("selected list not in selection order")
    remove_country(page, "TH")
    if selected_count(page) != 2:
        P.append("× did not remove תאילנד (נבחרו · %d)" % selected_count(page))
    x = find(page, SEL["remove_aria"].format(he=he("JP")))
    if x and (x[0]["w"] < 44 or x[0]["h"] < 44):
        P.append("× is %dx%d (< 44px)" % (x[0]["w"], x[0]["h"]))
    assert not P, "\n".join(P)


def test_c08_currency_rules(env):
    """C8 + §1.5: home chip first marked 'בית', other bases next, destination currencies in country order, deduped and
    bases excluded; 'K מתוך 10'; removing a country removes its currency unless another selected country uses it; help
    line; home=USD reorders (USD בית, ILS, EUR)."""
    dev, iid, token = to_step2(env)
    page = dev.page
    P = []
    if currency_codes(page)[:3] != ["ILS", "USD", "EUR"] or not home_marked(page, "ILS"):
        P.append("initial currencies %r (ILS בית, USD, EUR expected)" % currency_codes(page))
    if currency_count(page) != 3:
        P.append("count %r (expected '3 מתוך 10')" % currency_count(page))
    if not has(page, TXT["s2_help"]):
        P.append("help line missing")
    pick(page, "יפ", "JP")
    pick(page, "יוון", "GR")      # EUR: a base, must not be added again
    pick(page, "שוויי", "CH")     # CHF
    pick(page, "ליכט", "LI")      # CHF again (shared)
    want = ["ILS", "USD", "EUR", "JPY", "CHF"]
    if currency_codes(page) != want:
        P.append("currencies %r, expected %r" % (currency_codes(page), want))
    if currency_count(page) != 5:
        P.append("count %r (expected 5)" % currency_count(page))
    remove_country(page, "CH")
    if "CHF" not in currency_codes(page):
        P.append("CHF removed although ליכטנשטיין still uses it")
    remove_country(page, "LI")
    if "CHF" in currency_codes(page):
        P.append("CHF still listed after removing both countries")
    remove_country(page, "JP")
    if "JPY" in currency_codes(page):
        P.append("JPY still listed after removing יפן")
    click_text(page, TXT["back"])
    if wait_screen(page, "step1") != "step1":
        P.append("'חזרה' did not go to step 1")
    else:
        if day_count(page) != 18 or field(page, TXT["s1_me"]).input_value() != "דנה":
            P.append("step 1 values not kept after 'חזרה'")
        select_home(page, "USD")
        press_next(page)
        wait_screen(page, "step2")
        if currency_codes(page)[:3] != ["USD", "ILS", "EUR"] or not home_marked(page, "USD"):
            P.append("home=USD: currencies %r (USD בית, ILS, EUR expected)" % currency_codes(page))
        if selected_count(page) != 1:
            P.append("selected countries not kept across steps (נבחרו · %d)" % selected_count(page))
    assert not P, "\n".join(P)


def add_currency(page, code):
    click_text(page, TXT["add_cur"])
    page.wait_for_timeout(500)
    inp = page.locator('[role="dialog"] input, input[placeholder*="מטבע"], input[placeholder*="חיפוש"]').filter(visible=True)
    assert inp.count(), "currency sheet search input not found"
    inp.last.fill(code)
    page.wait_for_timeout(400)
    opts = [o for o in find(page, code) if o["clk"] and "מתוך 10" not in o["text"]]
    assert opts, "currency %s not offered in the sheet" % code
    page.mouse.click(opts[-1]["x"], opts[-1]["y"])
    page.wait_for_timeout(300)
    conf = [c for c in find(page, "הוספה (") if c["clk"]]
    if conf:
        page.mouse.click(conf[0]["x"], conf[0]["y"])
    page.wait_for_timeout(400)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def test_c08_add_currency_and_cap_10(env):
    """C8 + §1.5: '+ הוספה' adds a currency (searchable sheet; added chip has ×; sent as kind 'added'); at 10 the add
    button is disabled; a newly selected country whose currency doesn't fit shows 'המטבע MXN לא נכנס – הממיר מלא (10/10).
    אפשר להסיר מטבע אחר.'; the server is never asked for more than 10."""
    dev, iid, token = to_step2(env)
    page = dev.page
    P = []
    add_currency(page, "AED")
    if "AED" not in currency_codes(page):
        P.append("'+ הוספה' did not add AED: %r" % currency_codes(page))
    for q, c in (("יפ", "JP"), ("דרום קור", "KR"), ("תאיל", "TH"), ("וייט", "VN"), ("בריטניה", "GB"), ("הודו", "IN")):
        pick(page, q, c)
    if currency_count(page) != 10 or len(currency_codes(page)) != 10:
        P.append("expected 10 currencies, got %r (%r)" % (currency_count(page), currency_codes(page)))
    add = find(page, TXT["add_cur"])
    if not add or not all(a["disabled"] for a in add):
        P.append("'+ הוספה' not disabled at 10/10")
    pick(page, "מקסיקו", "MX")
    if not has(page, TXT["full_note"].format(code="MXN")):
        P.append("inline note for MXN missing")
    if "MXN" in currency_codes(page) or currency_count(page) != 10:
        P.append("cap exceeded: %r" % currency_codes(page))
    press_next(page)
    if wait_screen(page, "step3") == "step3":
        create_and_done(dev)
        body = (env.backend.ct("create") or [{"body": {}}])[-1]["body"]
        cur = body.get("currencies") or []
        if len(cur) + 3 > 10:
            P.append("client sent %d currencies (+3 bases > 10)" % len(cur))
        if not any(c.get("code") == "AED" and c.get("kind") == "added" for c in cur):
            P.append("AED not sent as kind 'added': %r" % cur)
        if not all(c.get("kind") == "destination" for c in cur if c.get("code") != "AED"):
            P.append("destination currencies not kind 'destination': %r" % cur)
    else:
        P.append("could not continue to step 3 with 8 countries")
    assert not P, "\n".join(P)


def test_c08_country_count_1_to_15(env):
    """§1.5: 0 countries → cannot continue; more than 15 → refused (never sent)."""
    dev, iid, token = to_step2(env)
    page = dev.page
    P = []
    press_next(page)
    if screen(page) != "step2":
        P.append("continued with 0 countries")
    txt = popular_container_text(page) or ""
    for f in re.findall(r"[\U0001F1E6-\U0001F1FF]{2}", txt)[:16]:
        c = [x for x in find(page, f) if x["clk"]]
        if c:
            page.mouse.click(c[0]["x"], c[0]["y"])
            page.wait_for_timeout(150)
    n = selected_count(page)
    press_next(page)
    if n > 15 and screen(page) != "step2":
        P.append("continued with %d countries (max 15)" % n)
    if screen(page) == "step3":
        click_text(page, TXT["create"])
        page.wait_for_timeout(1000)
        for c in env.backend.ct("create"):
            if len(c["body"].get("countries") or []) > 15:
                P.append("create sent %d countries" % len(c["body"]["countries"]))
    assert not P, "\n".join(P)


def test_c09_review_rows_edit_roundtrip_role_sent(env):
    """C9 + §1.6: review rows טיול / תאריכים (LTR range · N ימים) / את/ה בקבוצה ('<name> · מנהל/ת') / יעדים (flags + names)
    / מטבעות (home '(בית)'); 'עריכה' on rows 1, 2, 4 returns to the right step with state kept; the role choice is sent;
    the create body is exactly what the review showed."""
    dev, iid, token = to_step3(env)
    page, be = dev.page, env.backend
    P = []
    t = btext(page)
    for k in ("s3_sub", "role_card"):
        if not has(page, TXT[k]):
            P.append("missing %r" % TXT[k])
    if DRAFT not in t:
        P.append("trip name row missing")
    if not re.search(r"03/04/2027\s*-\s*20/04/2027\s*·\s*18 ימים", t):
        P.append("dates row lacks '03/04/2027 – 20/04/2027 · 18 ימים'")
    if norm(TXT["me_row"].format(name="דנה")) not in t:
        P.append("row 'דנה · מנהל/ת' missing")
    for c in ("JP", "KR"):
        if not re.search(flag(c) + r"\s*" + he(c), t):
            P.append("destinations row lacks %s %s" % (flag(c), he(c)))
    if not re.search(r"ILS\s*\(בית\)\s*·\s*USD\s*·\s*EUR\s*·\s*JPY\s*·\s*KRW", t):
        P.append("currencies row lacks 'ILS (בית) · USD · EUR · JPY · KRW'")
    edits = sorted(find(page, TXT["edit"], exact=True), key=lambda c: c["y"])
    if len(edits) != 3:
        P.append("%d 'עריכה' links (expected 3: trip, dates, destinations)" % len(edits))
    ed = find(page, TXT["role_editor"], exact=True)
    if not ed:
        P.append("role segmented control missing")
    assert not P, "\n".join(P)
    # row 1 → step 1, change the name; through step 2 back to step 3
    page.mouse.click(edits[0]["x"], edits[0]["y"])
    if wait_screen(page, "step1") != "step1":
        P.append("'עריכה' on טיול did not open step 1")
    else:
        if field(page, TXT["s1_me"]).input_value() != "דנה" or day_count(page) != 18:
            P.append("step 1 state lost after 'עריכה'")
        set_value(field(page, TXT["s1_name"]), "יפן וקוריאה")
        press_next(page)
        wait_screen(page, "step2")
        if selected_count(page) != 2:
            P.append("countries lost on the way back (נבחרו · %d)" % selected_count(page))
        press_next(page)
        wait_screen(page, "step3")
        if not has(page, "יפן וקוריאה"):
            P.append("edited name not on the review")
    # row 2 (dates) → step 1
    edits = sorted(find(page, TXT["edit"], exact=True), key=lambda c: c["y"])
    if len(edits) >= 2:
        page.mouse.click(edits[1]["x"], edits[1]["y"])
        if wait_screen(page, "step1") != "step1":
            P.append("'עריכה' on תאריכים did not open step 1")
        else:
            press_next(page)
            wait_screen(page, "step2")
            press_next(page)
            wait_screen(page, "step3")
    # row 4 (destinations) → step 2
    edits = sorted(find(page, TXT["edit"], exact=True), key=lambda c: c["y"])
    if len(edits) >= 3:
        page.mouse.click(edits[2]["x"], edits[2]["y"])
        if wait_screen(page, "step2") != "step2":
            P.append("'עריכה' on יעדים did not open step 2")
        else:
            if selected_count(page) != 2:
                P.append("step 2 state lost after 'עריכה'")
            press_next(page)
            wait_screen(page, "step3")
    click_text(page, TXT["role_viewer"], exact=True)
    create_and_done(dev)
    cr = be.ct("create")
    if len(cr) != 1:
        P.append("%d create calls" % len(cr))
    else:
        b = cr[0]["body"]
        exp = {"name": "יפן וקוריאה", "display_name": "דנה", "start_date": "2027-04-03", "end_date": "2027-04-20",
               "home_currency": "ILS", "default_lang": "he", "default_role": "viewer", "countries": ["JP", "KR"],
               "currencies": [{"code": "JPY", "kind": "destination"}, {"code": "KRW", "kind": "destination"}]}
        for k, v in exp.items():
            if b.get(k) != v:
                P.append("create body %s=%r, expected %r" % (k, b.get(k), v))
        cap = COUNTRIES["JP"]["capital"]
        ce = b.get("center") or {}
        if abs(float(ce.get("lat", 0)) - cap["lat"]) > 0.01 or abs(float(ce.get("lng", 0)) - cap["lng"]) > 0.01:
            P.append("center %r is not the first country's capital %r" % (ce, cap))
        if not cr[0]["bearer"] or cr[0]["bearer"] not in be.tokens:
            P.append("create not sent with the session JWT")
        if cr[0]["via"] == "fetch" and cr[0]["apikey"] != PT_KEY:
            P.append("create fetch without apikey")
    assert not P, "\n".join(P)


def test_c10_double_tap_creates_one_trip(env):
    """C10 + §1.6: two taps on 'יצירת הטיול' in the same instant send ONE create; Done reached; exactly one trip."""
    dev, iid, token = to_step3(env)
    page, be = dev.page, env.backend
    c = find(page, TXT["create"])
    assert c, "create button missing"
    page.evaluate("(i)=>{const e=(window.__qaLast||[])[i];const b=e.closest('button,a,[role=button]')||e;b.click();b.click()}", c[0]["i"])
    page.mouse.click(c[0]["x"], c[0]["y"])
    st = wait_screen(page, "done", 12)
    P = []
    if st != "done":
        P.append("Done not reached (screen=%s)" % st)
    if len(be.ct("create")) != 1:
        P.append("%d create calls for a double tap (expected 1)" % len(be.ct("create")))
    if len(be.trips_created) != 1:
        P.append("%d trips created" % len(be.trips_created))
    assert not P, "\n".join(P)


def test_c10_retry_after_network_error_same_trip(env):
    """C10 + §1 table: the create response is lost (network error after the server committed) → a Hebrew error, still
    on step 3; tapping again returns the SAME trip (idempotent, created:false) and reaches Done; one trip in total."""
    dev, iid, token = to_step3(env)
    page, be = dev.page, env.backend
    be.ct_drop_next = 1
    click_text(page, TXT["create"])
    page.wait_for_timeout(1500)
    P = []
    if screen(page) != "step3":
        P.append("left step 3 after a network error (screen=%s)" % screen(page))
    if not re.search(r"[֐-׿]", btext(page).replace(norm(TXT["s3_title"]), "")):
        P.append("no Hebrew error shown")
    assert not P, "\n".join(P)
    click_text(page, TXT["create"])
    st = wait_screen(page, "done", 12)
    if st != "done":
        P.append("retry did not reach Done (screen=%s)" % st)
    cr = be.ct("create")
    if len(cr) != 2 or cr[1]["resp"].get("created") is not False:
        P.append("expected 2 create calls, the 2nd created:false: %r" % [(c["status"], c["resp"]) for c in cr])
    if len(be.trips_created) != 1:
        P.append("%d trips created" % len(be.trips_created))
    tid = be.trips_created[0] if be.trips_created else None
    code = be.rows["trip_join_codes"][(tid,)]["code"] if tid else "?"
    if not has(page, "join/#code=" + code):
        P.append("Done does not show the join URL of the one trip")
    assert not P, "\n".join(P)


def test_invite_invalid_between_lookup_and_create(env):
    """§1 table: invite revoked after lookup → create answers invite_invalid → the same 'no active invite' card; nothing
    created."""
    dev, iid, token = to_step3(env)
    page, be = dev.page, env.backend
    be.invites[iid]["revoked_at"] = iso(be.now)
    click_text(page, TXT["create"])
    st = wait_screen(page, "no_invite", 8)
    P = []
    if st != "no_invite" or not has(page, TXT["no_invite2"]):
        P.append("no-invite card not shown after invite_invalid (screen=%s)" % st)
    if be.trips_created:
        P.append("a trip was created")
    if "invite_invalid" in btext(page):
        P.append("raw error code shown")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("where", ["step1", "step3"])
def test_offline_wizard_disabled_and_kept(env, where):
    """§1 table: offline on a wizard step → 'אין חיבור. נסו שוב כשהרשת תחזור.', primary button disabled, no request;
    entered data kept; back online → enabled again."""
    be = env.backend
    if where == "step1":
        dev, iid, token = to_step1(env)
        fill_step1(dev.page, name="שם שהוקלד", me="דנה", start="2027-04-03", end="2027-04-20")
        btn = TXT["next"]
    else:
        dev, iid, token = to_step3(env)
        btn = TXT["create"]
    page = dev.page
    dev.offline(True)
    page.wait_for_timeout(600)
    P = []
    if not has(page, TXT["err_offline"]):
        P.append("offline line missing")
    if not is_disabled(page, btn):
        P.append("%r enabled while offline" % btn)
    c = find(page, btn)
    if c:
        page.mouse.click(c[0]["x"], c[0]["y"])
        page.wait_for_timeout(500)
    if be.ct("create"):
        P.append("create sent while offline")
    if where == "step1" and screen(page) != "step1":
        P.append("advanced while offline")
    dev.offline(False)
    page.wait_for_timeout(800)
    if is_disabled(page, btn):
        P.append("%r still disabled after the network returned" % btn)
    if where == "step1" and field(page, TXT["s1_name"]).input_value() != "שם שהוקלד":
        P.append("typed name lost")
    assert not P, "\n".join(P)


# =====================================================================================================
# 11–16 · Result
# =====================================================================================================
def test_c11_c12_done_link_whatsapp_copy(env):
    """C11 (client view) + C12: Done shows '<name> · <flags> · N ימים', the join URL https://orsela.github.io/Plan_Travel/
    join/#code=<CODE> (LTR), 'בקרוב' card, saved line; WhatsApp = wa.me/?text= with the trip name and URL; copy writes
    the URL and toasts 'הקישור הועתק'. The fake DB holds the trip as §2 describes."""
    dev, iid, token = to_step3(env)
    page, be = dev.page, env.backend
    create_and_done(dev)
    tid = be.trips_created[0]
    code = be.rows["trip_join_codes"][(tid,)]["code"]
    url = JOIN_BASE + "#code=" + code
    P = []
    t = btext(page)
    if not re.search(re.escape(DRAFT) + r"\s*·\s*" + flag("JP") + r"\s*" + flag("KR") + r"\s*·\s*18 ימים", t):
        P.append("summary line '%s · 🇯🇵 🇰🇷 · 18 ימים' missing" % DRAFT)
    if "join/#code=" + code not in t:
        P.append("join URL not shown")
    dirs = f03.email_is_ltr(page, "join/#code=" + code)
    if not dirs or any(d != "ltr" for d in dirs):
        P.append("join URL not LTR (%r)" % dirs)
    for k in ("join_card", "saved_line", "soon"):
        if not has(page, TXT[k]):
            P.append("missing %r" % TXT[k])
    if chrome_visible(page):
        P.append("trip chrome on Done: %r" % chrome_visible(page))
    w = wa_url(dev) or ""
    if not w.startswith("https://wa.me/?text="):
        P.append("WhatsApp target %r is not https://wa.me/?text=…" % w)
    else:
        msg = wa_text(w)
        if DRAFT not in msg or url not in msg:
            P.append("WhatsApp text lacks the trip name or URL: %r" % msg)
    page.evaluate("()=>{window.__qaToasts=[];new MutationObserver(()=>{window.__qaToasts.push(document.body.innerText)}).observe(document.body,{subtree:true,childList:true,characterData:true})}")
    click_text(page, TXT["copy"], exact=True)
    page.wait_for_timeout(600)
    copied = page.evaluate("()=>window.__qaWatch.copied")
    if url not in copied:
        P.append("copy wrote %r, expected %r" % (copied, url))
    seen = " ".join(page.evaluate("()=>window.__qaToasts||[]")) + btext(page)
    if TXT["copied"] not in seen:
        P.append("toast %r not shown" % TXT["copied"])
    # C11 as stored by the fake (mirrors §2): days, members
    days = json.loads(be.kv(tid, "trip"))
    if len(days) != 18 or days[0]["date"] != "03/04/2027" or days[-1]["date"] != "20/04/2027":
        P.append("harness: fake days wrong")
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


# CHANGE 2026-10-12 F04-QA-03: criterion 11 / F04-DB-02 (new test)
HOME_LAYOUT_RE = re.compile(r"""((?:let|const|var)\s+HOME_LAYOUT\s*=\s*)(['"])v[12]\2""")


def serve_home_layout(env, layout):
    """Serve the app with the v2.15.2 home-layout flag set to `layout` (static flag flip, like serve_wizard_off)."""
    src = app_html()
    assert HOME_LAYOUT_RE.search(src), "harness: top-level HOME_LAYOUT flag not found in app/index.html"
    env.server.overrides[APP_PATH] = HOME_LAYOUT_RE.sub(r"\1'%s'" % layout, src, count=1).encode("utf-8")


def wait_home_any(page, timeout=30000):
    """f02.wait_ready only knows the v2 home (#homeV2); with HOME_LAYOUT 'v1' the home panel is #home."""
    page.wait_for_function("""()=>['homeV2','home'].some(id=>{const h=document.getElementById(id);
      return !!h&&h.classList.contains('active')&&getComputedStyle(h).display!=='none'})""", timeout=timeout)
    page.wait_for_timeout(700)


def trip_name_problems(dev, want, label):
    """#tripName (home header; in the DOM in both home layouts), the fallback, and ניהול → הגדרות מסע (row + modal)."""
    page = dev.page
    P = []
    f02.tab(page, "home")
    page.wait_for_timeout(500)
    got = page.evaluate("()=>{const e=document.getElementById('tripName');return e?e.textContent.trim():null}")
    if got != want:
        P.append("%s: home header #tripName = %r, expected %r" % (label, got, want))
    if has(page, TXT["tripname_fallback"]):
        P.append("%s: fallback %r shown" % (label, TXT["tripname_fallback"]))
    f03.open_more(page)
    if not visible(page, TXT["mgmt_row"], "#more"):
        P.append("%s: row %r not in 'עוד'" % (label, TXT["mgmt_row"]))
        return P
    click_text(page, TXT["mgmt_row"])
    if not wait_has(page, TXT["trip_settings"], 6):
        P.append("%s: %r not shown under %r" % (label, TXT["trip_settings"], TXT["mgmt_row"]))
        return P
    row = page.evaluate("""(t)=>{const vis=e=>e.offsetParent!==null;
      const h=[...document.querySelectorAll('body *')].filter(e=>vis(e)&&(e.innerText||'').includes(t));
      const leaf=h.filter(e=>!h.some(o=>o!==e&&e.contains(o)))[0];
      let r=leaf;for(let i=0;i<3&&r&&r.parentElement;i++)r=r.parentElement;return r?r.innerText:null}""", TXT["trip_settings"])
    if not row or norm(want) not in norm(row):
        P.append("%s: ניהול → %r row does not show the trip name: %r" % (label, TXT["trip_settings"], row))
    if TXT["tripname_fallback"] in (row or "") or has(page, TXT["tripname_fallback"]):
        P.append("%s: fallback %r on the management screen" % (label, TXT["tripname_fallback"]))
    click_text(page, TXT["trip_settings"])
    page.wait_for_timeout(700)
    vals = page.evaluate("()=>[...document.querySelectorAll('input,textarea')].filter(e=>e.offsetParent!==null).map(e=>e.value)")
    if want not in vals:
        P.append("%s: הגדרות מסע dialog has no field with the trip name (visible values %r)" % (label, vals[:8]))
    if TXT["tripname_fallback"] in vals:
        P.append("%s: הגדרות מסע dialog shows the fallback" % label)
    return P


@pytest.mark.parametrize("layout", ["v1", "v2"])
def test_c11_tripname_shown_home_and_settings(env, layout):
    """C11 (F04-DB-02, Or 2026-10-12): after create, trip_kv `tripname` = the trimmed entered name (fake mirrors §2 step 5);
    entering the trip shows that name in the home header #tripName (HOME_LAYOUT 'v1' served via a static flag flip; 'v2'
    = as delivered) and in ניהול → הגדרות מסע — never the fallback 'מסע של חלומות'; a reload keeps it."""
    serve_home_layout(env, layout)
    want = "טיול משפחה QA"
    dev, iid, token = to_step1(env)
    page, be = dev.page, env.backend
    fill_step1(page, name="  %s  " % want, me="דנה", start="2027-04-03", end="2027-04-05")
    press_next(page)
    assert wait_screen(page, "step2") == "step2", "step 2 not reached (screen=%s)" % screen(page)
    pick(page, "יפ", "JP")
    press_next(page)
    assert wait_screen(page, "step3") == "step3", "step 3 not reached (screen=%s)" % screen(page)
    create_and_done(dev)
    tid = be.trips_created[0]
    P = []
    if be.kv(tid, "tripname") != want:
        P.append("trip_kv tripname = %r, expected %r" % (be.kv(tid, "tripname"), want))
    if be.rows["trips"][(tid,)]["name"] != want:
        P.append("harness: trips.name = %r" % be.rows["trips"][(tid,)]["name"])
    click_text(page, TXT["enter"])
    page.wait_for_timeout(800)
    page.wait_for_load_state("domcontentloaded")
    wait_home_any(page)
    f02.ensure_user(page)
    if layout == "v1":
        shown = page.evaluate("()=>{const e=document.getElementById('tripName');return !!e&&e.offsetParent!==null}")
        if not shown:
            P.append("v1: #tripName not visible in the home header")
    P += trip_name_problems(dev, want, "after create")
    page.reload(wait_until="domcontentloaded")
    wait_home_any(page)
    f02.ensure_user(page)
    page.wait_for_timeout(600)
    P += trip_name_problems(dev, want, "after reload")
    if be.kv(tid, "tripname") != want:
        P.append("tripname changed after entering the trip: %r" % be.kv(tid, "tripname"))
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


# CHANGE 2026-10-12 F04-QA-04: helpers + tests for the tappable first-steps rows (alpha.4.1, F04-HOME-04)
WP_OPEN_JS = "()=>{const m=document.getElementById('waypointModal');return !!m&&m.classList.contains('open')}"
USER_OPEN_JS = "()=>!!document.querySelector('#userModal.open')"
FS_ROWS_JS = """()=>[1,2,3].map(i=>{const e=document.getElementById('ptFs'+i);if(!e)return null;
  const r=e.getBoundingClientRect();return {i,done:e.getAttribute('data-done'),role:e.getAttribute('role'),
  tab:e.getAttribute('tabindex'),w:r.width,h:r.height,t:e.innerText}})"""


def home_active(page):
    return page.evaluate("""()=>['homeV2','home'].some(id=>{const h=document.getElementById(id);
      return !!h&&h.classList.contains('active')&&getComputedStyle(h).display!=='none'})""")


def add_point_problems(dev, label, allow_user_modal=False):
    """After the trigger: #waypointModal is open with 'הוספת נקודת עניין · יום 1'; closing it returns to home.
    With allow_user_modal, the legacy 'מי אני' #userModal is an accepted immediate result (out of scope, F05)."""
    page = dev.page
    P = []
    end = time.time() + 5
    while time.time() < end and not page.evaluate(WP_OPEN_JS) and not page.evaluate(USER_OPEN_JS):
        page.wait_for_timeout(150)
    if not page.evaluate(WP_OPEN_JS):
        if allow_user_modal and page.evaluate(USER_OPEN_JS):
            return P
        return ["%s: #waypointModal not open (userModal open=%s)" % (label, page.evaluate(USER_OPEN_JS))]
    title = norm(page.evaluate("()=>document.getElementById('waypointModal').innerText"))
    if not re.search(re.escape(TXT["wp_modal"]) + r"\s*·\s*יום 1\b", title):
        P.append("%s: modal is not for day 1: %r" % (label, title[:120]))
    f02.close_modal(page, "waypointModal")
    page.wait_for_timeout(700)
    if not home_active(page):
        P.append("%s: did not return to home after closing the modal" % label)
    return P


@pytest.mark.parametrize("how", ["tap", "enter", "space"])
def test_c13_fs_row3_opens_add_point(env, how):
    """§1.8 alpha.4.1: the open row 'הוספת היעד הראשון ליום 1' (#ptFs3) = 'הוספת נקודה': day 1 + #waypointModal open,
    home after close; keyboard Enter / Space activate it too. Device user is set (boot → ensure_user)."""
    tid, code, dev = boot_trip(env, role="manager", n_days=3)
    page = dev.page
    assert wait_has(page, TXT["first_steps"], 6), "first-steps card missing"
    if how == "tap":
        page.locator("#ptFs3").click()
    else:
        page.locator("#ptFs3").focus()
        page.keyboard.press("Enter" if how == "enter" else " ")
    P = add_point_problems(dev, "row 3 (%s)" % how)
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


def test_c13_fs_row3_without_device_user(env):
    """Coordinator note: without a device user the legacy 'מי אני' modal may come first (deferred to F05) — accepted;
    otherwise the add-point modal must open for day 1."""
    tid, code, dev = boot_trip(env, role="manager", n_days=3)
    page = dev.page
    page.evaluate("()=>{for(const k of Object.keys(localStorage))if(/user/i.test(k)&&!/supabase|sb-/.test(k))localStorage.removeItem(k)}")
    page.reload(wait_until="domcontentloaded")
    wait_home_any(page)
    if page.evaluate(USER_OPEN_JS):
        f02.close_modal(page, "userModal")
    assert wait_has(page, TXT["first_steps"], 6), "first-steps card missing"
    page.locator("#ptFs3").click()
    P = add_point_problems(dev, "row 3 without user", allow_user_modal=True)
    assert not P, "\n".join(P)


def test_c13_fs_row2_tap_marks_shared(env):
    """§1.8 alpha.4.1: tapping the open row 'שליחת קישור לקבוצה' (#ptFs2) = the WhatsApp share: wa.me with the join URL,
    pt:<trip>:firststeps {shared:true}, the row becomes done and the count goes 1 → 2 מתוך 3."""
    tid, code, dev = boot_trip(env, role="manager", n_days=3)
    page = dev.page
    assert wait_has(page, TXT["first_steps"], 6), "first-steps card missing"
    P = []
    if not re.search(r"1\s*מתוך\s*3", btext(page)):
        P.append("count is not '1 מתוך 3' before")
    page.evaluate(WA_GUARD_JS)
    page.evaluate("()=>{window.__qaOpened=[]}")
    n = len(env_net(dev))
    page.locator("#ptFs2").click()
    page.wait_for_timeout(700)
    opened = page.evaluate("()=>window.__qaOpened||[]") + [r["url"] for r in env_net(dev)[n:]]
    wa = [u for u in opened if "wa.me" in u]
    if not wa:
        P.append("row 2 did not open WhatsApp (opened %r)" % opened[:3])
    elif JOIN_BASE + "#code=" + code not in wa_text(wa[0]):
        P.append("row 2 WhatsApp text lacks the join URL: %r" % wa[0])
    raw = dev.ls().get("pt:%s:firststeps" % tid)
    if not raw or not json.loads(raw).get("shared"):
        P.append("row 2 did not record {shared:true}: %r" % raw)
    rows = page.evaluate(FS_ROWS_JS)
    if not rows[1] or rows[1]["done"] != "true" or rows[1]["role"] == "button":
        P.append("row 2 not shown as done after sharing: %r" % rows[1])
    if not re.search(r"2\s*מתוך\s*3", btext(page)):
        P.append("count did not update to '2 מתוך 3' (%r)" % page.evaluate("()=>{const e=document.getElementById('ptFsCount');return e&&e.innerText}"))
    assert not P, "\n".join(P)


@pytest.mark.parametrize("state", ["none_done", "shared_done"])
def test_c13_fs_rows_tappable_only_when_open(env, state):
    """§1.8 alpha.4.1: open rows have role=button, tabindex=0, the '‹' marker and are ≥44px tall (and fit 390px); done
    rows (row 1 always; row 2 after sharing) have no role=button, no tabindex, no '‹'."""
    pre = {"pt:{tid}:firststeps": '{"shared":true}'} if state == "shared_done" else None
    tid, code, dev = boot_trip(env, role="manager", n_days=3, pre_ls=pre)
    page = dev.page
    assert wait_has(page, TXT["first_steps"], 6), "first-steps card missing"
    rows = page.evaluate(FS_ROWS_JS)
    P = []
    want_open = {3} if state == "shared_done" else {2, 3}
    for r in rows:
        if not r:
            P.append("row missing")
            continue
        if r["i"] in want_open:
            if r["done"] == "true":
                P.append("row %d should be open: %r" % (r["i"], r))
            if r["role"] != "button" or r["tab"] != "0":
                P.append("open row %d: role=%r tabindex=%r" % (r["i"], r["role"], r["tab"]))
            if "‹" not in r["t"]:
                P.append("open row %d lacks '‹'" % r["i"])
            if r["h"] < 44 - 0.5 or r["w"] > VIEWPORT["width"]:
                P.append("open row %d size %dx%d (need ≥44 tall, ≤390 wide)" % (r["i"], r["w"], r["h"]))
        else:
            if r["done"] != "true":
                P.append("row %d should be done: %r" % (r["i"], r))
            if r["role"] == "button" or r["tab"] is not None or "‹" in r["t"]:
                P.append("done row %d is still tappable-looking: %r" % (r["i"], r))
    P += layout_problems(page, "#ptFirstSteps", "first-steps " + state)
    assert not P, "\n".join(P)


def test_c13_enter_trip_home(env):
    """C13 + §1.8: 'כניסה לטיול' opens the new trip (not the Vietnam seed) with all global elements, trip name + dates in
    the header, the 'צעדים ראשונים' card (manager) with 'הקמת הטיול' done, buttons 'שליחה בווטסאפ' / 'למסלול', empty days
    showing 'עוד לא נוספו נקודות'; WhatsApp from Done marks 'שליחת קישור לקבוצה'; no page errors."""
    dev, iid, token = to_step3(env)
    page, be = dev.page, env.backend
    create_and_done(dev)
    tid = be.trips_created[0]
    wa_url(dev)
    enter_trip(dev)
    page.wait_for_timeout(800)
    P = []
    t = btext(page)
    if DRAFT not in t:
        P.append("trip name not shown")
    if not re.search(r"03/04\s*-\s*20/04/2027|03/04/2027", t):
        P.append("trip dates not in the header")
    seed = [s for s in SEED_MARKERS if s in t]
    if seed:
        P.append("Vietnam seed shown: %r" % seed)
    ch = chrome_visible(page)
    if sorted(ch) != sorted(SEL["trip_chrome"]):
        P.append("global elements missing: %r of %r" % (ch, SEL["trip_chrome"]))
    if not wait_has(page, TXT["first_steps"], 6):
        P.append("'צעדים ראשונים' card missing for the manager")
    for k in TXT["fs_items"] + [TXT["wa"], TXT["to_route"]]:
        if not has(page, k):
            P.append("first-steps card lacks %r" % k)
    if not wait_has(page, TXT["empty_day"], 6):
        P.append("empty days do not show %r" % TXT["empty_day"])
    raw = dev.ls().get("pt:%s:firststeps" % tid)
    if not raw or not json.loads(raw).get("shared"):
        P.append("WhatsApp on Done did not record pt:<trip>:firststeps {shared:true}: %r" % raw)
    # CHANGE 2026-10-12 F04-QA-04: "הוספת נקודה" opens day 1 + the add-point modal and returns home (was: route tab)
    click_text(page, TXT["to_route"], exact=True)
    P += add_point_problems(dev, "'%s'" % TXT["to_route"])
    if any(s in btext(page) for s in SEED_MARKERS):
        P.append("seed after the add-point flow")
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


@pytest.mark.parametrize("role", ["editor", "viewer"])
def test_c13_first_steps_managers_only(env, role):
    """§1.8: 'צעדים ראשונים' is for managers only."""
    tid, code, dev = boot_trip(env, role=role)
    assert not has(dev.page, TXT["first_steps"]), "first-steps card shown to a %s" % role
    assert wait_has(dev.page, TXT["empty_day"], 6), "empty days do not show %r" % TXT["empty_day"]


def test_c13_first_steps_state_and_disappears(env):
    """§1.8/§4: shared flag (pt:<trip>:firststeps) and a waypoint on any day complete the card → it disappears; with only
    the waypoint the card stays; WhatsApp on the card records the shared flag."""
    be = env.backend
    days = empty_days(dt.date(2027, 4, 3), 3)
    days[1]["waypoints"] = [{"name": "מקדש", "lat": 35.0, "lng": 135.7, "notes": ""}]
    tid, code, dev = boot_trip(env, role="manager", days=days)
    page = dev.page
    P = []
    if not wait_has(page, TXT["first_steps"], 6):
        P.append("card missing while 'shared' is not done")
    wa = wa_url(dev) or ""
    page.wait_for_timeout(400)
    raw = dev.ls().get("pt:%s:firststeps" % tid)
    if not raw or not json.loads(raw).get("shared"):
        P.append("WhatsApp on the card did not record {shared:true} (%r)" % raw)
    if code not in wa:
        P.append("card WhatsApp does not carry the join URL: %r" % wa)
    page.reload(wait_until="domcontentloaded")
    f02.wait_ready(page)
    f02.ensure_user(page)
    page.wait_for_timeout(600)
    if has(page, TXT["first_steps"]):
        P.append("card still shown with all three steps done")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("n", [0, 1, 18])
def test_c14_empty_days_render(env, n):
    """C14 + §4: a stored trip with 0 / 1 / 18 empty days (cloud, flag on) never brings back SEED_DATA; every tab renders
    without page errors; days show 'עוד לא נוספו נקודות'."""
    tid, code, dev = boot_trip(env, role="manager", n_days=n)
    page = dev.page
    P = []
    for tab in ("home", "route", "journal", "budget", "more", "home"):
        f02.tab(page, tab)
        page.wait_for_timeout(300)
        seed = [s for s in SEED_MARKERS if s in btext(page)]
        if seed:
            P.append("%s tab shows the seed: %r" % (tab, seed))
    if n and not wait_has(page, TXT["empty_day"], 6):
        P.append("%r not shown for %d empty days" % (TXT["empty_day"], n))
    kv = env.backend.kv(tid, "trip")
    if kv is None or len(json.loads(kv)) != n:
        P.append("the stored trip was overwritten (now %r days)" % (kv and len(json.loads(kv))))
    if page_errors(dev):
        P.append("page errors: %r" % page_errors(dev)[:3])
    assert not P, "\n".join(P)


@pytest.mark.parametrize("role", ["manager", "editor", "viewer"])
def test_c15_more_join_link_row(env, role):
    """C15 + §1.9: 'עוד' shows 'קישור הצטרפות לקבוצה' for managers only; it opens a sheet with the same URL (from
    trip_join_codes), WhatsApp and copy."""
    tid, code, dev = boot_trip(env, role=role)
    page = dev.page
    f03.open_more(page)
    P = []
    if role != "manager":
        if visible(page, TXT["more_row"]):
            P.append("row shown to a %s" % role)
        assert not P, "\n".join(P)
        return
    if not visible(page, TXT["more_row"]):
        pytest.fail("row %r missing for a manager" % TXT["more_row"])
    click_text(page, TXT["more_row"])
    page.wait_for_timeout(800)
    url = JOIN_BASE + "#code=" + code
    if "join/#code=" + code not in btext(page):
        P.append("sheet does not show the join URL with code %s" % code)
    if not env.backend.queries("trip_join_codes"):
        P.append("trip_join_codes was not read")
    w = wa_url(dev) or ""
    if url not in wa_text(w):
        P.append("sheet WhatsApp lacks the URL: %r" % w)
    click_text(page, TXT["copy"], exact=True)
    page.wait_for_timeout(400)
    if url not in page.evaluate("()=>window.__qaWatch.copied"):
        P.append("sheet copy did not write the URL")
    assert not P, "\n".join(P)


def test_c16_join_page_coming_soon_clears_hash(env):
    """C16 + §1.10: /join/#code=… shows 'Lonely Planner' (§8) + 'ההצטרפות לטיול תיפתח בקרוב' + text; the hash is removed; the code
    is neither shown nor sent anywhere; 390px clean."""
    serve_pages(env)
    if "/join/" not in env.server.overrides:
        pytest.fail("join/index.html missing")
    dev = env.new_device("J")
    page = dev.page
    page.goto(env.server.origin + "/join/#code=ABCD2345", wait_until="domcontentloaded")
    P = []
    if not wait_has(page, TXT["join_title"], 6):
        P.append("title %r missing" % TXT["join_title"])
    if not has(page, TXT["join_text"]) or not has(page, APP_NAME):  # CHANGE 2026-10-12 F04-QA-05: brand was "Plan_Travel"
        P.append("text / brand missing")
    page.wait_for_timeout(500)
    if "#code" in page.url or "ABCD2345" in page.url:
        P.append("hash not cleared: %s" % page.url)
    if "ABCD2345" in page.content():
        P.append("code displayed / kept in the DOM")
    ext = [r["url"] for r in env.net if "ABCD2345" in r["url"] or "supabase.co" in r["url"]]
    if ext:
        P.append("code or Supabase requested: %r" % ext)
    P += layout_problems(page, None, "/join/")
    assert not P, "\n".join(P)


def test_c16_invite_page_button_opens_app(env):
    """C16 + §1.1: valid /invite/ → '…הזמין אותך לנהל את הקבוצה "<draft>". ההקמה לוקחת כ-3 דקות.', step 1 text, enabled
    link 'פתיחה באפליקציה והקמת הטיול' → ../app/?invite=1#invite=<token>, home-screen note; invalid state unchanged."""
    serve_pages(env)
    if "/invite/" not in env.server.overrides:
        pytest.fail("invite/index.html missing")
    be = env.backend
    iid, token = be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7, inviter="אור")
    dev = env.new_device("I")
    page = dev.page
    page.goto(env.server.origin + "/invite/#invite=" + token, wait_until="domcontentloaded")
    P = []
    if not wait_has(page, TXT["inv_ok"], 8):
        pytest.fail("valid invite page not shown: %r" % btext(page)[:200])
    t = btext(page)
    if not re.search(r'הזמין אותך לנהל את הקבוצה\s*"?' + re.escape(DRAFT) + r'"?\.\s*' + re.escape(TXT["inv_copy"]), t):
        P.append("copy '…הזמין אותך לנהל את הקבוצה \"%s\". ההקמה לוקחת כ-3 דקות.' missing" % DRAFT)
    for k in ("inv_step1", "inv_note"):
        if not has(page, TXT[k]):
            P.append("missing %r" % TXT[k])
    # CHANGE 2026-10-12 F04-QA-03: F04-INV-02 — the old note wording must be gone
    if has(page, TXT["inv_note_old"]):
        P.append("old note wording %r still shown" % TXT["inv_note_old"])
    if has(page, TXT["f03_land_btn"]):
        P.append("old 'בקרוב' button still shown")
    c = find(page, TXT["inv_btn"])
    if not c:
        P.append("button %r missing" % TXT["inv_btn"])
    else:
        if c[0]["disabled"]:
            P.append("button disabled")
        href = page.evaluate("(i)=>{const e=(window.__qaLast||[])[i];const a=e&&e.closest('a');return a?[a.getAttribute('href'),a.href]:null}", c[0]["i"])
        want_rel = "../app/?invite=1#invite=" + token
        want_abs = env.server.origin + "/app/?invite=1#invite=" + token
        if not href or (href[0] != want_rel and href[1] != want_abs):
            P.append("button href %r, expected %r" % (href, want_rel))
    if "#invite" in page.url:
        P.append("token left in the address bar")
    P += layout_problems(page, None, "/invite/")
    page.goto(env.server.origin + "/__qa__/blank.html")
    page.goto(env.server.origin + "/invite/#invite=" + "Z" * 43, wait_until="domcontentloaded")
    if not wait_has(page, TXT["inv_bad"], 8):
        P.append("invalid state changed (no %r)" % TXT["inv_bad"])
    assert not P, "\n".join(P)


# =====================================================================================================
# 19 · WIZARD_FEATURE='off' == alpha.3 (F02/F03 suites run in both states by run.sh)
# =====================================================================================================
def test_c19_flag_declared_next_to_admin_feature():
    """§1: top-level const WIZARD_FEATURE='on' next to ADMIN_FEATURE (same classic script block)."""
    html = app_html()
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    blk = [b for b in blocks if re.search(r"const\s+ADMIN_FEATURE\s*=", b)]
    assert blk, "ADMIN_FEATURE flag block not found"
    assert re.search(r"""^\s*const\s+WIZARD_FEATURE\s*=\s*['"]on['"]""", blk[0], re.M), \
        "const WIZARD_FEATURE='on' not declared in the flags script next to ADMIN_FEATURE"


def test_c19_off_gate_and_token_link_are_alpha3(env):
    """C19: 'off' → no second card on the not-connected screen; a token link shows the F03 landing with the disabled
    'התחלת הקמה · בקרוב' button; no updateUser / OTP / create-trip traffic."""
    serve_wizard_off(env)
    be = env.backend
    dev = gate_device(env, "G")
    P = []
    for k in ("gate_title", "gate_btn"):
        if has(dev.page, TXT[k]):
            P.append("'off': %r on the not-connected card" % TXT[k])
    iid, token = be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7)
    d2 = env.new_device("T")
    d2.goto(APP_PATH + "?invite=1#invite=" + token, ready=False)
    st = wait_screen(d2.page, ["f03_landing", "code", "step1"])
    if st != "f03_landing":
        P.append("'off': token link did not show the F03 landing (screen=%s)" % st)
    elif not is_disabled(d2.page, TXT["f03_land_btn"]):
        P.append("'off': F03 landing button not disabled")
    if be.auth_sends() or be.ct_calls:
        P.append("'off': auth / create-trip traffic: %r" % ([c["op"] for c in be.auth_sends()] + [c["action"] for c in be.ct_calls]))
    assert not P, "\n".join(P)


def test_c19_off_no_first_steps_no_join_row(env):
    """C19: 'off' → a manager of a new trip gets no first-steps card and no 'קישור הצטרפות לקבוצה' row."""
    serve_wizard_off(env)
    tid, code, dev = boot_trip(env, role="manager")
    P = []
    if has(dev.page, TXT["first_steps"]):
        P.append("'off': first-steps card shown")
    f03.open_more(dev.page)
    if visible(dev.page, TXT["more_row"]):
        P.append("'off': join-link row in 'עוד'")
    assert not P, "\n".join(P)


@pytest.mark.parametrize("state", ["on", "off"])
def test_c19_boot_prefers_cached_trip_only_when_on(env, state):
    """D5 / §4: two active memberships, the cached pt:_device:active_trip is the OLDER one. 'on' → the cached trip;
    'off' → alpha.3: the newest joined_at — unless the served app has SWITCH_FEATURE='on' (F20, architect decision
    2026-10-13): then 'off' also boots the cached trip."""
    if state == "off":
        serve_wizard_off(env)
    # CHANGE 2026-10-13 F20-QA-02: F20 dev notes §6.6 (DECIDED) — WIZARD off + SWITCH on boots the cached trip as well
    switch_on = bool(re.search(r"""const\s+SWITCH_FEATURE\s*=\s*['"]on['"]""", app_html()))
    be = env.backend
    a = be.add_trip_full("טיול א", "2026-09-15", "2026-10-06")
    b = be.add_trip_full("טיול ב", "2026-11-01", "2026-11-10")
    be.set_kv(a, "tripname", "טיול א")
    be.set_kv(b, "tripname", "טיול ב")
    be.auto_link = {"trip_id": b, "role": "editor", "status": "active", "display_name": "QA"}
    dev = env.new_device("A")
    assert dev.goto(APP_PATH) == "app"
    f02.ensure_user(dev.page)
    uid = dev.uid()
    be.add_member(a, uid, "editor", "active", "QA", joined_at="2020-01-01T00:00:00+00:00")
    dev.seed_ls({"pt:_device:active_trip": json.dumps({"trip_id": a, "role": "editor"})})
    dev.page.reload(wait_until="domcontentloaded")
    assert f02.wait_ready(dev.page) == "app"
    f02.ensure_user(dev.page)
    f02.wait_until(lambda: f02.trip_name_is(dev.page, "טיול א") or f02.trip_name_is(dev.page, "טיול ב"), page=dev.page, msg="trip name")
    want = "טיול א" if (state == "on" or switch_on) else "טיול ב"  # CHANGE 2026-10-13 F20-QA-02: `or switch_on`
    assert f02.trip_name_is(dev.page, want), "'%s' (SWITCH %s): expected %r (cached=%s), got the other trip" % (
        state, "on" if switch_on else "off", want, "טיול א")


# =====================================================================================================
# 20 · 390px / RTL / 44px / trip chrome
# =====================================================================================================
LAYOUT_SCREENS = ["gate", "email", "code", "step1", "step2", "step3", "done", "home"]


@pytest.mark.parametrize("scr", LAYOUT_SCREENS)
def test_c20_layout_390_rtl_touch(env, scr):
    """C20: no horizontal scroll, RTL, touch ≥44px on screens 2–8; no trip chrome on 2–7; all global elements on 8."""
    P = []
    if scr in ("gate", "email"):
        dev = gate_device(env)
        if scr == "email":
            gate_to_email(dev)
    elif scr == "code":
        dev, _, _ = token_link(env)
        assert wait_screen(dev.page, "code") == "code"
    elif scr == "step1":
        dev, _, _ = to_step1(env)
    elif scr == "step2":
        dev, _, _ = to_step2(env)
        pick(dev.page, "יפ", "JP")
    elif scr == "step3":
        dev, _, _ = to_step3(env)
    else:
        dev, _, _ = to_step3(env)
        create_and_done(dev)
        if scr == "home":
            enter_trip(dev)
    page = dev.page
    if scr == "home":
        mark = f03.mark_container(page, "text:" + TXT["to_route"], TXT["first_steps"], "fs")
        if not mark:
            P.append("first-steps card not found on home")
        else:
            P += layout_problems(page, '[data-qa-mark="fs"]', scr)
        r = page.evaluate("()=>[document.scrollingElement.scrollWidth,innerWidth]")
        if r[0] > r[1] + 1:
            P.append("home: horizontal scroll")
        if sorted(chrome_visible(page)) != sorted(SEL["trip_chrome"]):
            P.append("home: global elements %r" % chrome_visible(page))
    else:
        P += layout_problems(page, None, scr)
        if scr != "gate" and chrome_visible(page):
            P.append("%s: trip chrome visible %r" % (scr, chrome_visible(page)))
        if scr == "gate" and chrome_visible(page):
            P.append("gate: trip chrome visible %r" % chrome_visible(page))
    if page_errors(dev):
        P.append("%s: page errors %r" % (scr, page_errors(dev)[:3]))
    assert not P, "\n".join(P)


# =====================================================================================================
# 21 · Static (the parts a browser suite can check; DB / advisors: sql/qa_f04_cases.md)
# =====================================================================================================
def _extract(html, names, tmp):
    p = tmp / ("x%d.html" % (abs(hash(html)) % 10 ** 8))
    p.write_text(html, encoding="utf-8")
    r = f02.node([str(f02.JS_TOOLS / "extract.js"), str(p)] + names)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


STATIC = ["protected:" + n for n in PROTECTED] + [
    "app_version", "pt_version", "title_version", "change_comments", "node_check_app", "node_check_invite",
    "node_check_join", "countries_json", "currencies_json", "sw_no_precache_of_json", "join_page_outside_scope",
    "no_live_project_ref", "no_localstorage_clear"]


@pytest.mark.parametrize("check", STATIC)
def test_c21_static(check, tmp_path):
    """C21 (static part): protected functions byte-identical to alpha.3; APP_VERSION / PT_VERSION = VERSION (alpha.5 since F20), <title>
    == "Lonely Planner";
    'CHANGE 2026-10-12 F04-…'; node --check on every inline script of app/, invite/, join/; countries.json / currencies.json
    per §4; not precached by the SW; /join/ outside the PWA scope."""
    html = app_html()
    if check.startswith("protected:"):
        name = check.split(":", 1)[1]
        a = _extract(alpha3_html(), [name], tmp_path)["found"][name]
        b = _extract(html, [name], tmp_path)["found"][name]
        assert len(a) == 1, "harness: %s found %d times in alpha.3" % (name, len(a))
        assert b and a[0] in b, "%s is not byte-identical to alpha.3" % name
    elif check == "app_version":
        assert re.search(r"""const\s+APP_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html), "APP_VERSION != %s" % VERSION
    elif check == "pt_version":
        assert re.search(r"""PT_VERSION\s*=\s*['"]%s['"]""" % re.escape(VERSION), html), "PT_VERSION != %s" % VERSION
    elif check == "title_version":
        # CHANGE 2026-10-12 F04-QA-05: spec §8 — <title> is exactly the app name, no version (was: carries VERSION)
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        assert m and m.group(1).strip() == APP_NAME, "<title> is not exactly %r: %r" % (APP_NAME, m and m.group(1))
    elif check == "change_comments":
        miss = [p for p in ("app/index.html", "invite/index.html", "join/index.html")
                if not (REPO_DIR / p).is_file() or "CHANGE 2026-10-12 F04-" not in (REPO_DIR / p).read_text(encoding="utf-8")]
        assert not miss, "no 'CHANGE 2026-10-12 F04-…' comment in %r" % miss
    elif check.startswith("node_check_"):
        rel = {"node_check_app": "app/index.html", "node_check_invite": "invite/index.html", "node_check_join": "join/index.html"}[check]
        f = REPO_DIR / rel
        assert f.is_file(), "%s missing" % rel
        dd = tmp_path / "scripts"
        dd.mkdir()
        r = f02.node([str(f02.JS_TOOLS / "extract.js"), str(f)], env={**os.environ, "DUMP_DIR": str(dd)})
        assert r.returncode == 0, r.stderr
        files = sorted(list(dd.glob("*.js")) + list(dd.glob("*.mjs")))
        assert files, "no inline scripts found in %s" % rel
        bad = [x.name for x in files if f02.node(["--check", str(x)]).returncode != 0]
        assert not bad, "node --check failed in %s: %r" % (rel, bad)
    elif check == "countries_json":
        data = json.loads((APP_DIR / "countries.json").read_text(encoding="utf-8"))
        assert isinstance(data, list) and len(data) >= 245, "countries.json has %d entries (≥ 245)" % len(data)
        bad = [c.get("code") for c in data if not (re.match(r"^[A-Z]{2}$", str(c.get("code"))) and c.get("he") and c.get("en")
                                                   and c.get("flag") == flag(c["code"]) and re.match(r"^[A-Z]{3}$", str(c.get("currency")))
                                                   and isinstance(c.get("tz"), list) and c["tz"]
                                                   and isinstance(c.get("capital"), dict) and {"he", "en", "lat", "lng"} <= set(c["capital"])
                                                   and isinstance(c.get("popular"), bool))]
        assert not bad, "malformed countries.json entries: %r" % bad[:10]
        pop = sorted(c["code"] for c in data if c["popular"])
        assert pop == sorted(POPULAR_ORDER), "popular set %r != spec %r" % (pop, sorted(POPULAR_ORDER))
        assert len({c["code"] for c in data}) == len(data), "duplicate codes"
    elif check == "currencies_json":
        cur = json.loads((APP_DIR / "currencies.json").read_text(encoding="utf-8"))
        codes = {c.get("code") for c in cur}
        need = {c["currency"] for c in json.loads((APP_DIR / "countries.json").read_text(encoding="utf-8"))} | set(BASES)
        assert need <= codes, "currencies missing from currencies.json: %r" % sorted(need - codes)
        bad = [c.get("code") for c in cur if not (c.get("symbol") and c.get("he") and c.get("en") and isinstance(c.get("common"), bool))]
        assert not bad, "malformed currencies.json entries: %r" % bad[:10]
    elif check == "sw_no_precache_of_json":
        sw = (APP_DIR / "sw.js").read_text(encoding="utf-8")
        assert "countries.json" not in sw and "currencies.json" not in sw, "sw.js references countries/currencies.json (§4: not precached)"
    elif check == "join_page_outside_scope":
        man = json.loads((APP_DIR / "manifest.json").read_text(encoding="utf-8"))
        scope = man.get("scope") or "./"
        assert "join" not in scope and (REPO_DIR / "join" / "index.html").is_file(), "join/ missing or inside the PWA scope (%r)" % scope
    elif check == "no_live_project_ref":
        assert f02.LIVE_REF not in html
    elif check == "no_localstorage_clear":
        assert not re.search(r"localStorage\s*\.\s*clear\s*\(", html)


# =====================================================================================================
# Harness self-check: the fake create-trip / OTP follow the spec (so client tests rest on the right semantics)
# =====================================================================================================
def test_harness_fake_semantics():
    be = F04Backend()
    uid = str(uuid.uuid4())
    tok = "fake-at." + uid
    be.tokens[tok] = uid
    be.users[uid] = {"id": uid, "email": "", "is_anonymous": True}
    good = {"name": " יפן 2027 ", "display_name": "דנה", "start_date": "2027-04-03", "end_date": "2027-04-20",
            "home_currency": "ILS", "default_lang": "he", "default_role": "editor", "countries": ["JP", "KR"],
            "currencies": [{"code": "JPY", "kind": "destination"}], "center": {"lat": 35.68, "lng": 139.69}}
    assert be._create_trip(tok, {"action": "lookup"}) == (403, {"error": "email_not_verified"})
    assert be._create_trip(None, {"action": "lookup"})[0] == 401
    iid, token = be.add_invite("dana@example.com", "יפן 2027", sent_days_ago=0, expires_in_days=7)
    assert be.check(token) is True
    assert be._invite_manager(None, {"action": "check", "token": token})[1]["email"] == "dana@example.com"
    assert be._invite_manager(None, {"action": "check", "token": "x"})[1] == {"valid": False}
    # OTP: email_change keeps uid
    assert be.update_user(tok, {"email": "dana@example.com"}, {}).get("user")
    assert be.verify_otp("A", tok, {"email": "dana@example.com", "token": "000000", "type": "email_change"})["error"]["code"] == "otp_expired"
    assert be.verify_otp("A", tok, {"email": "dana@example.com", "token": OTP, "type": "email_change"})["user"]["id"] == uid
    assert be.users[uid]["email_confirmed_at"]
    s, r = be._create_trip(tok, {"action": "lookup"})
    assert s == 200 and set(r) == {"found", "draft_name", "inviter_name", "expires_at"}
    for k, v in (("name", ""), ("name", "א" * 81), ("display_name", "ב" * 41), ("end_date", "2027-04-02"),
                 ("end_date", "2027-08-01"), ("home_currency", "GBP"), ("default_lang", "en"), ("default_role", "manager"),
                 ("countries", []), ("countries", ["JP", "JP"]), ("currencies", [{"code": "EUR", "kind": "destination"}]),
                 ("center", {"lat": 91, "lng": 0})):
        be.ct_rate.clear()
        s, r = be._create_trip(tok, dict(good, action="create", **{k: v}))
        assert (s, r.get("field")) == (400, k), (k, v, s, r)
    many = [{"code": c, "kind": "destination"} for c in ("JPY", "KRW", "THB", "VND", "GBP", "CHF", "INR", "MXN")]
    assert be._create_trip(tok, dict(good, action="create", currencies=many)) == (400, {"error": "too_many_currencies"})
    s, r = be._create_trip(tok, dict(good, action="create"))
    assert s == 200 and r["created"] and r["join_url"] == JOIN_BASE + "#code=" + r["join_code"]
    assert all(ch in JOIN_ALPHABET for ch in r["join_code"]) and len(r["join_code"]) == 8
    days = json.loads(be.kv(r["trip_id"], "trip"))
    assert len(days) == 18 and days[0]["date"] == "03/04/2027" and days[-1]["date"] == "20/04/2027" and days[0]["country"] == "JP"
    assert be.kv(r["trip_id"], "tripname") == "יפן 2027"  # CHANGE 2026-10-12 F04-QA-03: §2 step 5, trimmed plain text
    cur = sorted(be.rows["trip_currencies"].values(), key=lambda x: x["sort"])
    assert [c["currency_code"] for c in cur if c["trip_id"] == r["trip_id"]] == ["ILS", "USD", "EUR", "JPY"]
    s2, r2 = be._create_trip(tok, dict(good, action="create", name="אחר"))
    assert s2 == 200 and r2["trip_id"] == r["trip_id"] and r2["created"] is False and len(be.trips_created) == 1
    be2 = F04Backend()
    _, n = validate_payload(dict(good, start_date="2028-02-28", end_date="2028-03-01"))
    assert n == 3
    be2.users[uid] = dict(be.users[uid])
    be2.tokens[tok] = uid
    iid2, _ = be2.add_invite("dana@example.com", "x", sent_days_ago=0, expires_in_days=7, revoked=True)
    assert be2._create_trip(tok, dict(good, action="create")) == (409, {"error": "invite_invalid"})
    other = be2.add_account("other@example.com")
    anon = str(uuid.uuid4())
    be2.users[anon] = {"id": anon, "email": "", "is_anonymous": True}
    be2.tokens["t2"] = anon
    assert be2.update_user("t2", {"email": "other@example.com"}, {})["error"]["code"] == "email_exists"
    assert be2.sign_in_with_otp("A", "t2", {"email": "nobody@example.com", "options": {"shouldCreateUser": False}})["error"]["code"] == "otp_disabled"
    assert be2.sign_in_with_otp("A", "t2", {"email": "other@example.com", "options": {"shouldCreateUser": False}}).get("messageId")
    res = be2.verify_otp("A", "t2", {"email": "other@example.com", "token": OTP, "type": "email"})
    assert res["session"]["user"]["id"] == other


# =====================================================================================================
# CHANGE 2026-10-12 F04-QA-05: alpha.4.2 — app name "Lonely Planner" (spec §8) and new address (spec §8.1)
# =====================================================================================================
def old_name_hits(page, scope=None, vn=True):
    """Old app names in the rendered text of `scope` (default body) and in document.title."""
    t = page.evaluate("(s)=>{const e=s?document.querySelector(s):document.body;return [e?e.innerText:'',document.title]}", scope)
    txt = "\n".join(t)
    names = OLD_NAMES + (["ויאטנם 2026"] if vn else [])
    return [n for n in names if n in txt], txt


NAME_SCREENS = ["gate", "email", "code", "step1", "step2", "step3", "done", "home_card", "more_sheet", "admin",
                "landing_invalid", "landing_off_valid", "invite_valid", "invite_invalid", "join"]


@pytest.mark.parametrize("scr", NAME_SCREENS)
def test_n01_no_old_name_rendered(env, scr):
    """§8: no rendered 'Plan_Travel' / 'Vietnam Travel Planner' (nor 'ויאטנם 2026' as the app name) on the screens before a
    trip exists, the trip-less pages and the F04/F03 manager UI; 'Lonely Planner' shown where §8 puts the brand (landing,
    wizard header, spam hint, admin sub 'Lonely Planner · סופר-אדמין', /invite/, /join/). Trip content (a trip's own
    name/header) is out of scope, so home/admin are checked inside their F04/F03 regions only."""
    be = env.backend
    P = []
    scope, vn, need = None, True, APP_NAME
    if scr == "gate":
        dev = gate_device(env)
        need = None  # §8 lists no brand on the F02 card
    elif scr == "email":
        dev = gate_device(env)
        gate_to_email(dev)
    elif scr in ("code", "step1", "step2", "step3", "done"):
        if scr == "code":
            dev, _, _ = token_link(env)
            assert wait_screen(dev.page, "code") == "code", "code screen not reached"
            click_text(dev.page, TXT["spam"])
            dev.page.wait_for_timeout(400)
            hint = dev.page.evaluate("()=>{const e=document.getElementById('ptWzSpamHint');return e?e.innerText:''}")
            if APP_NAME not in hint:
                P.append("spam hint lacks %r: %r" % (APP_NAME, hint))
        elif scr == "step1":
            dev, _, _ = to_step1(env)
        elif scr == "step2":
            dev, _, _ = to_step2(env)
        else:
            dev, _, _ = to_step3(env)
            if scr == "done":
                create_and_done(dev)
    elif scr == "home_card":
        tid, code, dev = boot_trip(env, role="manager", n_days=3)
        assert wait_has(dev.page, TXT["first_steps"], 6), "first-steps card missing"
        scope, need = "#ptFirstSteps", None
    elif scr == "more_sheet":
        tid, code, dev = boot_trip(env, role="manager", n_days=3)
        f03.open_more(dev.page)
        click_text(dev.page, TXT["more_row"])
        dev.page.wait_for_timeout(800)
        scope, need = "#ptF04Sheet", None
    elif scr == "admin":
        tid, dev = f03.boot(env, admin=True, email="or@example.com")
        f03.open_admin(dev.page)
        vn, need = False, APP_NAME + " · סופר-אדמין"   # the admin list may show a trip named "ויאטנם 2026"
    elif scr == "landing_invalid":
        dev = env.new_device("L")
        dev.goto(APP_PATH + "?invite=1#invite=" + "Z" * 43, ready=False)
        assert wait_has(dev.page, TXT["inv_bad"], 8), "invalid landing not shown: %r" % btext(dev.page)[:200]
    elif scr == "landing_off_valid":
        serve_wizard_off(env)
        dev, _, _ = token_link(env)
        assert wait_screen(dev.page, "f03_landing") == "f03_landing", "'off': F03 landing not shown"
    elif scr in ("invite_valid", "invite_invalid"):
        serve_pages(env)
        iid, token = be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7, inviter="אור")
        dev = env.new_device("I")
        dev.page.goto(env.server.origin + "/invite/#invite=" + (token if scr == "invite_valid" else "Z" * 43),
                      wait_until="domcontentloaded")
        assert wait_has(dev.page, TXT["inv_ok"] if scr == "invite_valid" else TXT["inv_bad"], 8), "invite page state"
    else:
        serve_pages(env)
        dev = env.new_device("J")
        dev.page.goto(env.server.origin + "/join/#code=ABCD2345", wait_until="domcontentloaded")
        assert wait_has(dev.page, TXT["join_title"], 6), "join page not shown"
    dev.page.wait_for_timeout(500)
    hits, txt = old_name_hits(dev.page, scope, vn)
    if hits:
        P.append("%s: old app name rendered: %r" % (scr, hits))
    if need and norm(need) not in norm(txt):
        P.append("%s: %r not shown" % (scr, need))
    assert not P, "\n".join(P)


def _meta(html, name):
    m = re.search(r"""<meta[^>]+name=["']%s["'][^>]*>""" % re.escape(name), html, re.I)
    c = m and re.search(r"""content=["']([^"']*)["']""", m.group(0))
    return c.group(1) if c else None


@pytest.mark.parametrize("check", ["manifest_name", "manifest_short_name", "apple_title", "invite_title", "join_title",
                                   "no_old_name_in_visible_html", "manifest_icons_unchanged"])
def test_n02_static_names(check):
    """§8: installed-app name (manifest name / short_name, apple-mobile-web-app-title) is 'Lonely Planner'; the /invite/ +
    /join/ <title> carry it; no old name inside <title>, apple title or manifest of any of the three pages."""
    if check == "manifest_icons_unchanged":
        # replaces the icons part of F02 test_ac15_static[manifest_visible_fields_unchanged] (deselected by run.sh 1.2.0:
        # §8 renames name/short_name on purpose)
        man = json.loads((APP_DIR / "manifest.json").read_text(encoding="utf-8"))
        base = f02.BASELINE_DIR / "manifest.json"
        if not base.is_file():
            pytest.skip("v2.15.2 baseline not available (BASELINE_DIR)")
        assert man.get("icons") == json.loads(base.read_text(encoding="utf-8")).get("icons"), "manifest icons changed"
    elif check.startswith("manifest_"):
        man = json.loads((APP_DIR / "manifest.json").read_text(encoding="utf-8"))
        k = check[len("manifest_"):]
        assert man.get(k) == APP_NAME, "manifest %s = %r" % (k, man.get(k))
    elif check == "apple_title":
        assert _meta(app_html(), "apple-mobile-web-app-title") == APP_NAME, "apple-mobile-web-app-title = %r" % _meta(app_html(), "apple-mobile-web-app-title")
    elif check in ("invite_title", "join_title"):
        html = (REPO_DIR / check.split("_")[0] / "index.html").read_text(encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        # §8 renames the /invite/ and /join/ titles; only the app <title> must be exactly the name (test_c21_static)
        assert m and APP_NAME in m.group(1) and not any(n in m.group(1) for n in OLD_NAMES), \
            "%s <title> = %r" % (check.split("_")[0], m and m.group(1))
    else:
        bad = []
        for f in (APP_DIR / "index.html", REPO_DIR / "invite" / "index.html", REPO_DIR / "join" / "index.html"):
            h = f.read_text(encoding="utf-8")
            vis = [(re.search(r"<title>(.*?)</title>", h, re.S) or [None, ""])[1], _meta(h, "apple-mobile-web-app-title") or "",
                   _meta(h, "application-name") or ""]
            bad += ["%s: %r" % (f.parent.name, v) for v in vis if any(n in v for n in OLD_NAMES + ["ויאטנם 2026"])]
        man = (APP_DIR / "manifest.json").read_text(encoding="utf-8")
        mj = json.loads(man)
        bad += ["manifest %s: %r" % (k, mj.get(k)) for k in ("name", "short_name", "description")
                if any(n in str(mj.get(k) or "") for n in OLD_NAMES)]
        assert not bad, "old name in a displayed field: %r" % bad


@pytest.mark.parametrize("where", ["done", "card", "sheet"])
def test_n03_whatsapp_text_name_and_url(env, where):
    """§8 + §8.1: the WhatsApp join message says '…ב-Lonely Planner 🧳' and carries https://orsela.github.io/Lonely_Planner/
    join/#code=<CODE> (Done, the first-steps card, the עוד sheet); never the old name or path."""
    if where == "done":
        dev, iid, token = to_step3(env)
        create_and_done(dev)
        code = env.backend.rows["trip_join_codes"][(env.backend.trips_created[0],)]["code"]
    else:
        tid, code, dev = boot_trip(env, role="manager", n_days=3)
        assert wait_has(dev.page, TXT["first_steps"], 6), "first-steps card missing"
        if where == "sheet":
            f03.open_more(dev.page)
            click_text(dev.page, TXT["more_row"])
            dev.page.wait_for_timeout(800)
    w = wa_url(dev) or ""
    msg = wa_text(w)
    P = []
    if not w.startswith("https://wa.me/?text="):
        P.append("WhatsApp target %r" % w)
    if "ב-" + APP_NAME + " 🧳" not in msg:
        P.append("message lacks 'ב-%s 🧳': %r" % (APP_NAME, msg))
    if JOIN_BASE + "#code=" + code not in msg:
        P.append("message lacks %s#code=%s: %r" % (JOIN_BASE, code, msg))
    if any(n in msg for n in OLD_NAMES):
        P.append("old name/path in the message: %r" % msg)
    assert not P, "\n".join(P)


REDIRECT_DIR = REPO_DIR / "ops" / "old_address_redirect"
NEW_BASE = "https://orsela.github.io/Lonely_Planner/"
LANDED_HTML = b"<!doctype html><meta charset=utf-8><title>landed</title><script>window.__landed=location.href</script>"


def serve_old_address(env):
    """The redirect repo at the OLD path: /Plan_Travel/{,index.html,app/,invite/,join/} from ops/old_address_redirect;
    GitHub Pages answers any other path with 404.html — emulated for the paths the tests open."""
    o = env.server.overrides
    for sub in ("", "app/", "invite/", "join/"):
        b = (REDIRECT_DIR / sub / "index.html").read_bytes()
        o["/Plan_Travel/" + sub] = b
        o["/Plan_Travel/" + sub + "index.html"] = b
    for unknown in ("/Plan_Travel/foo", "/Plan_Travel/foo/bar.html", "/Plan_Travel/app/old-page"):
        o[unknown] = (REDIRECT_DIR / "404.html").read_bytes()


def intercept_new_address(dev, real_invite=False):
    """https://orsela.github.io/Lonely_Planner/** → a stub that records location.href (hash included), or the real local
    /invite/ page. Registered after Env's catch-all route, so it takes precedence."""
    hits = []

    def h(route, request):
        hits.append(request.url)
        if real_invite and "/Lonely_Planner/invite/" in request.url and request.resource_type == "document":
            return route.fulfill(status=200, content_type="text/html; charset=utf-8",
                                 body=(REPO_DIR / "invite" / "index.html").read_bytes())
        if request.resource_type == "document":
            return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=LANDED_HTML)
        return route.abort()
    dev.ctx.route("https://orsela.github.io/**", h)
    return hits


REDIRECTS = [
    ("/Plan_Travel/invite/#invite=TOKEN43abc", NEW_BASE + "invite/#invite=TOKEN43abc"),
    ("/Plan_Travel/app/?invite=1#invite=XYZ", NEW_BASE + "app/?invite=1#invite=XYZ"),
    ("/Plan_Travel/join/#code=ABC23456", NEW_BASE + "join/#code=ABC23456"),
    ("/Plan_Travel/join/?x=1#code=ABC23456", NEW_BASE + "join/?x=1#code=ABC23456"),
    ("/Plan_Travel/", NEW_BASE + "app/"),
    ("/Plan_Travel/index.html#admin", NEW_BASE + "app/#admin"),
    ("/Plan_Travel/foo", NEW_BASE + "app/"),
    ("/Plan_Travel/foo/bar.html?a=b#c", NEW_BASE + "app/?a=b#c"),
]


@pytest.mark.parametrize("old,new", REDIRECTS, ids=[o for o, _ in REDIRECTS])
def test_n04_old_address_redirects(env, old, new):
    """§8.1 + ops/old_address_redirect: every old-path page forwards with location.replace() to the same sub-path under
    https://orsela.github.io/Lonely_Planner/, keeping ?query and #hash; unknown old paths (404.html) → the app; the
    redirect page itself is not left in history (replace)."""
    serve_old_address(env)
    dev = env.new_device("R")
    intercept_new_address(dev)
    page = dev.page
    page.goto(env.server.origin + f02.BLANK_PATH)
    page.goto(env.server.origin + old, wait_until="domcontentloaded")
    end = time.time() + 6
    landed = None
    while time.time() < end and not landed:
        try:
            landed = page.evaluate("()=>window.__landed||null")
        except PWError:
            pass
        page.wait_for_timeout(150)
    assert landed == new, "%s landed on %r, expected %r" % (old, landed or page.url, new)
    page.go_back(wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    assert page.url.startswith(env.server.origin + f02.BLANK_PATH), \
        "Back from the new address went to %r, not the page before the old link (location.replace expected)" % page.url


def test_n04_old_invite_link_end_to_end(env):
    """§8.1: an invite link already sent (old /Plan_Travel/invite/#invite=<token>) reaches the real /invite/ page under
    /Lonely_Planner/, which validates the token ('ההזמנה שלך אומתה') and links on into the app; old page has the brand."""
    serve_old_address(env)
    be = env.backend
    iid, token = be.add_invite(INVITE_EMAIL, DRAFT, sent_days_ago=0, expires_in_days=7, inviter="אור")
    dev = env.new_device("R")
    intercept_new_address(dev, real_invite=True)
    page = dev.page
    page.goto(env.server.origin + "/Plan_Travel/invite/#invite=" + token, wait_until="domcontentloaded")
    P = []
    if not wait_has(page, TXT["inv_ok"], 10):
        P.append("valid invite page not reached via the old link (url=%s, text=%r)" % (page.url, btext(page)[:200]))
    if not page.url.startswith(NEW_BASE + "invite/"):
        P.append("not on the new address: %s" % page.url)
    if not any(r.get("action") == "fn" for r in env.net):
        P.append("invite-manager check not called from the new address")
    hits, _ = old_name_hits(page)
    if hits:
        P.append("old name on the invite page: %r" % hits)
    old_html = (REDIRECT_DIR / "invite" / "index.html").read_text(encoding="utf-8")
    if APP_NAME not in old_html or "location.replace" not in old_html:
        P.append("old-address page lacks the brand or location.replace")
    assert not P, "\n".join(P)
