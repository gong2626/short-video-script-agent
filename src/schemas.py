#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data schemas for the Short-Video Script ReAct Agent."""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class ShotItem:
    shot_id: int
    visual_description: str
    voiceover: str
    subtitle: str
    estimated_duration_sec: float
    cited_doc_ids: List[str] = field(default_factory=list)


@dataclass
class ScriptDraft:
    version: int
    title: str
    platform: str
    target_audience: str
    style: str
    shots: List[ShotItem]
    cited_doc_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceRecord:
    """Single step in the ReAct execution trace (meets exact submission spec)."""
    step: int
    action: str
    tool_name: Optional[str]
    tool_params: Dict[str, Any]
    observation_summary: str
    subsequent_action: str
    decision_rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentDeliverable:
    """Final structured output of the Short-Video Script Agent."""
    brief_id: str
    status: str  # "completed" | "rejected_missing_facts" | "incomplete_step_limit" | "failed_tool_error"
    title: str
    platform: str
    target_duration_sec: float
    estimated_total_duration_sec: float
    duration_check_passed: bool
    compliance_status: str  # "PASSED" | "FAILED" | "UNVERIFIED"
    cited_doc_ids: List[str]
    shots: List[Dict[str, Any]]
    rejection_or_incomplete_reason: Optional[str]
    searched_doc_scope: List[str]
    steps_executed: int
    tool_calls_count: int
    max_steps_limit: int
    max_tool_calls_limit: int
    execution_trace: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
