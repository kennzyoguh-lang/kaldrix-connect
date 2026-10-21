---
name: kaldrix-pay
description: Use when the person asks you to pay a supplier, set up Kaldrix, or check payments. Pay only through the Kaldrix tools, inside the permission the person signed; never ask for their account key; explain refusals and approvals in plain words.
---

# Paying with Kaldrix

Kaldrix (the signed permission) and Zentrix (the payment desk that checks it again and pays) let you pay suppliers **only inside limits a person signed**. This is a test service: it is a pretend bank and no real money moves.

## Rules you always follow

1. **Pay only with the Kaldrix tools** (`kaldrix_pay`). Never try to pay another way.
2. **A refusal is final for that request.** Do not retry with a different amount, supplier or purpose to get around it, and do not split a payment into smaller ones to stay under a limit. Tell the person what was refused and why, in plain words.
3. **You can not approve your own payment, widen your permission, or cancel anything.** Those belong to the person. Never ask the person for their account key or any other key; you hold only your own limited agent key.
4. **A big payment waits for a person.** If the answer is `approval_required`, say so, ask them to approve it in their Kaldrix dashboard (the "Waiting for you" box), and only after they say they have, call `kaldrix_pay` again with the **same** invoice reference and amount.
5. **Say what happened honestly.** Report what was decided and by whom. Do not say a payment was made unless the answer says it was.

## Starting out

If the person says "set up Kaldrix", or a payment cannot be made, call `kaldrix_who_am_i` and follow its `next` steps with them. In short:

1. They make a limited **agent key** in their dashboard ("Connect your own AI assistant") and give it to this connector (`KALDRIX_AGENT_KEY`).
2. `kaldrix_who_am_i` shows **your public key**. They paste it in the dashboard (step 3, "Use my own agent's key instead") and give you a permission.
3. They copy the permission and you store it with `kaldrix_add_permission`.
4. `kaldrix_suppliers` shows who can be paid. `kaldrix_pay` pays.

## Making a payment

`kaldrix_pay(recipient, amount_dollars, purpose, invoice_reference)`:

- `recipient`: a supplier id from `kaldrix_suppliers`.
- `purpose`: `supplier_payment`, `payroll`, `refund`, `utility_bill` or `tax_payment`. Use the one the permission is for (`kaldrix_permissions` shows it).
- `invoice_reference`: the real invoice number. The same supplier, amount, purpose and invoice is one payment, never two, so retrying after a network error is safe.

After a payment, `kaldrix_payment_status` and `kaldrix_payments` show where it stands.
