#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Domain tools for product retrieval, duration estimation, and compliance verification."""

import json
import os
import re
from typing import Dict, Any, List


class ToolExecutionError(Exception):
    """Raised when a tool encounters a simulated or real runtime failure."""
    pass


class ScriptAgentToolbox:
    """Provides deterministic domain tools and fault-injection hooks for testing."""

    def __init__(self, data_dir: str, simulate_compliance_timeout_once: bool = False):
        self.data_dir = data_dir
        with open(os.path.join(data_dir, "product_docs.json"), "r", encoding="utf-8") as f:
            self.product_docs: List[Dict[str, Any]] = json.load(f)
        with open(os.path.join(data_dir, "compliance_rules.json"), "r", encoding="utf-8") as f:
            self.rules: Dict[str, Any] = json.load(f)

        self._compliance_timeout_pending = simulate_compliance_timeout_once

    def search_product_docs(self, query: str, category_filter: str = "") -> Dict[str, Any]:
        """Search product documentation and creative specifications by keyword."""
        keywords = [k.strip() for k in re.split(r"[\s,，+]+", query) if k.strip()]
        matched = []
        for doc in self.product_docs:
            if category_filter and category_filter not in doc["category"]:
                continue
            haystack = f"{doc['doc_id']} {doc['title']} {doc['summary']} {' '.join(doc['facts'])} {doc['unsupported_claims_notice']}"
            score = sum(1 for kw in keywords if kw.lower() in haystack.lower())
            if score > 0 or not keywords:
                matched.append({
                    "doc_id": doc["doc_id"],
                    "title": doc["title"],
                    "version": doc["version"],
                    "category": doc["category"],
                    "summary": doc["summary"],
                    "match_score": score
                })
        matched.sort(key=lambda x: x["match_score"], reverse=True)
        return {
            "query": query,
            "matched_count": len(matched),
            "results": matched,
            "all_available_doc_ids": [d["doc_id"] for d in self.product_docs]
        }

    def get_doc_detail(self, doc_ids: List[str]) -> Dict[str, Any]:
        """Fetch full factual details and boundary notices for specific document IDs."""
        found = {}
        missing = []
        for did in doc_ids:
            match = next((d for d in self.product_docs if d["doc_id"] == did), None)
            if match:
                found[did] = {
                    "doc_id": match["doc_id"],
                    "title": match["title"],
                    "version": match["version"],
                    "facts": match["facts"],
                    "unsupported_claims_notice": match["unsupported_claims_notice"]
                }
            else:
                missing.append(did)
        return {
            "requested_doc_ids": doc_ids,
            "documents": found,
            "missing_doc_ids": missing
        }

    def verify_mandatory_claims_support(self, required_claims: List[str]) -> Dict[str, Any]:
        """Verify whether user-mandated claims are supported or explicitly refuted by product docs."""
        all_facts_text = " ".join(" ".join(d["facts"]) for d in self.product_docs)
        unsupported = []
        supported = []
        for claim in required_claims:
            for hp in self.rules["hallucination_patterns"]:
                if hp["pattern"].lower() in claim.lower():
                    unsupported.append({
                        "claim": claim,
                        "violated_pattern": hp["pattern"],
                        "reason": hp["reason"],
                        "checked_docs": [d["doc_id"] for d in self.product_docs]
                    })
                    break
            else:
                if any(k in all_facts_text for k in ["304", "过滤", "28dB", "断电", "2.5L"]):
                    supported.append(claim)
        return {
            "is_fully_supported": len(unsupported) == 0,
            "supported_claims": supported,
            "unsupported_claims": unsupported,
            "checked_doc_scope": [d["doc_id"] for d in self.product_docs]
        }

    def estimate_script_duration(self, shots: List[Dict[str, Any]], target_duration_sec: float = 30.0,
                                 min_sec: float = 25.0, max_sec: float = 35.0) -> Dict[str, Any]:
        """
        Calculate spoken duration of each shot based on Chinese character count (4.0 chars/sec)
        plus 0.5s camera cut transition buffer per shot.
        """
        rate = self.rules.get("speech_rate_chars_per_sec", 4.0)
        buffer_sec = self.rules.get("shot_transition_buffer_sec", 0.5)
        shot_breakdown = []
        total_sec = 0.0

        for s in shots:
            vo = s.get("voiceover", "")
            clean_chars = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", vo)
            char_count = len(clean_chars)
            est_sec = round(char_count / rate + buffer_sec, 1)
            total_sec += est_sec
            shot_breakdown.append({
                "shot_id": s.get("shot_id"),
                "char_count": char_count,
                "estimated_sec": est_sec
            })

        total_sec = round(total_sec, 1)
        in_range = (min_sec <= total_sec <= max_sec)
        diff_sec = round(total_sec - target_duration_sec, 1)
        char_budget_min = int((min_sec - len(shots) * buffer_sec) * rate)
        char_budget_max = int((max_sec - len(shots) * buffer_sec) * rate)

        return {
            "estimated_total_duration_sec": total_sec,
            "target_duration_sec": target_duration_sec,
            "allowed_range_sec": [min_sec, max_sec],
            "within_target_range": in_range,
            "over_or_under_sec": diff_sec,
            "recommended_total_char_range": [char_budget_min, char_budget_max],
            "shot_breakdown": shot_breakdown,
            "adjustment_advice": (
                "时长合格，无需调整。" if in_range else
                f"当前总时长 {total_sec}s 超出上限 {max_sec}s（超出 {round(total_sec - max_sec, 1)}s），请删减旁白字数至 {char_budget_min}~{char_budget_max} 字以内并重新调用本工具复检。"
                if total_sec > max_sec else
                f"当前总时长 {total_sec}s 低于下限 {min_sec}s，请扩充细节至 {char_budget_min}~{char_budget_max} 字。"
            )
        }

    def check_script_compliance(self, title: str, shots: List[Dict[str, Any]],
                                use_local_fallback: bool = False) -> Dict[str, Any]:
        """
        Check script title, voiceover, and subtitles against advertising banned words (RULE-AD-01)
        and product fact hallucination patterns (PRD-PET-01 / FAQ-PET-02).
        """
        if self._compliance_timeout_pending and not use_local_fallback:
            self._compliance_timeout_pending = False
            raise ToolExecutionError(
                "RemoteComplianceServiceTimeout: HTTP 504 Gateway Timeout when connecting to remote ad-audit endpoint. "
                "Hint: Retry check_script_compliance with use_local_fallback=True to invoke local rule engine RULE-AD-01."
            )

        banned_hits = []
        hallucination_hits = []
        full_text_blocks = [("title", 0, title)]
        for s in shots:
            sid = s.get("shot_id", 0)
            full_text_blocks.append(("voiceover", sid, s.get("voiceover", "")))
            full_text_blocks.append(("subtitle", sid, s.get("subtitle", "")))

        for field_name, sid, text in full_text_blocks:
            for bw in self.rules["banned_words"]:
                if bw["word"].lower() in text.lower():
                    banned_hits.append({
                        "shot_id": sid,
                        "field": field_name,
                        "word": bw["word"],
                        "category": bw["category"],
                        "suggested_replacement": bw["replacement"]
                    })
            for hp in self.rules["hallucination_patterns"]:
                if hp["pattern"].lower() in text.lower():
                    hallucination_hits.append({
                        "shot_id": sid,
                        "field": field_name,
                        "unverified_claim": hp["pattern"],
                        "reason": hp["reason"]
                    })

        passed = (len(banned_hits) == 0 and len(hallucination_hits) == 0)
        return {
            "compliance_passed": passed,
            "engine_mode": "local_rule_engine_fallback (RULE-AD-01)" if use_local_fallback else "remote_compliance_service",
            "rule_doc_id": self.rules["rule_doc_id"],
            "banned_word_violations": banned_hits,
            "fact_hallucination_violations": hallucination_hits,
            "remediation_instruction": (
                "合规与事实核查通过（PASSED）。" if passed else
                "核查未通过（FAILED）：请根据 banned_word_violations 替换违禁词，并移除 fact_hallucination_violations 中无资料依据的虚构参数，修改后必须再次调用本工具复检！"
            )
        }
