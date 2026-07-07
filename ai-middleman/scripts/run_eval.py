"""
run_eval.py — Labeled evaluation harness for the AI Middleman pipeline.

Runs four independent checks against tests/eval_set.json:
  1. Intent classification accuracy/precision/recall (direct, no side effects —
     calls IntentClassifier in-process, never touches WhatsApp).
  2. Matching relevance (calls the local API's POST /match, which also has no
     side effects — no WhatsApp send, no thread_events written).
  3. Follow-up selection (pure function, no LLM/API/quota) — checks that
     _resolve_selected_contacts picks the right people from the last draft's
     suggestions given a natural follow-up.
  4. Language guard (pure function, no LLM/API/quota) — checks that
     _looks_nguni_not_afrikaans catches real isiZulu without false-positiving
     on real Afrikaans or English.

Requires the local API to be running on localhost:8000 (for the matching
half only — intent classification and follow-up selection don't need it).

Usage:
    python scripts/run_eval.py
"""

import asyncio
import io
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from app.services.intent_classifier import (
    IntentClassifier,
    IntentClassificationError,
    _looks_nguni_not_afrikaans,
)
from app.routes.friend import _resolve_selected_contacts

EVAL_SET_PATH = Path(__file__).parent.parent / "tests" / "eval_set.json"
REPORT_PATH = Path(__file__).parent.parent / "tests" / "eval_report.md"
API_BASE = "http://localhost:8000"


async def run_intent_eval(cases: list) -> dict:
    print("=" * 70)
    print("INTENT CLASSIFICATION")
    print("=" * 70)
    classifier = IntentClassifier()

    tp = fp = tn = fn = errors = 0
    rows = []
    for case in cases:
        text, expected = case["text"], case["expected"]
        try:
            actual = (await classifier.classify(text))["is_request"]
        except IntentClassificationError as e:
            errors += 1
            rows.append((text, expected, None, f"ERROR: {e}"))
            print(f"  [ERR ] {text!r} -> classifier unreachable: {e}")
            continue

        correct = actual == expected
        if expected and actual:
            tp += 1
        elif not expected and not actual:
            tn += 1
        elif not expected and actual:
            fp += 1
        else:
            fn += 1

        mark = "PASS" if correct else "FAIL"
        rows.append((text, expected, actual, mark))
        print(f"  [{mark}] expected={expected!s:<5} got={actual!s:<5} — {text!r}")

    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else float("nan")

    print()
    print(f"  Accuracy:  {accuracy:.1%}  ({tp + tn}/{total} correct, {errors} unreachable)")
    print(f"  Precision: {precision:.1%}  (of messages flagged as requests, how many really were)")
    print(f"  Recall:    {recall:.1%}  (of real requests, how many were caught)")
    print(f"  F1:        {f1:.1%}")

    return {
        "rows": rows, "tp": tp, "fp": fp, "tn": tn, "fn": fn, "errors": errors,
        "accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1,
    }


async def run_matching_eval(cases: list) -> dict:
    print()
    print("=" * 70)
    print("MATCHING RELEVANCE")
    print("=" * 70)

    passed = 0
    rows = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for case in cases:
            query = case["query"]
            try:
                resp = await client.post(f"{API_BASE}/match", json={"query": query})
                data = resp.json()
            except httpx.HTTPError as e:
                rows.append((query, None, None, f"ERROR: {e}"))
                print(f"  [ERR ] {query!r} -> API unreachable: {e}")
                continue

            matches = data.get("matches", [])
            top = matches[0] if matches else None

            # Note: /match doesn't return a sector field, so expected_sector in
            # eval_set.json is documentation/context only — pass/fail here is
            # based on location/company, the fields actually present.
            ok = True
            reasons = []
            expected_loc = case.get("expected_location_contains")
            if expected_loc is not None:
                found = bool(top) and expected_loc.lower() in (top.get("location") or "").lower()
                ok = ok and found
                if not found:
                    reasons.append(f"expected location containing {expected_loc!r}")
            elif expected_loc is None and "expected_location_contains" in case:
                # Deliberately-impossible case: correct behavior is a low-confidence
                # match or no match, NOT a confident hit — a hallucination check.
                found = (not top) or top.get("confidence", 1.0) < 0.5
                ok = found
                if not found:
                    reasons.append("expected a low-confidence/no match (this location isn't in the dataset) but got a confident hit — possible hallucination")
            expected_company = case.get("expected_company_contains")
            if expected_company is not None:
                found = bool(top) and expected_company.lower() in (top.get("company") or "").lower()
                ok = ok and found
                if not found:
                    reasons.append(f"expected company containing {expected_company!r}")

            mark = "PASS" if ok else "FAIL"
            passed += ok
            top_desc = f"{top['name']} ({top.get('company','')}, {top.get('location','')}) conf={top.get('confidence')}" if top else "no match"
            rows.append((query, top_desc, mark, "; ".join(reasons)))
            print(f"  [{mark}] {query!r}")
            print(f"         -> {top_desc}" + (f"  [{'; '.join(reasons)}]" if reasons else ""))

    total = len(cases)
    print()
    print(f"  Relevance rate: {passed}/{total} ({passed/total:.1%})")
    return {"rows": rows, "passed": passed, "total": total}


