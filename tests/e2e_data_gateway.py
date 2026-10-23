"""The connector's database tool, end to end, through the real MCP protocol, against a running Kaldrix test service.

    python tests/e2e_data_gateway.py http://127.0.0.1:8099

The developer signs up, makes a limited key for the assistant and gives it a purpose-bound, time-bound data permission. The assistant (the
connector, started the way an assistant would start it) reads what it was given and is refused everything else. Uses a throwaway test account.
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
    text = result.content[0].text
    try:
        return json.loads(text)
    except ValueError:
        raise SystemExit(f"the tool {name} did not answer with JSON: {text[:400]}")


async def main(base):
    base = base.rstrip("/")
    print("The developer, in the dashboard:")
    s, v = http(base, "POST", "/api/sandbox/v1/signup", body={"name": "data e2e", "accept_terms": True, "terms_version": AGREEMENT})
    check("signs up", s == 201, f"HTTP {s}")
    dev_key = v["api_key"]
    s, v = http(base, "POST", "/api/sandbox/v1/agent-keys", dev_key, {"label": "data e2e assistant"})
    check("makes a limited key for the assistant", s == 201, f"HTTP {s}")
    agent_key = v["agent_key"]
    check("the key can ask to use the data gateway", any("demo database" in x for x in v["it_can"]))

    home = tempfile.mkdtemp(prefix="kaldrix-e2e-data-")
    params = StdioServerParameters(command=sys.executable, args=["-m", "kaldrix_connect"], env={**os.environ, "KALDRIX_URL": base, "KALDRIX_AGENT_KEY": agent_key, "KALDRIX_HOME": home})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        names = {t.name for t in (await session.list_tools()).tools}
        check("the assistant sees the database tool", "kaldrix_query" in names)
        me = await tool(session, "kaldrix_who_am_i")

        print("With no data permission it does not even try:")
        r = await tool(session, "kaldrix_query", sql="SELECT id FROM support_tickets", purpose="customer_support")
        check("it refuses and says why", r["ran"] is False and r["reason"] == "no_matching_data_permission")

        print("The developer gives it a data permission:")
        s, v = http(base, "POST", "/api/sandbox/v1/data-permissions", dev_key, {
            "subject": "claude", "subject_key": me["agent_public_key"], "purpose": "customer_support", "ttl_ms": 600_000,
            "grants": [
                {"table": "support_tickets", "operations": ["read"]},
                {"table": "customers", "operations": ["read"], "columns": ["id", "name", "plan"]},
            ],
        })
        check("it is issued for the assistant's public key", s == 200, f"HTTP {s}")
        token = v["token"]
        added = await tool(session, "kaldrix_add_permission", permission_json=json.dumps(token))
        check("the assistant stores it", added["ok"])

        print("The assistant does its job:")
        ok = await tool(session, "kaldrix_query", sql="SELECT id, subject FROM support_tickets WHERE status = 'open' ORDER BY id", purpose="customer_support")
        check("reads the open tickets", ok["ran"] is True and ok["result"]["row_count"] >= 4, f"{ok['result']['row_count']} rows" if ok.get("ran") else json.dumps(ok)[:200])
        cols = await tool(session, "kaldrix_query", sql="SELECT id, name FROM customers WHERE plan = 'pro'", purpose="customer_support")
        check("reads the columns it was given", cols["ran"] is True)

        print("Then it tries to go where it should not:")
        for label, sql in [
            ("payroll", "SELECT * FROM payroll"),
            ("the financial records", "SELECT * FROM financial_records"),
            ("a column it was not given", "SELECT email FROM customers"),
            ("every column of customers", "SELECT * FROM customers"),
            ("payroll through a join", "SELECT s.subject, p.salary_usd FROM support_tickets s JOIN payroll p ON p.id = s.id"),
            ("payroll through a subquery", "SELECT subject FROM support_tickets WHERE id IN (SELECT id FROM payroll)"),
            ("a change to a table it may only read", "UPDATE support_tickets SET status = 'closed'"),
            ("a deletion", "DELETE FROM support_tickets"),
        ]:
            r = await tool(session, "kaldrix_query", sql=sql, purpose="customer_support")
            check(f"is refused: {label}", r["ran"] is False and r["reason"] == "resource_not_permitted", str(r.get("reason")))
        for label, sql in [("dropping a table", "DROP TABLE payroll"), ("a second statement tucked on the end", "SELECT 1 FROM support_tickets; DROP TABLE payroll")]:
            r = await tool(session, "kaldrix_query", sql=sql, purpose="customer_support")
            check(f"is refused before the permission is even looked at: {label}", r["ran"] is False, str(r.get("reason")))
        wrong = await tool(session, "kaldrix_query", sql="SELECT id FROM support_tickets", purpose="marketing")
        check("a different purpose finds no permission", wrong["ran"] is False and wrong["reason"] == "no_matching_data_permission")

        print("The person cancels:")
        s, _ = http(base, "POST", f"/api/sandbox/v1/permissions/{token['id']}/revoke", dev_key, {})
        check("the developer cancels the permission", s == 200)
        after = await tool(session, "kaldrix_query", sql="SELECT id FROM support_tickets", purpose="customer_support")
        check("the assistant can no longer read", after["ran"] is False and after["reason"] == "revoked", str(after.get("reason")))

    print("The limited key really is limited:")
    s, _ = http(base, "POST", "/api/sandbox/v1/data-permissions", agent_key, {"subject": "x", "subject_key": me["agent_public_key"], "purpose": "p", "grants": [{"table": "payroll", "operations": ["read"]}]})
    check("the assistant's key cannot give itself access", s == 403, f"HTTP {s}")

    print()
    if failures:
        print(f"{len(failures)} step(s) did not go as expected: {failures}")
        sys.exit(1)
    print("Everything went as expected.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1]))
