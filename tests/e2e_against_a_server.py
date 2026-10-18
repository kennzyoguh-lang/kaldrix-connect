"""The connector, end to end, through the real MCP protocol, against a running Kaldrix test service.

    python tests/e2e_against_a_server.py https://kaldrix-sandbox.fly.dev

It plays both people: the developer (signs up, makes a supplier, a limited agent key, and a permission) and the AI assistant (the connector,
started the way an assistant would start it, and called over MCP). Every step says what it expected; the exit code is non-zero if anything
differs. Uses a throwaway test account on the service you name. Not part of the unit tests: it needs a server.
"""

import asyncio
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

AGREEMENT = "2026-10-19-draft"
failures = []


def check(label, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{('  (' + detail + ')') if detail else ''}")
    if not ok:
        failures.append(label)


def http(base, method, path, key=None, body=None):
    headers = {"Content-Type": "application/json", "User-Agent": "kaldrix-connect-e2e/1.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


async def tool(session, name, **args):
    result = await session.call_tool(name, args)
    return json.loads(result.content[0].text)


async def main(base):
    base = base.rstrip("/")
    print("The developer, in the dashboard:")
    s, v = http(base, "POST", "/api/sandbox/v1/signup", body={"name": "connector e2e", "accept_terms": True, "terms_version": AGREEMENT})
    check("signs up", s == 201, f"HTTP {s}")
    dev_key = v["api_key"]
    s, v = http(base, "POST", "/api/sandbox/v1/recipients", dev_key, {"label": "acme", "name": "Acme Supplies", "bank_code": "057", "account_last4": "4821"})
    acme = v["recipient"]["id"]
    s, v = http(base, "POST", "/api/sandbox/v1/recipients", dev_key, {"label": "other", "name": "Unlisted Traders", "bank_code": "058", "account_last4": "9902"})
    other = v["recipient"]["id"]
    s, v = http(base, "POST", "/api/sandbox/v1/agent-keys", dev_key, {"label": "e2e assistant"})
    check("makes a limited key for the assistant", s == 201, f"HTTP {s}")
    agent_key = v["agent_key"]

    home = tempfile.mkdtemp(prefix="kaldrix-e2e-")
    params = StdioServerParameters(command=sys.executable, args=["-m", "kaldrix_connect"], env={**os.environ, "KALDRIX_URL": base, "KALDRIX_AGENT_KEY": agent_key, "KALDRIX_HOME": home})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        names = {t.name for t in (await session.list_tools()).tools}
        check("the assistant sees the Kaldrix tools", {"kaldrix_who_am_i", "kaldrix_pay", "kaldrix_add_permission", "kaldrix_suppliers"} <= names, ", ".join(sorted(names)))

        print("The assistant asks who it is:")
        me = await tool(session, "kaldrix_who_am_i")
        check("it has its own public key and no permission yet", len(me["agent_public_key"]) == 64 and me["permissions_held"] == [] and me["agent_key_set"], me["next"][0][:60])
        pay = await tool(session, "kaldrix_pay", recipient=acme, amount_naira=300, purpose="supplier_payment", invoice_reference="inv-1")
        check("with no permission it refuses to even try, and says why", pay["paid"] is False and pay["reason"] == "no_matching_permission")

        print("The developer gives it a permission, and it stores it:")
        s, v = http(base, "POST", "/api/sandbox/v1/permissions", dev_key, {"subject": "claude", "subject_key": me["agent_public_key"], "recipients": ["acme"], "max_per_payment_minor": 100_000, "max_total_minor": 300_000, "approval_above_minor": 50_000})
        check("a permission is issued for the assistant's public key", s == 200, f"HTTP {s}")
        token = v["token"]
        wrong = await tool(session, "kaldrix_add_permission", permission_json="not json")
        check("it refuses something that is not a permission", wrong["ok"] is False)
        added = await tool(session, "kaldrix_add_permission", permission_json=json.dumps(token))
        check("it stores the permission", added["ok"] and added["stored"]["most_per_payment"] == "N1,000.00", json.dumps(added.get("stored", {}).get("may_pay")))
        listed = await tool(session, "kaldrix_suppliers")
        check("it can see the account's suppliers", {x["id"] for x in listed["suppliers"]} == {acme, other})

        print("The assistant does its job, then tries to cheat:")
        ok = await tool(session, "kaldrix_pay", recipient=acme, amount_naira=300, purpose="supplier_payment", invoice_reference="inv-2")
        check("pays N300", ok["paid"] is True and ok["state"] in ("successful", "pending"), f"{ok.get('state')}")
        again = await tool(session, "kaldrix_pay", recipient=acme, amount_naira=300, purpose="supplier_payment", invoice_reference="inv-2")
        check("asking again for the same invoice is the same payment, not a second", again["paid"] is False and again["reason"] == "replayed")
        for label, kwargs in [
            ("more than one payment may be", dict(recipient=acme, amount_naira=1200, purpose="supplier_payment", invoice_reference="inv-3")),
            ("a supplier the permission does not name", dict(recipient=other, amount_naira=100, purpose="supplier_payment", invoice_reference="inv-4")),
            ("a purpose the permission does not allow", dict(recipient=acme, amount_naira=100, purpose="payroll", invoice_reference="inv-5")),
        ]:
            r = await tool(session, "kaldrix_pay", **kwargs)
            check(f"is refused: {label}", r["paid"] is False and r["reason"] == "no_matching_permission", r["why_each_permission_does_not_fit"][0][-40:])
        bad_amount = await tool(session, "kaldrix_pay", recipient=acme, amount_naira=0.001, purpose="supplier_payment", invoice_reference="inv-6")
        check("is refused: an amount that is not whole kobo", bad_amount["reason"] == "invalid_amount")

        print("A big payment waits for the person:")
        held = await tool(session, "kaldrix_pay", recipient=acme, amount_naira=800, purpose="supplier_payment", invoice_reference="inv-7")
        check("the assistant is told a person must approve it", held["paid"] is False and held["reason"] == "approval_required", held.get("decided_by"))
        s, waiting = http(base, "GET", "/api/sandbox/v1/approvals", dev_key)
        approval = next((a for a in waiting["approvals"] if a["status"] == "pending"), None)
        if approval is None:
            print("  (debug) held answer:", json.dumps(held)[:300])
            print("  (debug) approvals the developer sees:", json.dumps(waiting)[:400])
            check("the developer can see the held payment waiting", False)
            return
        s, _ = http(base, "POST", f"/api/sandbox/v1/approvals/{approval['id']}/approve", dev_key, {})
        check("the developer approves that exact payment", s == 200, f"HTTP {s}")
        done = await tool(session, "kaldrix_pay", recipient=acme, amount_naira=800, purpose="supplier_payment", invoice_reference="inv-7")
        check("the assistant asks again and it goes through", done["paid"] is True, f"{done.get('state')}")
        payments = await tool(session, "kaldrix_payments")
        check("it can read the payments", len(payments["payments"]) == 2, f"{len(payments['payments'])} payments")

        print("The person cancels:")
        s, _ = http(base, "POST", f"/api/sandbox/v1/permissions/{token['id']}/revoke", dev_key, {})
        check("the developer cancels the permission", s == 200)
        after = await tool(session, "kaldrix_pay", recipient=acme, amount_naira=100, purpose="supplier_payment", invoice_reference="inv-8")
        check("the assistant can no longer pay with it", after["paid"] is False and after["decided_by"] == "Kaldrix", after.get("reason"))

    print("The limited key really is limited:")
    for method, path, body in [("POST", "/api/sandbox/v1/permissions", {"subject": "x", "subject_key": me["agent_public_key"], "recipients": ["acme"], "max_per_payment_minor": 1000}),
                               ("GET", "/api/sandbox/v1/approvals", None), ("POST", "/api/sandbox/v1/agent-keys", {})]:
        s, _ = http(base, method, path, agent_key, body)
        check(f"the assistant's key is refused: {method} {path}", s == 403, f"HTTP {s}")

    print()
    if failures:
        print(f"{len(failures)} step(s) did not go as expected: {failures}")
        sys.exit(1)
    print("Everything went as expected.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1]))
