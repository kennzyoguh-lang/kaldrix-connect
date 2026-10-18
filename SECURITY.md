# Security

## What this connector holds, and what it can do

* **Its own signing key**, made on first use and kept in `~/.kaldrix/connector.json` (or `KALDRIX_HOME`). It never leaves your computer; only signatures go out. Anyone who can read that file can make this agent sign, so keep it private like any key.
* **The permissions you gave it.** A permission is not a secret: it is useless without the matching private key.
* **A limited agent key** (`KALDRIX_AGENT_KEY`). It can pay and read payments, nothing else: it can not make suppliers or permissions, approve or refuse a payment, cancel a permission, or make or read other keys. That is enforced by the Kaldrix service, not by this program.

So even a fully hijacked assistant is bounded: it can only pay what a permission you signed allows, each payment needs its own signed proof, a big payment waits for you, and you can cancel the permission or switch the key off at any moment.

**Never give the assistant your own account key.** That key can approve payments and make permissions.

## Reporting a problem

Tell us privately through the **Report a vulnerability** button on the Security tab of github.com/kennzyoguh-lang/kaldrix-connect (a private report that only we can see). Please give us a reasonable time to fix it before you tell anyone else. You may test the security of your own test account within the limits of the testing agreement.

This is a test service and a first version. It has had no independent security review.
