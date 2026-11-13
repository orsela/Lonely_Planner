"""Lonely Planner F23 · wizard calendar opens on the requested month (F23-WZ-01) · version 1.0.0
CHANGE 2026-11-13 F23-QA-11: new file (no previous version).

A native date picker cannot be inspected from a test, so the test records what the picker is OPENED with: showPicker() is
replaced by a recorder that stores the field's value at the moment of the call (a native picker opens on that value).
Checks: a tap on the empty "יציאה" field opens the picker on the 1st of the requested month and the field is empty again
afterwards (nothing pre-chosen); the form still has no start date; a picked date works as before; "חזרה" after "יציאה"
is left to the native min; without a requested month nothing is intercepted.
Run: tests/f23/run.sh --only app
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "f21"))
sys.path.insert(0, str(HERE.parent))
import test_f21 as t21  # noqa: E402
from test_f21 import browser, env, server  # noqa: E402,F401  (pytest fixtures)

f04 = t21.f04

SPY = """()=>{window.__picker=[];HTMLInputElement.prototype.showPicker=function(){window.__picker.push({id:this.id,value:this.value})}}"""


def test_f23_wizard_calendar_opens_on_requested_month(env):
    be = env.backend
    _, token = t21._approved_invite(be)          # request month 2027-04
    dev = t21.wizard_step1(env, token)
    page = dev.page
    page.evaluate(SPY)
    a, b = f04.dates(page)
    P = []
    a.click()
    page.wait_for_timeout(300)
    calls = page.evaluate("()=>window.__picker")
    if calls != [{"id": "ptWzFrom", "value": "2027-04-01"}]:
        P.append("start picker must open on 2027-04-01: %r" % calls)
    if a.input_value() != "":
        P.append("start field must be empty again after the picker opened: %r" % a.input_value())
    if not t21.has(page, "בבקשה: אפריל 2027"):
        P.append("help line gone although no date was picked")
    b.click()                                    # end date while start is empty → requested month too
    page.wait_for_timeout(300)
    calls = page.evaluate("()=>window.__picker")
    if calls[-1:] != [{"id": "ptWzTo", "value": "2027-04-01"}] or b.input_value() != "":
        P.append("end picker (start empty) must open on 2027-04-01 and stay empty: %r / %r" % (calls[-1:], b.input_value()))
    f04.press_next(page)
    page.wait_for_timeout(400)
    if f04.wait_screen(page, "step1", 2) != "step1" or not t21.has(page, "צריך לבחור תאריך יציאה."):
        P.append("an untouched start date must still be required")
    a.fill("2027-04-03")                         # a real pick
    page.wait_for_timeout(200)
    n = len(page.evaluate("()=>window.__picker"))
    a.click()
    b.click()                                    # start chosen → end has min → not intercepted
    page.wait_for_timeout(300)
    if len(page.evaluate("()=>window.__picker")) != n:
        P.append("fields with a value / a min must not be intercepted")
    if a.input_value() != "2027-04-03" or b.get_attribute("min") != "2027-04-03":
        P.append("picked start date / end min changed: %r %r" % (a.input_value(), b.get_attribute("min")))
    b.fill("2027-04-20")
    f04.press_next(page)
    if f04.wait_screen(page, "step2") != "step2":
        P.append("step 2 not reached with picked dates")
    assert not P, "; ".join(P)


def test_f23_wizard_calendar_untouched_without_requested_month(env):
    be = env.backend
    _, token = t21._approved_invite(be, month=None)
    dev = t21.wizard_step1(env, token)
    page = dev.page
    page.evaluate(SPY)
    a, _b = f04.dates(page)
    a.click()
    page.wait_for_timeout(300)
    assert page.evaluate("()=>window.__picker") == [], "no requested month → the native behaviour, no interception"
    assert a.input_value() == ""
