"""Tests for the connector's own logic. Run: python -m unittest discover -s tests -v   (from the repository root, with the package installed)."""

import json
import os
import tempfile
import unittest

from kaldrix_connect import core, proof, state

NOW = 1_790_000_000_000

# The bytes the agent signs for one payment, as made by the reference implementation that the Kaldrix service accepts. If this ever changes,
# the connector has stopped speaking the published proof format.
VECTOR = (
    "00000000000000146b616c647269782e746f6b656e2e7573652e763200000000000000116361705f6465765f746573745f30303031000000000000001865633635633837393865636639353930323431336334"
    "306600000000000000117061796d656e74732e696e69746961746500000000000000207061796d656e74733a726563697069656e743a6465765f746573742d61636d65010000000000000010737570706c696572"
    "5f7061796d656e7401000000000000000355534400000000000138800000000000000010000102030405060708090a0b0c0d0e0f000001a0c4506c00"
)


def token(agent_pub="aa" * 32, recipients=("dev_x-acme",), purpose="supplier_payment", per=100_000, total=300_000, approval=50_000, expires=NOW + 3_600_000, not_before=NOW - 1_000):
    spend = {"currency": "USD", "max_minor": per}
    if total is not None:
        spend["max_total_minor"] = total
    if approval is not None:
        spend["approval_above_minor"] = approval
    scope = {"actions": ["payments.initiate"], "resources": [{"exact": f"payments:recipient:{r}"} for r in recipients], "purpose": purpose, "expires_at_ms": expires, "not_before_ms": not_before, "spend": spend}
    return {"id": "cap_dev_x_1", "issuer": "i", "version": 1, "blocks": [{"grant": {"subject": "my-agent", "subject_key": agent_pub, "scope": scope}, "signature": "cd" * 64}]}


class Proof(unittest.TestCase):
    def test_the_proof_message_is_exactly_the_published_one(self):
        t = {"id": "cap_dev_test_0001", "blocks": [{"signature": "ab" * 64}]}
        msg = proof.proof_message(t, "payments:recipient:dev_test-acme", "supplier_payment", 80000, "USD", bytes(range(16)), 1_790_000_000_000)
        self.assertEqual(msg.hex(), VECTOR)

    def test_a_proof_is_signed_by_the_agent_and_differs_each_time(self):
        key = proof.key_from_seed(proof.new_seed_hex())
        t = token(proof.public_hex(key))
        a = proof.sign_proof(key, t, "dev_x-acme", "supplier_payment", 30_000, now_ms=NOW)
        b = proof.sign_proof(key, t, "dev_x-acme", "supplier_payment", 30_000, now_ms=NOW)
        self.assertNotEqual(a["nonce"], b["nonce"])
        # the signature verifies against the agent's public key, for exactly this payment
        msg = proof.proof_message(t, "payments:recipient:dev_x-acme", "supplier_payment", 30_000, "USD", bytes.fromhex(a["nonce"]), a["issued_at_ms"])
        key.public_key().verify(bytes.fromhex(a["signature"]), msg)
        other = proof.proof_message(t, "payments:recipient:dev_x-acme", "supplier_payment", 90_000, "USD", bytes.fromhex(a["nonce"]), a["issued_at_ms"])
        with self.assertRaises(Exception):
            key.public_key().verify(bytes.fromhex(a["signature"]), other)  # a proof for N300 does not pay N900


class Money(unittest.TestCase):
    def test_amounts_are_exact_and_never_rounded(self):
        self.assertEqual(core.to_minor(300), 30_000)
        self.assertEqual(core.to_minor(1234.56), 123_456)
        for bad in (0, -5, 0.001, 10.005, "abc", None, float("nan")):
            self.assertIsNone(core.to_minor(bad), bad)
        self.assertEqual(core.naira(123_456), "N1,234.56")


class Choosing(unittest.TestCase):
    def test_the_first_permission_that_fits_is_used(self):
        me = "aa" * 32
        t = token(me)
        got, why = core.choose([t], me, "dev_x-acme", "supplier_payment", 30_000, NOW)
        self.assertIs(got, t)
        self.assertEqual(why, [])

    def test_each_reason_a_permission_does_not_fit_is_named(self):
        me = "aa" * 32
        cases = {
            "different agent key": (token("bb" * 32), "dev_x-acme", "supplier_payment", 30_000),
            "has expired": (token(me, expires=NOW - 1), "dev_x-acme", "supplier_payment", 30_000),
            "has not started": (token(me, not_before=NOW + 5_000), "dev_x-acme", "supplier_payment", 30_000),
            "does not name that supplier": (token(me), "dev_x-other", "supplier_payment", 30_000),
            "is for supplier_payment, not payroll": (token(me), "dev_x-acme", "payroll", 30_000),
            "allows at most N1,000.00 a payment": (token(me), "dev_x-acme", "supplier_payment", 100_001),
        }
        for expected, (t, recipient, purpose, amount) in cases.items():
            got, why = core.choose([t], me, recipient, purpose, amount, NOW)
            self.assertIsNone(got, expected)
            self.assertIn(expected, why[0])

    def test_describe_reads_the_permission_in_plain_words(self):
        d = core.describe(token("aa" * 32), NOW)
        self.assertEqual((d["may_pay"], d["purpose"], d["most_per_payment"], d["most_in_all"], d["a_person_must_approve_above"], d["expired"]), (["dev_x-acme"], "supplier_payment", "N1,000.00", "N3,000.00", "N500.00", False))
        self.assertTrue(core.describe(token("aa" * 32, expires=NOW - 1), NOW)["expired"])