def run_followup_eval(section: dict) -> dict:
    print()
    print("=" * 70)
    print("FOLLOW-UP SELECTION (no LLM/API — pure resolver)")
    print("=" * 70)

    # Rebuild the "last suggested matches" the resolver would see.
    suggested = [{"contact_id": i + 1, "name": n} for i, n in enumerate(section["suggested"])]
    print(f"  Suggested: {', '.join(section['suggested'])}")
    print()

    passed = 0
    rows = []
    for case in section["cases"]:
        text, expected = case["text"], sorted(case["expected"])
        got = sorted(m.get("name", "") for m in _resolve_selected_contacts(text, suggested))
        ok = got == expected
        passed += ok
        mark = "PASS" if ok else "FAIL"
        rows.append((text, expected, got, mark))
        print(f"  [{mark}] {text!r}")
        if not ok:
            print(f"         expected {expected}, got {got}")

    total = len(section["cases"])
    print()
    print(f"  Selection accuracy: {passed}/{total} ({passed/total:.1%})")
    return {"rows": rows, "passed": passed, "total": total}


async def run_update_intent_eval(cases: list) -> dict:
    print()
    print("=" * 70)
    print("UPDATE INTENT DETECTION")
    print("=" * 70)

    classifier = IntentClassifier()
    passed = errors = 0
    rows = []
    for case in cases:
        text = case["text"]
        expected_is_update = case["expected_is_update"]
        expected_attribute = case.get("expected_attribute")
        expected_contact = case.get("expected_contact", "__absent__")
        try:
            result = await classifier.classify(text)
        except IntentClassificationError as e:
            errors += 1
            rows.append((text, expected_is_update, None, None, f"ERROR: {e}"))
            print(f"  [ERR ] {text!r} -> classifier unreachable: {e}")
            continue

        got_is_update = result.get("is_update", False)
        update_target = result.get("update_target") or {}
        got_attribute = update_target.get("attribute")
        got_contact = update_target.get("contact_name")

        ok = got_is_update == expected_is_update
        attr_ok = True
        if expected_is_update and expected_attribute:
            attr_ok = (got_attribute or "").lower() == expected_attribute.lower()
            ok = ok and attr_ok

        mark = "PASS" if ok else "FAIL"
        passed += ok
        rows.append((text, expected_is_update, got_is_update, got_attribute, mark))
        detail = f"attribute={got_attribute!r}" if got_is_update else ""
        contact_detail = f" contact={got_contact!r}" if got_is_update else ""
        print(f"  [{mark}] expected_update={expected_is_update!s:<5} got={got_is_update!s:<5}  {detail}{contact_detail} — {text!r}")
        if not attr_ok:
            print(f"         attribute mismatch: expected={expected_attribute!r} got={got_attribute!r}")

    total = len(cases)
    print()
    print(f"  Update detection accuracy: {passed}/{total} ({passed/total:.1%}){' (' + str(errors) + ' errors)' if errors else ''}")
    return {"rows": rows, "passed": passed, "total": total, "errors": errors}


async def run_named_contact_eval(cases: list) -> dict:
    print()
    print("=" * 70)
    print("NAMED CONTACT DETECTION")
    print("=" * 70)

    classifier = IntentClassifier()
    passed = errors = 0
    rows = []
    for case in cases:
        text = case["text"]
        expected = case["expected_named_contact"]
        try:
            result = await classifier.classify(text)
        except IntentClassificationError as e:
            errors += 1
            rows.append((text, expected, None, f"ERROR: {e}"))
            print(f"  [ERR ] {text!r} -> classifier unreachable: {e}")
            continue

        got = result.get("named_contact")
        # Loose match: if a name is expected, just check something was extracted
        # containing at least the first token (model wording/casing may vary
        # slightly) — not an exact-string requirement.
        if expected is None:
            ok = got is None
        else:
            first_token = expected.split()[0].lower()
            ok = bool(got) and first_token in got.lower()

        mark = "PASS" if ok else "FAIL"
        passed += ok
        rows.append((text, expected, got, mark))
        print(f"  [{mark}] expected={expected!r:<20} got={got!r:<20} — {text!r}")

    total = len(cases)
    print()
    print(f"  Named-contact accuracy: {passed}/{total} ({passed/total:.1%}){' (' + str(errors) + ' errors)' if errors else ''}")
    return {"rows": rows, "passed": passed, "total": total, "errors": errors}


