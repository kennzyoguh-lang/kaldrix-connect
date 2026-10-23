"""The Kaldrix connector: lets an AI assistant (Claude, Copilot, Cursor, Codex and others that speak MCP) pay with a limited permission.

The assistant sees a few ordinary tools. Behind `kaldrix_pay`, this process holds the agent's own key and the permissions it was given,
signs a proof for exactly the payment asked for, and sends it to the Kaldrix service, where Kaldrix decides and Zentrix checks again.
The assistant can not widen its permission, can not approve its own payment, and a refusal comes back as plain data it can explain.

Settings (environment):
  KALDRIX_AGENT_KEY   the limited key you made for your assistant in your Kaldrix dashboard (it can only pay and read payments)
  KALDRIX_URL         the service address (default: the public test service)
  KALDRIX_HOME        where the agent's key and permissions are kept (default: ~/.kaldrix)
"""

import json
import os
import sys

from . import core, proof, state

try:  # the current MCP library, then the earlier one
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # pragma: no cover - depends on the installed library
    from mcp.server.fastmcp import FastMCP as _Server

server = _Server("kaldrix")


def _base() -> str:
    return os.environ.get("KALDRIX_URL", core.DEFAULT_URL).rstrip("/")


def _key() -> str:
    return os.environ.get("KALDRIX_AGENT_KEY", "").strip()


def _no_key() -> str:
    return json.dumps({
        "ok": False,
        "problem": "KALDRIX_AGENT_KEY is not set",
        "how_to_fix": f"In your Kaldrix dashboard ({_base()}), open 'Connect your own AI assistant' and make a key. Put it in the KALDRIX_AGENT_KEY setting of this connector, then restart your assistant.",
    })


def _me() -> str:
    return proof.public_hex(state.agent_key())


@server.tool()
def kaldrix_who_am_i() -> str:
    """Start here. Says which agent key this connector holds, whether it is ready, which permissions it has, and exactly what to do next.
    Use this when the person asks to set up Kaldrix, or when a payment cannot be made."""
    now = core.server_now_ms(_base())
    perms = [core.describe(t, now) for t in state.permissions()]
    ready = bool(_key())
    nxt = []
    if not ready:
        nxt.append("Set KALDRIX_AGENT_KEY (make the key in the dashboard under 'Connect your own AI assistant').")
    if not perms:
        nxt.append(f"Give this agent a permission: in the dashboard ({_base()}), step 3, open \"Use my own agent's key instead\", paste the public key below, and give it a permission. Copy the permission it shows and call kaldrix_add_permission with it.")
    if ready and perms:
        nxt.append("Ready. Call kaldrix_suppliers to see who can be paid, then kaldrix_pay.")
    return json.dumps({"agent_public_key": _me(), "service": _base(), "agent_key_set": ready, "permissions_held": perms, "next": nxt, "this_is": "a pretend bank: no real money moves"}, indent=2)


@server.tool()
def kaldrix_add_permission(permission_json: str) -> str:
    """Store a permission the person gave this agent (the JSON they copied from the dashboard). It is only accepted if it was made for this
    agent's own key. A permission is not a secret: on its own it is useless without this agent's private key."""
    try:
        token = json.loads(permission_json)
        holder = core.holder_key(token)
        _ = token["id"], token["blocks"][-1]["signature"]
    except (ValueError, KeyError, TypeError, IndexError):
        return json.dumps({"ok": False, "problem": "that is not a permission. Copy the whole JSON from the dashboard, starting with { and ending with }."})
    if holder != _me():
        return json.dumps({"ok": False, "problem": "this permission was made for a different agent key.", "this_agent_key_is": _me(), "the_permission_is_for": holder})
    state.add_permission(token)
    return json.dumps({"ok": True, "stored": core.describe(token, core.server_now_ms(_base()))}, indent=2)


@server.tool()
def kaldrix_permissions() -> str:
    """List the permissions this agent holds and what each allows: who it may pay, for what, how much, and until when."""
    now = core.server_now_ms(_base())
    return json.dumps({"agent_public_key": _me(), "permissions": [core.describe(t, now) for t in state.permissions()]}, indent=2)


@server.tool()
def kaldrix_suppliers() -> str:
    """List the suppliers (recipients) that exist on the person's account, with the ids you pass to kaldrix_pay."""
    if not _key():
        return _no_key()
    status, body = core.call(_base(), _key(), "GET", "/api/zentrix/v1/recipients")
    if status != 200:
        return json.dumps(core.summarise(status, body))
    return json.dumps({"suppliers": [{"id": r["id"], "name": r["display_name"], "active": r["active"]} for r in body.get("recipients", [])]}, indent=2)


