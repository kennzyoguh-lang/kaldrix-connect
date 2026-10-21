"""The connector's decisions, as plain functions: which permission fits a payment, what a permission allows, and what an answer from
the platform means in plain words. No network and no MCP here, so each can be tested on its own."""

import email.utils
import hashlib
import json
import time
import urllib.error
import urllib.request

DEFAULT_URL = "https://kaldrix-sandbox.onrender.com"

# This computer's clock against the service's. A permission starts and ends by the service's clock, and a proof carries a time the service
# must accept, so the connector uses the service's time, not this computer's: a clock that is a little slow or fast must not make a fresh
# permission look "not started" or a proof look stale.
_clock = {"checked_at": 0, "offset_ms": 0}
CLOCK_RECHECK_MS = 5 * 60 * 1000
START_GRACE_MS = 2_000  # the service's time is read to the second, so a permission that starts this instant is not "not started"


def server_now_ms(base: str) -> int:
    local = int(time.time() * 1000)
    if local - _clock["checked_at"] > CLOCK_RECHECK_MS:
        _clock["checked_at"] = local
        try:
            req = urllib.request.Request(base.rstrip("/") + "/api/health", headers={"User-Agent": "kaldrix-connect/0.1"})
            with urllib.request.urlopen(req, timeout=15) as r:
                date = r.headers.get("Date")
        except urllib.error.HTTPError as e:  # even an error answer carries the time
            date = e.headers.get("Date")
        except (urllib.error.URLError, TimeoutError, OSError):
            date = None
        if date:
            try:
                _clock["offset_ms"] = int(email.utils.parsedate_to_datetime(date).timestamp() * 1000) - local
            except (TypeError, ValueError):
                pass
    return int(time.time() * 1000) + _clock["offset_ms"]  # read now, after any network call above


def dollars(minor) -> str:
    return "$" + format(int(minor) / 100, ",.2f")


def to_minor(amount_dollars):
    """Dollars to cents, only if it is a positive amount with at most two decimal places; otherwise None. Money is never rounded."""
    try:
        minor = round(float(amount_dollars) * 100)
    except (TypeError, ValueError):
        return None
    if minor <= 0 or abs(float(amount_dollars) * 100 - minor) > 1e-6:
        return None
    return minor


def leaf(token: dict) -> dict:
    return token["blocks"][-1]["grant"]


def holder_key(token: dict) -> str:
    return leaf(token)["subject_key"]


def describe(token: dict, now_ms=None) -> dict:
    """What a permission allows, in words, read from the permission itself."""
    now = int(time.time() * 1000) if now_ms is None else now_ms
    g = leaf(token)
    sc = g["scope"]
    spend = sc.get("spend") or {}
    resources = [r.get("exact") or (r.get("prefix", "") + "*") for r in sc.get("resources", [])]
    out = {
        "permission_id": token["id"],
        "for_agent": g["subject"],
        "may_pay": [r.replace("payments:recipient:", "") for r in resources],
        "purpose": sc.get("purpose"),
        "most_per_payment": dollars(spend["max_minor"]) if "max_minor" in spend else None,
        "most_in_all": dollars(spend["max_total_minor"]) if spend.get("max_total_minor") is not None else None,
        "a_person_must_approve_above": dollars(spend["approval_above_minor"]) if spend.get("approval_above_minor") is not None else None,
        "valid_until_ms": sc.get("expires_at_ms"),
        "expired": sc.get("expires_at_ms") is not None and sc["expires_at_ms"] <= now,
        "not_started": sc.get("not_before_ms") is not None and sc["not_before_ms"] > now + START_GRACE_MS,
    }
    return out


def names(sc: dict, recipient_id: str) -> bool:
    for r in sc.get("resources", []):
        if r.get("exact") == f"payments:recipient:{recipient_id}":
            return True
        if "prefix" in r and f"payments:recipient:{recipient_id}".startswith(r["prefix"]):
            return True
    return False


