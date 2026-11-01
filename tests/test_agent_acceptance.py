#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automated Acceptance Test Suite for Question 4: Short-Video Script Agent.
Runnable via standard library `python3 -m unittest discover -s tests -v` or `pytest`.
Covers all 6 mandatory boundaries and audit checkpoints specified in the exam.
"""

import json
import os
import unittest

from src.agent import ShortVideoScriptReActAgent

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


class TestShortVideoScriptAgentAcceptance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(DATA_DIR, "briefs.json"), "r", encoding="utf-8") as f:
            items = json.load(f)
        cls.briefs_map = {b["brief_id"]: b for b in items}
        cls.agent = ShortVideoScriptReActAgent(data_dir=DATA_DIR)

    def test_01_br1_overlong_and_compliance_refinement_loop(self):
        """Verify BR1: Initial draft is 48.0s & has banned/hallucinated words -> Agent revises and re-verifies to 25-35s & PASSED."""
        res = self.agent.run(self.briefs_map["BR1"])
        self.assertEqual(res.status, "completed")
        self.assertTrue(res.duration_check_passed)
        self.assertGreaterEqual(res.estimated_total_duration_sec, 25.0)
        self.assertLessEqual(res.estimated_total_duration_sec, 35.0)
        self.assertEqual(res.compliance_status, "PASSED")
        self.assertIn("PRD-PET-01", res.cited_doc_ids)

        duration_calls = [t for t in res.execution_trace if t["tool_name"] == "estimate_script_duration"]
        compliance_calls = [t for t in res.execution_trace if t["tool_name"] == "check_script_compliance"]
        self.assertEqual(len(duration_calls), 2, "Must call estimate_script_duration on both Draft v1 and revised Draft v2")
        self.assertEqual(len(compliance_calls), 2, "Must call check_script_compliance on both Draft v1 and revised Draft v2")
        self.assertIn("48.0s", duration_calls[0]["observation_summary"])
        self.assertIn("passed=False", compliance_calls[0]["observation_summary"])
        self.assertIn("passed=True", compliance_calls[1]["observation_summary"])

        delivered_text = res.title + " " + " ".join(s["voiceover"] + " " + s["subtitle"] for s in res.shots)
        self.assertNotIn("100%治愈", delivered_text)
        self.assertNotIn("静音提升50%", delivered_text)
        self.assertTrue("二十八分贝" in delivered_text or "28dB" in delivered_text)

    def test_02_br2_missing_facts_supplementary_search_and_refusal(self):
        """Verify BR2: When brief demands unsupported claims (UV sterilization, 50% quieter), Agent checks FAQ-PET-02 and refuses fabrication."""
        res = self.agent.run(self.briefs_map["BR2"])
        self.assertEqual(res.status, "rejected_missing_facts")
        self.assertEqual(len(res.shots), 0)
        self.assertIn("PRD-PET-01", res.searched_doc_scope)
        self.assertIn("FAQ-PET-02", res.searched_doc_scope)
        self.assertIsNotNone(res.rejection_or_incomplete_reason)
        self.assertIn("拒绝编造", res.rejection_or_incomplete_reason)

    def test_03_br3_tool_timeout_recovery_and_fallback(self):
        """Verify BR3: When remote compliance tool raises timeout error, Agent catches it and retries with local rule engine."""
        res = self.agent.run(self.briefs_map["BR3"])
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.compliance_status, "PASSED")
        error_steps = [t for t in res.execution_trace if "ERROR" in t["action"]]
        self.assertEqual(len(error_steps), 1)
        self.assertIn("504 Gateway Timeout", error_steps[0]["observation_summary"])

        fallback_steps = [
            t for t in res.execution_trace
            if t["tool_name"] == "check_script_compliance" and t["tool_params"].get("use_local_fallback") is True
        ]
        self.assertGreaterEqual(len(fallback_steps), 1)

    def test_04_br4_step_limit_circuit_breaker(self):
        """Verify BR4: When max_steps/max_tool_calls is reached before re-verification completes, Agent returns incomplete_step_limit."""
        res = self.agent.run(self.briefs_map["BR4"])
        self.assertEqual(res.status, "incomplete_step_limit")
        self.assertEqual(res.steps_executed, 5)
        self.assertEqual(res.max_steps_limit, 5)
        self.assertFalse(res.duration_check_passed)
        self.assertEqual(res.compliance_status, "UNVERIFIED_AT_STEP_LIMIT")
        self.assertIn("已触发安全步数/工具调用上限", res.rejection_or_incomplete_reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