@server.tool()
def kaldrix_pay(recipient: str, amount_dollars: float, purpose: str, invoice_reference: str) -> str:
    """Pay a supplier in US dollars, using a permission this agent holds. `recipient` is the supplier id (see kaldrix_suppliers), `purpose` says what
    the payment is for (supplier_payment, payroll, refund, utility_bill or tax_payment), `invoice_reference` is the invoice number.
    Returns what was decided and why. A refusal is final for that request: do not try to get around it, explain it to the person.
    If the answer is `approval_required`, a person must approve it first: after they have, call again with the SAME invoice reference and
    amount and it goes through. The same supplier, amount, purpose and invoice is one payment, never two."""
    if not _key():
        return _no_key()
    minor = core.to_minor(amount_dollars)
    if minor is None:
        return json.dumps({"paid": False, "reason": "invalid_amount", "explanation": "the amount must be more than zero and have at most two decimal places", "money_moved": False})
    me = _me()
    now = core.server_now_ms(_base())
    token, why = core.choose(state.permissions(), me, recipient, purpose, minor, now)
    if token is None:
        return json.dumps({
            "paid": False, "reason": "no_matching_permission", "money_moved": False,
            "explanation": "this agent holds no permission that covers this payment, so nothing was sent." if why else "this agent holds no permission yet.",
            "why_each_permission_does_not_fit": why,
            "tell_the_user": "Ask the person to give this agent a permission that covers it (kaldrix_who_am_i says how). Do not ask them for their account key.",
        }, indent=2)
    key = state.agent_key()
    body = {
        "token": token,
        "presenter": core.leaf(token)["subject"],
        "proof": proof.sign_proof(key, token, recipient, purpose, minor, now_ms=now),
        "intent": {"amount_minor": minor, "currency": "USD", "recipient": recipient, "purpose": purpose, "client_reference": invoice_reference, "idempotency_key": core.payment_number(recipient, minor, purpose, invoice_reference)},
    }
    status, resp = core.call(_base(), _key(), "POST", "/api/v1/authorized-payments", body)
    return json.dumps(core.summarise(status, resp), indent=2)


@server.tool()
def kaldrix_query(sql: str, purpose: str) -> str:
    """Read or change rows in the person's database through the Kaldrix data gateway, using a data permission this agent holds. Send ONE statement.
    `purpose` must be exactly the purpose the permission was issued for (for example customer_support). The gateway checks the permission against every
    table, column and row the statement touches, the purpose and the time window, and runs the statement only if all of it is covered. A refusal is
    final for that request: do not try another table or reword the statement to slip past it, explain it to the person. Today the gateway serves a built-in
    demo database only."""
    if not _key():
        return _no_key()
    me = _me()
    now = core.server_now_ms(_base())
    token, why = core.choose_data(state.permissions(), me, purpose, now)
    if token is None:
        return json.dumps({
            "ran": False, "reason": "no_matching_data_permission", "database_saw_nothing": True,
            "why_each_permission_does_not_fit": why,
            "tell_the_user": "Ask the person to give this agent a data permission for this purpose (their dashboard or the data-permissions call), then add it with kaldrix_add_permission. Do not ask them for their account key.",
        }, indent=2)
    key = state.agent_key()
    status, plan = core.call(_base(), _key(), "POST", "/api/v1/data-access/plan", {"database": "demo", "sql": sql})
    if status != 200 or not plan.get("ok"):
        return json.dumps({"ran": False, "reason": (plan or {}).get("refused", "statement_not_allowed"), "explanation": (plan or {}).get("detail"), "database_saw_nothing": True,
                           "tell_the_user": "The statement was refused before any permission was looked at (one statement at a time; no schema changes, grants or unsafe functions)."}, indent=2)
    body = {
        "database": "demo", "sql": sql, "purpose": purpose, "token": token, "presenter": core.leaf(token)["subject"],
        "proof": proof.sign_data_proof(key, token, plan["resource_to_sign"], purpose, now_ms=now),
    }
    status, resp = core.call(_base(), _key(), "POST", "/api/v1/data-access", body)
    return json.dumps(core.summarise(status, resp), indent=2)


@server.tool()
def kaldrix_payment_status(transaction_id: str) -> str:
    """Ask where a payment stands, according to the (pretend) payment provider."""
    if not _key():
        return _no_key()
    status, body = core.call(_base(), _key(), "POST", f"/api/zentrix/v1/payments/{transaction_id}/refresh", {})
    t = (body or {}).get("transaction") or {}
    if status != 200:
        return json.dumps(core.summarise(status, body))
    return json.dumps({"transaction_id": transaction_id, "state": t.get("state"), "amount": core.dollars(t.get("amount_minor", 0)), "provider": t.get("provider")})


@server.tool()
def kaldrix_payments() -> str:
    """List the most recent payments made on the person's account."""
    if not _key():
        return _no_key()
    status, body = core.call(_base(), _key(), "GET", "/api/zentrix/v1/payments?limit=20")
    if status != 200:
        return json.dumps(core.summarise(status, body))
    return json.dumps({"payments": [{"id": t["id"], "state": t["state"], "amount": core.dollars(t["amount_minor"]), "to": t["recipient"], "invoice": t.get("client_reference")} for t in body.get("transactions", [])]}, indent=2)


def main() -> None:
    if "--version" in sys.argv:
        from . import __version__

        print(__version__)
        return
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