def run_language_guard_eval(cases: list) -> dict:
    print()
    print("=" * 70)
    print("LANGUAGE GUARD (no LLM/API — pure Nguni-marker check)")
    print("=" * 70)

    passed = 0
    rows = []
    for case in cases:
        text, expected = case["text"], case["expected"]
        got = _looks_nguni_not_afrikaans(text)
        ok = got == expected
        passed += ok
        mark = "PASS" if ok else "FAIL"
        rows.append((text, expected, got, mark))
        print(f"  [{mark}] expected={expected!s:<5} got={got!s:<5} — {text!r}")

    total = len(cases)
    print()
    print(f"  Guard accuracy: {passed}/{total} ({passed/total:.1%})")
    return {"rows": rows, "passed": passed, "total": total}


def write_report(intent_result: dict, matching_result: dict, followup_result: dict, language_guard_result: dict):
    lines = ["# AI Middleman — Evaluation Report", ""]
    lines.append("## Intent classification")
    lines.append(f"- Accuracy: {intent_result['accuracy']:.1%}")
    lines.append(f"- Precision: {intent_result['precision']:.1%}")
    lines.append(f"- Recall: {intent_result['recall']:.1%}")
    lines.append(f"- F1: {intent_result['f1']:.1%}")
    lines.append(f"- Confusion: TP={intent_result['tp']} FP={intent_result['fp']} TN={intent_result['tn']} FN={intent_result['fn']} (errors={intent_result['errors']})")
    lines.append("")
    lines.append("| Expected | Actual | Result | Message |")
    lines.append("|---|---|---|---|")
    for text, expected, actual, mark in intent_result["rows"]:
        lines.append(f"| {expected} | {actual} | {mark} | {text} |")
    lines.append("")
    lines.append("## Matching relevance")
    lines.append(f"- Relevance rate: {matching_result['passed']}/{matching_result['total']} ({matching_result['passed']/matching_result['total']:.1%})")
    lines.append("")
    lines.append("| Query | Top match | Result | Notes |")
    lines.append("|---|---|---|---|")
    for query, top_desc, mark, reasons in matching_result["rows"]:
        lines.append(f"| {query} | {top_desc} | {mark} | {reasons} |")
    lines.append("")
    lines.append("## Follow-up selection")
    lines.append(f"- Selection accuracy: {followup_result['passed']}/{followup_result['total']} ({followup_result['passed']/followup_result['total']:.1%})")
    lines.append("")
    lines.append("| Follow-up | Expected | Got | Result |")
    lines.append("|---|---|---|---|")
    for text, expected, got, mark in followup_result["rows"]:
        lines.append(f"| {text} | {expected or '(none)'} | {got or '(none)'} | {mark} |")
    lines.append("")
    lines.append("## Language guard")
    lines.append(f"- Guard accuracy: {language_guard_result['passed']}/{language_guard_result['total']} ({language_guard_result['passed']/language_guard_result['total']:.1%})")
    lines.append("")
    lines.append("| Message | Expected (is Nguni) | Got | Result |")
    lines.append("|---|---|---|---|")
    for text, expected, got, mark in language_guard_result["rows"]:
        lines.append(f"| {text} | {expected} | {got} | {mark} |")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


async def main():
    eval_set = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))

    intent_result = await run_intent_eval(eval_set["intent"])
    matching_result = await run_matching_eval(eval_set["matching"])
    followup_result = run_followup_eval(eval_set["followup"])
    language_guard_result = run_language_guard_eval(eval_set["language_guard"]["cases"])
    update_result = await run_update_intent_eval(eval_set["update_intent"]["cases"])
    named_contact_result = await run_named_contact_eval(eval_set["named_contact_intent"]["cases"])

    write_report(intent_result, matching_result, followup_result, language_guard_result)
    print()
    print(f"Full report written to {REPORT_PATH}")
    print()
    print("=" * 70)
    print(f"SUMMARY")
    print("=" * 70)
    print(f"  Intent classification:  {intent_result['accuracy']:.0%}")
    print(f"  Matching relevance:     {matching_result['passed']}/{matching_result['total']} ({matching_result['passed']/matching_result['total']:.0%})")
    print(f"  Follow-up selection:    {followup_result['passed']}/{followup_result['total']} ({followup_result['passed']/followup_result['total']:.0%})")
    print(f"  Language guard:         {language_guard_result['passed']}/{language_guard_result['total']} ({language_guard_result['passed']/language_guard_result['total']:.0%})")
    print(f"  Update detection:       {update_result['passed']}/{update_result['total']} ({update_result['passed']/update_result['total']:.0%})")
    print(f"  Named contact:          {named_contact_result['passed']}/{named_contact_result['total']} ({named_contact_result['passed']/named_contact_result['total']:.0%})")


if __name__ == "__main__":
    asyncio.run(main())