class Identity(unittest.TestCase):
    def test_the_same_payment_has_the_same_number_and_a_different_one_does_not(self):
        a = core.payment_number("dev_x-acme", 30_000, "supplier_payment", "inv-1")
        self.assertEqual(a, core.payment_number("dev_x-acme", 30_000, "supplier_payment", "inv-1"))
        self.assertNotEqual(a, core.payment_number("dev_x-acme", 30_001, "supplier_payment", "inv-1"))
        self.assertNotEqual(a, core.payment_number("dev_x-acme", 30_000, "supplier_payment", "inv-2"))


class Answers(unittest.TestCase):
    def tx(self, state_, replay=False):
        return {"stage": "payment_submitted", "payment": {"replay": replay, "transaction": {"id": "txn_1", "state": state_, "amount_minor": 30_000, "reject_code": None, "detail": None}}}

    def test_a_payment_is_reported_honestly(self):
        ok = core.summarise(201, self.tx("successful"))
        self.assertEqual((ok["paid"], ok["state"], ok["amount"], ok["money_moved"]), (True, "successful", "N300.00", False))
        self.assertIn("pretend", ok["note"])
        self.assertFalse(core.summarise(200, self.tx("successful", replay=True))["paid"], "a repeat is not paid again")
        self.assertFalse(core.summarise(201, self.tx("rejected"))["paid"])

    def test_refusals_and_waiting_say_what_to_do(self):
        denied = core.summarise(403, {"stage": "authorization_denied", "authorization": {"reason_code": "authorization_amount", "detail": "the request is for more"}})
        self.assertEqual((denied["paid"], denied["decided_by"], denied["reason"]), (False, "Kaldrix", "authorization_amount"))
        self.assertIn("Do not try to get around it", denied["tell_the_user"])
        wait = core.summarise(202, {"stage": "approval_required", "approval_id": "apr_1", "message": "waiting"})
        self.assertEqual((wait["paid"], wait["reason"], wait["approval_id"]), (False, "approval_required", "apr_1"))
        self.assertIn("SAME invoice reference", wait["tell_the_user"])
        down = core.summarise(0, {"error": {"code": "unreachable", "message": "could not reach"}})
        self.assertEqual((down["paid"], down["reason"]), (False, "unreachable"))


class Keeping(unittest.TestCase):
    def test_the_agents_key_is_made_once_and_kept_and_permissions_are_stored_once(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["KALDRIX_HOME"] = d
            try:
                first = state.agent_seed()
                self.assertEqual(first, state.agent_seed(), "the same key every time")
                self.assertEqual(len(first), 64)
                t = token(proof.public_hex(state.agent_key()))
                state.add_permission(t)
                state.add_permission(t)
                self.assertEqual(len(state.permissions()), 1, "storing the same permission twice keeps one")
                self.assertTrue(os.path.exists(os.path.join(d, "connector.json")))
                self.assertNotIn("permissions_secret", json.dumps(state.load()))
            finally:
                del os.environ["KALDRIX_HOME"]


class Clock(unittest.TestCase):
    def test_the_services_clock_is_used_so_a_slow_computer_does_not_make_a_fresh_permission_look_not_started(self):
        import email.utils
        import http.server
        import threading
        import time

        ahead_ms = 120_000  # the service's clock is two minutes ahead of this computer's

        class H(http.server.BaseHTTPRequestHandler):
            def date_time_string(self, timestamp=None):  # the server adds this header itself; make it run ahead
                return email.utils.formatdate((time.time() * 1000 + ahead_ms) / 1000, usegmt=True)

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            core._clock.update({"checked_at": 0, "offset_ms": 0})
            now = core.server_now_ms(f"http://127.0.0.1:{srv.server_address[1]}")
            self.assertAlmostEqual(now - int(time.time() * 1000), ahead_ms, delta=3_000, msg="it reads the service's time")
            # A permission the service issued one second ago starts at the service's now. By this computer's slow clock it would be in the future.
            me = "aa" * 32
            issued_at = now - 1_000
            t = token(me, not_before=issued_at, expires=issued_at + 3_600_000)
            local_slow = int(time.time() * 1000)
            got_by_local, _ = core.choose([t], me, "dev_x-acme", "supplier_payment", 30_000, local_slow)
            self.assertIsNone(got_by_local, "by the slow local clock it looks not started: the bug")
            got, why = core.choose([t], me, "dev_x-acme", "supplier_payment", 30_000, now)
            self.assertIs(got, t, why)
        finally:
            srv.shutdown()
            core._clock.update({"checked_at": 0, "offset_ms": 0})

    def test_an_unreachable_service_leaves_the_computers_own_clock_in_use(self):
        import time

        core._clock.update({"checked_at": 0, "offset_ms": 0})
        now = core.server_now_ms("http://127.0.0.1:9")  # nothing listens here
        self.assertAlmostEqual(now, int(time.time() * 1000), delta=2_000)
        core._clock.update({"checked_at": 0, "offset_ms": 0})


if __name__ == "__main__":
    unittest.main()
