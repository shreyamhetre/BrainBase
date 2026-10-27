"""The Jev evidence gate's decisions, with Jev and GPT faked. No database, no network.

Run from the project root: python -m unittest discover -s backend/tests
"""

import unittest
from dataclasses import replace
from unittest import mock

from app import evidence_gate, rag_settings
from app.evidence_gate import Check, gated_retrieve


def run(enough: list[float | None], error: str = "", gate_on: bool = True, key: str = "k"):
    """enough: what Jev says for the first search and the retry (None = Jev failed)."""
    answers = iter(enough)
    searched = []

    def fake_check(question, chunks):
        value = next(answers)
        if value is None:
            return Check(question, sent=[{}], error=error or "Jev unreachable")
        return Check(question, enough=value, passed=value >= 0.5, sent=[{}], input_tokens=100)

    def fake_retrieve(question):
        searched.append(question)
        return [f"chunk for {question}"]

    settings = replace(rag_settings.RagSettings(), gate_enabled=gate_on)
    with mock.patch.object(rag_settings, "get", return_value=settings), \
         mock.patch.object(evidence_gate, "TYPESAFE_API_KEY", key), \
         mock.patch.object(evidence_gate, "check", side_effect=fake_check), \
         mock.patch.object(evidence_gate, "rewrite", return_value=("rewritten", 90, 16)):
        return gated_retrieve(fake_retrieve, "original"), searched, settings


class Gate(unittest.TestCase):
    def test_enough_evidence_answers_from_the_first_search(self):
        result, searched, _ = run([0.97])
        self.assertEqual(result.outcome, "passed")
        self.assertEqual(searched, ["original"])
        self.assertEqual(result.chunks, ["chunk for original"])

    def test_retry_with_rewritten_question_can_pass(self):
        result, searched, _ = run([0.2, 0.8])
        self.assertEqual(result.outcome, "passed_after_retry")
        self.assertEqual(searched, ["original", "rewritten"])
        self.assertEqual(result.chunks, ["chunk for rewritten"])
        self.assertEqual(result.rewrite_tokens, (90, 16))

    def test_two_failures_leave_no_chunks_so_no_answer_call(self):
        result, searched, _ = run([0.03, 0.03])
        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.chunks, [])
        self.assertEqual(result.retrieved, ["chunk for rewritten"])   # still shown in the inspector
        self.assertEqual(len(searched), 2)                            # one retry only

    def test_jev_down_steps_aside(self):
        result, searched, _ = run([None])
        self.assertEqual(result.outcome, "skipped")
        self.assertEqual(result.chunks, ["chunk for original"])

    def test_gate_off_or_no_key(self):
        self.assertEqual(run([], gate_on=False)[0].outcome, "off")
        result = run([], key="")[0]
        self.assertEqual(result.outcome, "skipped")
        self.assertIn("TYPESAFE_API_KEY", result.checks[0].error)

    def test_details_cost_counts_jev_tokens(self):
        result, _, settings = run([0.2, 0.8])
        with mock.patch.object(rag_settings, "get", return_value=settings):
            details = result.details()
        self.assertEqual(details["jev_tokens"], 200)
        self.assertAlmostEqual(details["jev_cost_usd"], 200 * settings.gate_price_per_m / 1_000_000)


class Settings(unittest.TestCase):
    def test_gate_settings_validated(self):
        ok = rag_settings.validate({"gate_enabled": False, "gate_threshold": "0.7", "gate_model": " jev-1.14.0 "}, [])
        self.assertEqual(ok, {"gate_enabled": False, "gate_threshold": 0.7, "gate_model": "jev-1.14.0"})
        for bad in ({"gate_threshold": 0.95}, {"gate_enabled": "yes"}, {"gate_model": ""}):
            with self.assertRaises(rag_settings.SettingsError):
                rag_settings.validate(bad, [])


if __name__ == "__main__":
    unittest.main()