def choose(tokens: list, my_public_hex: str, recipient_id: str, purpose: str, amount_minor: int, now_ms=None):
    """The first permission this agent holds that fits this payment, or (None, why not) for each one it holds."""
    now = int(time.time() * 1000) if now_ms is None else now_ms
    why = []
    for t in tokens:
        g, sc = leaf(t), leaf(t)["scope"]
        if g["subject_key"] != my_public_hex:
            why.append(f"{t['id']}: was made for a different agent key")
        elif sc.get("expires_at_ms") is not None and sc["expires_at_ms"] <= now:
            why.append(f"{t['id']}: has expired")
        elif sc.get("not_before_ms") is not None and sc["not_before_ms"] > now + START_GRACE_MS:
            why.append(f"{t['id']}: has not started yet")
        elif not names(sc, recipient_id):
            why.append(f"{t['id']}: does not name that supplier")
        elif sc.get("purpose") is not None and sc["purpose"] != purpose:
            why.append(f"{t['id']}: is for {sc['purpose']}, not {purpose}")
        elif (sc.get("spend") or {}).get("max_minor") is not None and amount_minor > sc["spend"]["max_minor"]:
            why.append(f"{t['id']}: allows at most {dollars(sc['spend']['max_minor'])} a payment")
        else:
            return t, []
    return None, why


def payment_number(recipient: str, amount_minor: int, purpose: str, reference: str) -> str:
    """The payment's identity. The same supplier, amount, purpose and invoice is the same payment, never two, and a retry after a
    person approves is recognised as the payment that was waiting."""
    return "inv-" + hashlib.sha256(f"{recipient}|{amount_minor}|{purpose}|{reference}".encode()).hexdigest()[:24]


def summarise(status: int, body: dict) -> dict:
    """What the assistant is told after a payment attempt: plain data about what was decided, by whom and why."""
    body = body or {}
    stage = body.get("stage")
    if stage == "authorization_denied":
        a = body.get("authorization") or {}
        return {"paid": False, "decided_by": "Kaldrix", "reason": a.get("reason_code"), "explanation": a.get("detail"), "money_moved": False,
                "tell_the_user": "Kaldrix refused this payment, so it was not made. Do not try to get around it; explain the reason to the person."}
    if stage == "approval_required":
        return {"paid": False, "decided_by": "waiting for a person", "reason": "approval_required", "approval_id": body.get("approval_id"), "money_moved": False,
                "explanation": body.get("message"),
                "tell_the_user": "This payment is above what the permission lets the agent pay alone. Ask the person to approve it in their Kaldrix dashboard (Waiting for you). When they say they have, call kaldrix_pay again with the SAME invoice reference and amount."}
    if stage == "approval_denied":
        return {"paid": False, "decided_by": "a person", "reason": "approval_denied", "approval_id": body.get("approval_id"), "explanation": body.get("reason") or "a person said no", "money_moved": False}
    if stage == "payment_submitted":
        t = body["payment"]["transaction"]
        if body["payment"].get("replay"):
            return {"paid": False, "decided_by": "Zentrix, from its record of the first time", "reason": "replayed", "transaction_id": t["id"], "money_moved": False,
                    "explanation": "this exact payment was already made; nothing was paid again"}
        return {"paid": t["state"] in ("successful", "pending"), "decided_by": "Kaldrix allowed; Zentrix " + ("accepted" if t["state"] != "rejected" else "refused"),
                "transaction_id": t["id"], "state": t["state"], "amount": dollars(t["amount_minor"]), "reason": t.get("reject_code"), "explanation": t.get("detail"),
                "money_moved": False, "note": "This is a pretend bank: no real money moves."}
    err = body.get("error") or {}
    return {"paid": False, "decided_by": "the platform", "reason": err.get("code") or f"http_{status}", "explanation": err.get("message") or json.dumps(body)[:200], "money_moved": False}


def call(base: str, key: str, method: str, path: str, body=None, timeout=60):
    """One call to the platform. Returns (HTTP status, parsed body)."""
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "kaldrix-connect/0.1"}
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"error": {"code": f"http_{e.code}", "message": raw.decode("utf-8", "replace")[:200]}}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"error": {"code": "unreachable", "message": f"could not reach the Kaldrix service: {e}"}}
