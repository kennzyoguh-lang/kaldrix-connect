# Kaldrix and Zentrix connector

**Agentic authorization, security and payments.** Let your AI assistant pay suppliers, inside limits you signed.

An AI agent that can spend money is only safe if the limit lives *outside* the agent. If the limit is just a rule in its prompt, one clever message can talk it out of the rule. Kaldrix puts the limit in a **signed permission**, and the payment desk checks that signature again at the moment of paying.

> **You tell the assistant: "this supplier, this much, until this time." A big payment waits for you. Even if the assistant is tricked or hijacked, the money does not move past what you signed.**

## What you get

| | |
|---|---|
| **Kaldrix** (the permission) | A signed, limited permission: who may be paid, how much per payment and in all, for what purpose, until when. It can only be narrowed when passed on, never widened. You can cancel it at any moment. |
| **Zentrix** (the conditional escrow and execution clearinghouse) | Moves money only when the agent proves it stayed inside its exact instructions. It checks Kaldrix's yes again on its own, applies its own limits, never pays the same invoice twice, tells the truth when the bank has not answered ("unknown", never a guess), and returns a **signed proof envelope** with every payment: who held the permission, the exact amount, supplier and purpose, and the time limits. |
| **This connector** | Lets Claude, Cursor, Copilot, Codex and other MCP assistants use both. The assistant holds its own key; only signatures leave your computer. |

## How this is different

* **The proof is tied to the payment.** Each payment needs its own signature over the exact amount, supplier and currency. A proof made for $200 cannot be stretched to pay $450.
* **The assistant cannot grant itself anything.** Its key can pay and read payments, nothing else: no new suppliers, no new permissions, no approving its own payment. The service enforces that, not this program.
* **Humans stay in the loop where it matters.** Above an amount you choose, a named person (or two) must approve that exact payment.
* **Built for places where banks are slow and unreliable.** Zentrix is designed first for emerging markets (Nigeria first): it will not pay twice when a bank times out, and it fails over to another provider only when it is certain nothing was sent.

You can see all of this yourself in the test service: press **Run the demo for me** and an agent gets a limit, pays, tries to cheat (every attempt is refused with a plain reason), and waits for you to approve a big payment. Product site and a 3-minute video: https://kennzyoguh-lang.github.io/kaldrix-zentrix/ . Built by [Oguh Chidiebube Kenneth](https://kennzyoguh-lang.github.io/).

**What is built and what is not:** the signed limits, approvals, two-step checks and the proof envelope work in the test service. A locked escrow vault for multi-step tasks, M-Pesa and PIX settlement, and integrations with open agent-payment protocols are designed or planned, not built. No partnership with any company is claimed.

> **This is a test service. It is a pretend bank: no real money moves.** It is a first version with no independent security review. Read [SECURITY.md](SECURITY.md).

Works with assistants that speak [MCP](https://modelcontextprotocol.io): Claude (Code and Desktop), Cursor, GitHub Copilot in VS Code, Codex and others. ChatGPT needs a hosted connector, which is not built yet.

## Work with us

Building agents that touch money, or running a payments, banking or AI platform? We want to hear what would make this safe enough for you. Open an issue on this repository titled **"Let's talk"** and say who you are and what you are building.

## Try it in five minutes

1. **Make a test account** at **https://kaldrix-sandbox.onrender.com** (read and accept the testing agreement; save the key it shows once). Add a supplier.
2. In the dashboard, open **5. Connect your own AI assistant** and **make a key for my AI assistant**. This key can only pay and read payments. Save it.
3. **Install the connector** (below) with that key.
4. Ask your assistant: **"Who am I with Kaldrix?"** It makes its own signing key and tells you its public key.
5. In the dashboard, step 3 → *Use my own agent's key instead* → paste that public key → give it a permission. **Copy the permission** that appears and give it to your assistant ("add this permission"). Nothing about it is secret: it is useless without the assistant's private key.
6. Ask it to pay a supplier. A payment above your approval amount waits in the dashboard's **Waiting for you** box. Approve it, then ask again.

## Install

You need [`uv`](https://docs.astral.sh/uv/) (it runs the connector straight from this repository). Replace `kz_YOUR_AGENT_KEY` with the key from step 2.

**Claude Code** (as a plugin, with the skill and the `/kaldrix-start` command):

```
/plugin marketplace add kennzyoguh-lang/kaldrix-connect
/plugin install kaldrix@kaldrix
```

Set `KALDRIX_AGENT_KEY` in your environment first. Or add only the connector:

```
claude mcp add kaldrix -e KALDRIX_AGENT_KEY=kz_YOUR_AGENT_KEY -- uvx --from git+https://github.com/kennzyoguh-lang/kaldrix-connect kaldrix-connect
```

**Other assistants** use the same three pieces: the command `uvx`, the arguments `--from git+https://github.com/kennzyoguh-lang/kaldrix-connect kaldrix-connect`, and the environment setting `KALDRIX_AGENT_KEY`. See [docs/INSTALL.md](docs/INSTALL.md) for Claude Desktop, Cursor, VS Code (Copilot) and Codex.

## What the assistant can do

| Tool | What it does |
|---|---|
| `kaldrix_who_am_i` | Start here: the agent's public key, what is ready, what to do next |
| `kaldrix_add_permission` | Store a permission you gave it (only if it was made for this agent) |
| `kaldrix_permissions` | What it may pay, how much, until when |
| `kaldrix_suppliers` | Who can be paid |
| `kaldrix_pay` | Pay inside a permission: Kaldrix decides, Zentrix checks again and pays; a refusal comes back as plain words |
| `kaldrix_payment_status`, `kaldrix_payments` | Where payments stand |
| `kaldrix_query` | Read or change rows in the person's database through the data gateway, inside a **purpose-bound, time-bound data permission**: the gateway checks every table, column and row the statement touches. Today it serves a built-in demo database only |

## Database access (new)

A data permission says which tables, operations, columns or rows an agent may touch, **for what purpose**, and for **how long** (5 seconds to 24 hours). A request for payroll, a join to a table it was not given, a `DROP TABLE`, or the right query after the time has run out is refused, and the database sees nothing. The agent signs a proof for each exact statement, so a proof for one statement cannot be used for another. Try it with `tests/e2e_data_gateway.py`. The gateway serves one pretend database; it is not connected to any real one. Details: the Kaldrix docs, `docs/api/data-gateway.md`.

## What it can never do

Make suppliers or permissions, approve or refuse a payment, cancel a permission, or make or read other keys. The Kaldrix service enforces this, not this program.

## Settings

| Setting | What it is |
|---|---|
| `KALDRIX_AGENT_KEY` | The limited key you made in step 2 |
| `KALDRIX_URL` | The service address (default: the public test service) |
| `KALDRIX_HOME` | Where the agent's own key and permissions are kept (default `~/.kaldrix`) |

## Rights

All rights reserved. You may read this and use it with the Kaldrix service; see [NOTICE.md](NOTICE.md). It is not open source.

<!-- mcp-name: io.github.kennzyoguh-lang/kaldrix-connect -->
