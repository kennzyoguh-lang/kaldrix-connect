# Kaldrix Connect

**Give your AI assistant a spending limit it cannot argue with.**

[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![MCP](https://img.shields.io/badge/MCP-connector-5B3FD6)

If an agent's spending limit lives in its prompt, one clever message can talk it out of the limit. Kaldrix puts the limit in a **signed permission** that lives outside the assistant and is checked at the moment of paying.

> "This supplier, this much, until this time. Ask me above this amount."
> Your assistant can pay inside that. It cannot widen it, and it cannot approve its own payment.

Works with assistants that speak [MCP](https://modelcontextprotocol.io): Claude (Code and Desktop), Cursor, GitHub Copilot in VS Code, Codex and others.

## What it looks like

Your assistant asks for more than the permission allows. This is the shape of the answer it gets back:

```json
{
  "paid": false,
  "reason": "no_matching_permission",
  "money_moved": false,
  "why_each_permission_does_not_fit": ["cap_...: allows at most $1,000.00 a payment"],
  "tell_the_user": "Ask the person to give this agent a permission that covers it (kaldrix_who_am_i says how). Do not ask them for their account key."
}
```

A payment above your approval amount comes back as `"reason": "approval_required"` and waits for you in the dashboard.

## Try it in five minutes

The hosted service runs in **test mode**: no real money moves, so try hard to break it.

1. **Make a test account** at **https://kaldrix-sandbox.onrender.com** (read and accept the testing agreement and save the key it shows once). Add a supplier.
2. In the dashboard, open **5. Connect your own AI assistant** and make a key for your assistant. This key can only pay and read payments.
3. **Install the connector** (below) with that key.
4. Ask your assistant: **"Who am I with Kaldrix?"** It makes its own signing key and tells you the public half.
5. In the dashboard, step 3, choose *Use my own agent's key instead*, paste that public key and give it a permission. Copy the permission and give it to your assistant. It is not a secret: it is useless without the assistant's private key.
6. Ask it to pay a supplier. Then ask it to cheat.

The service sleeps when idle, so the first request can take up to a minute.

## Install

You need [`uv`](https://docs.astral.sh/uv/). Replace `kz_YOUR_AGENT_KEY` with the key from step 2.

**Claude Code**, as a plugin (adds a skill and the `/kaldrix-start` command; set `KALDRIX_AGENT_KEY` in your environment first):

```
/plugin marketplace add kennzyoguh-lang/kaldrix-connect
/plugin install kaldrix@kaldrix
```

Or only the connector:

```
claude mcp add kaldrix -e KALDRIX_AGENT_KEY=kz_YOUR_AGENT_KEY -- uvx --from git+https://github.com/kennzyoguh-lang/kaldrix-connect kaldrix-connect
```

**Every other assistant** needs the same three things: the command `uvx`, the arguments `--from git+https://github.com/kennzyoguh-lang/kaldrix-connect kaldrix-connect`, and the environment setting `KALDRIX_AGENT_KEY`. Steps for Claude Desktop, Cursor, VS Code (Copilot) and Codex are in [docs/INSTALL.md](docs/INSTALL.md).

## What the assistant can do

| Tool | What it does |
|---|---|
| `kaldrix_who_am_i` | Start here: the agent's public key, what is ready, what to do next |
| `kaldrix_add_permission` | Store a permission you gave it (only if it was made for this agent) |
| `kaldrix_permissions` | What it may pay, how much and until when |
| `kaldrix_suppliers` | Who can be paid |
| `kaldrix_pay` | Pay inside a permission. Refusals come back in plain words |
| `kaldrix_payment_status`, `kaldrix_payments` | Where payments stand |
| `kaldrix_query` | Read or change rows in a demo database inside a purpose bound, time bound data permission |

It can **never** make suppliers or permissions, approve or refuse a payment, cancel a permission, or read other keys. The service enforces this, not this program.

## How it works

| | |
|---|---|
| **Kaldrix**, the permission | Who may be paid, how much per payment and in all, for what, until when. It can only be narrowed when passed on, never widened, and you can cancel it at any moment. |
| **Zentrix**, the payment | Checks the permission again on its own, applies its own limits, does not pay the same invoice twice, answers "unknown" instead of guessing when a bank has not replied, and returns a signed proof envelope. |
| **This connector** | Gives your assistant both. The assistant holds its own signing key and only signatures leave your computer. |

* **The proof is tied to the payment.** A signature made for one amount and supplier cannot be stretched to another.
* **People stay in charge where it matters.** Above an amount you choose, a named person (or two) approves that exact payment.
* **Designed for places where banks can be slow.** Built with Nigeria first in mind.

## Roadmap

* A hosted version of the connector, so assistants that connect over the web (including ChatGPT) can use it
* More payment providers and rails
* Examples for popular agent frameworks

Want one of these sooner? Open an issue.

## Work with us

Building agents that touch money, or running a payments, banking or AI platform? Open an issue titled **"Let's talk"** and say who you are and what you are building.

If this is useful to you, **a star helps other builders find it.**

Built in Lagos by [Oguh Chidiebube Kenneth](https://kaldrix-zentrix-web.vercel.app/oguh). Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: [SECURITY.md](SECURITY.md).

## Licence

The connector is open source under the [Apache License 2.0](LICENSE). The Kaldrix and Zentrix engines and the hosted service are separate and are not part of this repository. See [NOTICE](NOTICE).

<!-- mcp-name: io.github.kennzyoguh-lang/kaldrix-connect -->
