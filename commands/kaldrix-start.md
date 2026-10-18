---
description: Set up Kaldrix so this assistant can pay suppliers inside limits you sign
---

Set me up to pay with Kaldrix, step by step, using the Kaldrix tools.

1. Call `kaldrix_who_am_i`.
2. Tell me, in plain words, what is ready and what is missing, and do only the next missing step with me:
   - If the agent key is not set, tell me how to make one (my dashboard, "Connect your own AI assistant") and where to put it (`KALDRIX_AGENT_KEY`), then that I need to restart this assistant.
   - If I have no permission for you yet, show me your public key and tell me how to give you a permission in my dashboard (step 3, "Use my own agent's key instead"). When I paste the permission JSON, store it with `kaldrix_add_permission`.
   - If everything is ready, call `kaldrix_permissions` and `kaldrix_suppliers` and summarise what you may pay, how much, and until when.
3. Remind me that this is a test service with a pretend bank, and that you can not approve payments or change your limits: only I can.
