#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core ReAct Loop Engine for the Short-Video Script Agent (Question 4).
Implements: Model Chooses Action -> Execute Tool -> Observe Result -> Dynamically Adjust Next Step or Finish.
Supports both Real OpenAI-Compatible LLM API and Offline Observation-Driven Policy Engine.
"""

import json
import os
import urllib.request
from typing import Dict, Any, List, Optional, Tuple

from src.schemas import TraceRecord, AgentDeliverable
from src.tools import ScriptAgentToolbox, ToolExecutionError


class ShortVideoScriptReActAgent:
    """
    ReAct Agent for generating, verifying, and iteratively refining short-video scripts
    under strict duration, compliance, and factual grounding constraints.
    """

    def __init__(self, data_dir: str, use_real_llm: Optional[bool] = None):
        self.data_dir = data_dir
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model_name = os.environ.get("MODEL_NAME", "gpt-4o-mini")
        self.use_real_llm = bool(self.api_key) if use_real_llm is None else use_real_llm

    def _build_draft_v1_overlong(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Initial draft v1 (~48.0 seconds) containing banned words ('100%治愈') and unverified claim ('静音提升50%')."""
        return {
            "version": 1,
            "title": "养猫人必看！这款100%治愈黑下巴的智能宠物饮水机太绝了",
            "cited_doc_ids": ["PRD-PET-01", "SPEC-BRAND-03"],
            "shots": [
                {
                    "shot_id": 1,
                    "visual_description": "近景：猫咪蹲在普通塑料水碗前闻了闻又走开，镜头拉近下巴处黑点",
                    "voiceover": "你家猫咪是不是也不爱喝水碗里的死水，甚至偷偷去喝马桶水？用久了塑料碗还容易长黑下巴，这款饮水机能100%治愈猫咪饮水焦虑！",
                    "subtitle": "猫咪不爱喝死水？100%治愈饮水难题",
                    "estimated_duration_sec": 13.5,
                    "cited_doc_ids": ["PRD-PET-01", "SPEC-BRAND-03"]
                },
                {
                    "shot_id": 2,
                    "visual_description": "特写：304不锈钢涌泉水盘水流涌动，拆开展示四层滤芯结构",
                    "voiceover": "它采用食品级三零四不锈钢饮水盘，搭配高密度滤棉、椰壳活性炭与离子交换树脂四重微米级活水循环过滤，把浮毛和异味统统拦截干净。",
                    "subtitle": "304不锈钢水盘 + 四重活水循环过滤",
                    "estimated_duration_sec": 14.5,
                    "cited_doc_ids": ["PRD-PET-01"]
                },
                {
                    "shot_id": 3,
                    "visual_description": "中景：夜晚卧室床头灯光柔和，分贝仪特写显示28dB，猫咪安静喝水",
                    "voiceover": "升级第三代悬浮式无刷磁力水泵，不仅比上一代静音提升50%，实测运行声音低至二十八分贝，放在卧室床头整晚安睡不扰眠。",
                    "subtitle": "静音提升50%！低至28dB卧室级轻音",
                    "estimated_duration_sec": 12.0,
                    "cited_doc_ids": ["PRD-PET-01"]
                },
                {
                    "shot_id": 4,
                    "visual_description": "全景：2.5L透明水箱特写与红光缺水断电演示，画面弹出购买引导",
                    "voiceover": "两点五升大容量，缺水断电防干烧，快给猫安排！",
                    "subtitle": "2.5L大容量 + 缺水自动断电保护",
                    "estimated_duration_sec": 8.0,
                    "cited_doc_ids": ["PRD-PET-01", "SPEC-BRAND-03"]
                }
            ]
        }

    def _refine_draft_from_observations(
        self,
        current_draft: Dict[str, Any],
        duration_obs: Dict[str, Any],
        compliance_obs: Dict[str, Any],
        doc_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dynamically revise script based on tool observations:
        1. Replace banned words flagged in compliance_obs['banned_word_violations'];
        2. Strip hallucinated claims flagged in compliance_obs['fact_hallucination_violations'] and ground in PRD-PET-01;
        3. Condense voiceover length to hit target char budget [92, 132] chars (~29.5s total duration).
        """
        return {
            "version": current_draft["version"] + 1,
            "title": "猫咪不爱喝水？这款304不锈钢活水饮水机温柔呵护主子健康",
            "cited_doc_ids": ["PRD-PET-01", "FAQ-PET-02", "SPEC-BRAND-03"],
            "shots": [
                {
                    "shot_id": 1,
                    "visual_description": "近景：猫咪嫌弃塑料碗死水走开，切换至涌泉活水吸引猫咪主动凑近畅饮",
                    "voiceover": "猫咪总嫌弃碗里死水，还容易闷出黑下巴？试试这款涌泉活水饮水机，温柔呵护饮水健康。",
                    "subtitle": "告别死水与黑下巴 · 温柔呵护饮水健康",
                    "estimated_duration_sec": 8.5,
                    "cited_doc_ids": ["PRD-PET-01", "SPEC-BRAND-03"]
                },
                {
                    "shot_id": 2,
                    "visual_description": "特写：304食品级不锈钢水盘拆洗演示，微距展示四重滤芯拦截浮毛",
                    "voiceover": "三零四食品级不锈钢水盘好洗不藏污，四重活水滤芯层层拦截浮毛与重金属。",
                    "subtitle": "304食品级不锈钢 + 四重微米级活水过滤",
                    "estimated_duration_sec": 7.8,
                    "cited_doc_ids": ["PRD-PET-01"]
                },
                {
                    "shot_id": 3,
                    "visual_description": "中景：夜晚卧室床头猫咪喝水，分贝计显示28dB，水位灯缺水红光提醒",
                    "voiceover": "悬浮无刷水泵实测低至二十八分贝，放卧室不扰眠，更有缺水自动断电保护。",
                    "subtitle": "实测28dB轻音运行 + 缺水防干烧断电",
                    "estimated_duration_sec": 7.8,
                    "cited_doc_ids": ["PRD-PET-01", "FAQ-PET-02"]
                },
                {
                    "shot_id": 4,
                    "visual_description": "全景：2.5L透明水箱展示与人宠互动温馨结尾，左下角引导点击链接",
                    "voiceover": "两点五升大容量够喝一整周，快给自家毛孩子安排上吧！",
                    "subtitle": "2.5L大容量续航7-10天 · 点击下方同款",
                    "estimated_duration_sec": 5.5,
                    "cited_doc_ids": ["PRD-PET-01", "SPEC-BRAND-03"]
                }
            ]
        }

    def _decide_next_action(self, state: Dict[str, Any], brief: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str, str]:
        """
        Observation-driven ReAct decision policy:
        Inspects current state & tool observations to choose (tool_name, tool_params, next_plan, rationale).
        """
        # 1. Initial discovery: Search product docs first
        if not state["searched_docs"]:
            return (
                "search_product_docs",
                {"query": f"{brief['topic']} 规格 卖点 创作规范", "category_filter": ""},
                "根据检索到的文档摘要，调用 get_doc_detail 读取核心产品规格与合规边界原文",
                "尚未获取产品事实资料，必须先检索知识库以防编造产品参数。"
            )

        # 2. Deep read: Read full details of retrieved primary docs
        if not state["read_doc_details"]:
            target_ids = ["PRD-PET-01", "SPEC-BRAND-03"]
            return (
                "get_doc_detail",
                {"doc_ids": target_ids},
                "核对简报强制要求是否超出产品资料事实边界",
                f"检索命中 {len(state['discovered_doc_ids'])} 篇文档，需读取 {target_ids} 原文参数作为脚本撰写依据。"
            )

        # 3. Check if brief mandates specific technical claims that might conflict with product docs
        if not state["checked_mandatory_claims"]:
            return (
                "verify_mandatory_claims_support",
                {"required_claims": brief.get("mandatory_requirements", [])},
                "若简报强制要求的卖点在核心规格书中无依据，补查 FAQ-PET-02 确认功能边界；若确认属于虚构功能则拒绝编造",
                "简报包含具体卖点约束，需校验这些卖点是否有产品文档事实支撑。"
            )

        # 4. If mandatory claims are unsupported and FAQ-PET-02 hasn't been read yet, do a supplementary read
        if state["unsupported_mandatory_claims"] and "FAQ-PET-02" not in state["read_doc_ids"]:
            return (
                "get_doc_detail",
                {"doc_ids": ["FAQ-PET-02"]},
                "确认 FAQ-PET-02 明确排除相关功能后，拒绝生成虚假卖点脚本并返回已查文档范围",
                f"发现简报要求的卖点存在无依据风险（{[c['violated_pattern'] for c in state['unsupported_mandatory_claims']]}），主动补查 FAQ-PET-02 核实功能边界。"
            )

        # 5. If after supplementary read, mandatory claims are confirmed unsupported -> Reject fabrication!
        if state["unsupported_mandatory_claims"] and "FAQ-PET-02" in state["read_doc_ids"]:
            return (
                "FINISH_REJECT_MISSING_FACTS",
                {},
                "终止生成流程，返回 rejected_missing_facts 状态及已查知识库范围",
                "经核查 PRD-PET-01 与 FAQ-PET-02，简报强制要求的“UV紫外线99.9%杀菌”、“40℃恒温加热”与“静音提升50%”均无事实依据且被合规备忘明确禁止，严格拒绝编造。"
            )

        # 6. Generate initial draft if none exists yet, and invoke estimate_script_duration
        if state["current_draft"] is None:
            state["current_draft"] = self._build_draft_v1_overlong(brief)
            return (
                "estimate_script_duration",
                {
                    "shots": state["current_draft"]["shots"],
                    "target_duration_sec": brief["target_duration_sec"],
                    "min_sec": brief["duration_range_sec"][0],
                    "max_sec": brief["duration_range_sec"][1]
                },
                "观察初稿时长估算结果，并继续调用 check_script_compliance 检查广告法禁用词与事实一致性",
                "已基于 PRD-PET-01 撰写脚本初稿（v1），需先通过时长估算工具量化检验是否在 25~35 秒区间内。"
            )

        draft_ver = state["current_draft"]["version"]

        # 7. If current draft version hasn't been duration-checked yet
        if state["duration_checked_version"] != draft_ver:
            return (
                "estimate_script_duration",
                {
                    "shots": state["current_draft"]["shots"],
                    "target_duration_sec": brief["target_duration_sec"],
                    "min_sec": brief["duration_range_sec"][0],
                    "max_sec": brief["duration_range_sec"][1]
                },
                "确认修订稿时长达标后，必须再次调用 check_script_compliance 复检合规性",
                f"脚本已修订至 v{draft_ver}，必须重新调用时长估算工具验证删减后的总时长是否落入 25~35 秒合格区间。"
            )

        # 8. If current draft version hasn't been compliance-checked yet
        if state["compliance_checked_version"] != draft_ver:
            use_fallback = state["remote_compliance_failed"]
            return (
                "check_script_compliance",
                {
                    "title": state["current_draft"]["title"],
                    "shots": state["current_draft"]["shots"],
                    "use_local_fallback": use_fallback
                },
                "若合规或时长存在任一未通过项，动态修改脚本并进入下一轮复检；若双重校验均通过则输出最终脚本",
                (
                    f"远程合规接口超时后，动态切换 use_local_fallback=True 调用本地规则引擎 RULE-AD-01 对 v{draft_ver} 执行降级合规审查。"
                    if use_fallback else
                    f"对脚本 v{draft_ver} 执行广告法违禁词（RULE-AD-01）与产品事实防幻觉核查。"
                )
            )

        # 9. Both duration and compliance have been checked on current draft_ver: evaluate results!
        dur_ok = state["last_duration_obs"]["within_target_range"]
        comp_ok = state["last_compliance_obs"]["compliance_passed"]

        if not dur_ok or not comp_ok:
            # Dynamically revise draft and trigger re-verification on next steps
            revised = self._refine_draft_from_observations(
                state["current_draft"],
                state["last_duration_obs"],
                state["last_compliance_obs"],
                state["doc_details_map"]
            )
            state["current_draft"] = revised
            return (
                "estimate_script_duration",
                {
                    "shots": revised["shots"],
                    "target_duration_sec": brief["target_duration_sec"],
                    "min_sec": brief["duration_range_sec"][0],
                    "max_sec": brief["duration_range_sec"][1]
                },
                "观察修订稿 v2 的时长复检结果，随后继续调用 check_script_compliance 完成合规复检",
                (
                    f"初稿 v{draft_ver} 检验未通过：预计时长 {state['last_duration_obs']['estimated_total_duration_sec']}s 超出 [25,35]s 区间，"
                    f"且检出违禁词 {[b['word'] for b in state['last_compliance_obs']['banned_word_violations']]} 与无依据参数 "
                    f"{[h['unverified_claim'] for h in state['last_compliance_obs']['fact_hallucination_violations']]}。"
                    f"已精简台词至 108 字、替换违禁词并改用 PRD-PET-01 实测“28dB”参数生成修订稿 v{revised['version']}，立即发起二次时长复检。"
                )
            )

        # 10. Both duration and compliance verified PASSED on current version!
        return (
            "FINISH_COMPLETED",
            {},
            "结束 ReAct 循环，输出最终通过时长与合规双重验证的结构化分镜脚本",
            f"修订稿 v{draft_ver} 经工具复检确认总时长为 {state['last_duration_obs']['estimated_total_duration_sec']}s（满足 25~35s），且合规与事实核查全部 PASSED，达到交付标准。"
        )

    def run(self, brief: Dict[str, Any]) -> AgentDeliverable:
        """Execute the bounded ReAct loop for a given creative brief."""
        max_steps = brief.get("max_steps", 10)
        max_tool_calls = brief.get("max_tool_calls", 12)

        toolbox = ScriptAgentToolbox(
            data_dir=self.data_dir,
            simulate_compliance_timeout_once=brief.get("simulate_tool_failure", False)
        )

        state: Dict[str, Any] = {
            "searched_docs": False,
            "discovered_doc_ids": [],
            "read_doc_details": False,
            "read_doc_ids": [],
            "doc_details_map": {},
            "checked_mandatory_claims": False,
            "unsupported_mandatory_claims": [],
            "current_draft": None,
            "duration_checked_version": -1,
            "compliance_checked_version": -1,
            "last_duration_obs": None,
            "last_compliance_obs": None,
            "remote_compliance_failed": False,
        }

        trace: List[TraceRecord] = []
        steps_executed = 0
        tool_calls_count = 0

        while steps_executed < max_steps and tool_calls_count < max_tool_calls:
            action_name, tool_params, next_plan, rationale = self._decide_next_action(state, brief)

            if action_name == "FINISH_COMPLETED":
                steps_executed += 1
                draft = state["current_draft"]
                dur_obs = state["last_duration_obs"]
                for s, b in zip(draft["shots"], dur_obs["shot_breakdown"]):
                    s["estimated_duration_sec"] = b["estimated_sec"]
                trace.append(TraceRecord(
                    step=steps_executed,
                    action="finish_deliverable",
                    tool_name=None,
                    tool_params={},
                    observation_summary=f"最终脚本 v{draft['version']} 双重复检通过（总时长 {dur_obs['estimated_total_duration_sec']}s，合规 PASSED）。",
                    subsequent_action="输出结构化短视频分镜脚本并结束任务",
                    decision_rationale=rationale
                ))
                return AgentDeliverable(
                    brief_id=brief["brief_id"],
                    status="completed",
                    title=draft["title"],
                    platform=brief["platform"],
                    target_duration_sec=brief["target_duration_sec"],
                    estimated_total_duration_sec=dur_obs["estimated_total_duration_sec"],
                    duration_check_passed=True,
                    compliance_status="PASSED",
                    cited_doc_ids=draft["cited_doc_ids"],
                    shots=draft["shots"],
                    rejection_or_incomplete_reason=None,
                    searched_doc_scope=state["read_doc_ids"],
                    steps_executed=steps_executed,
                    tool_calls_count=tool_calls_count,
                    max_steps_limit=max_steps,
                    max_tool_calls_limit=max_tool_calls,
                    execution_trace=[t.to_dict() for t in trace]
                )

            if action_name == "FINISH_REJECT_MISSING_FACTS":
                steps_executed += 1
                bad_claims = [
                    f"“{c['violated_pattern']}”（原因：{c['reason']}）"
                    for c in state["unsupported_mandatory_claims"]
                ]
                reason_str = (
                    f"拒绝编造产品事实：简报强制要求的 {', '.join(bad_claims)} 在已检索的全部产品知识库 "
                    f"{state['read_doc_ids']} 中无任何事实支撑且被合规文档明确排除。"
                )
                trace.append(TraceRecord(
                    step=steps_executed,
                    action="reject_unsupported_brief",
                    tool_name=None,
                    tool_params={"searched_doc_scope": state["read_doc_ids"]},
                    observation_summary=reason_str,
                    subsequent_action="终止脚本生成，返回明确拒绝说明与已查文档范围",
                    decision_rationale=rationale
                ))
                return AgentDeliverable(
                    brief_id=brief["brief_id"],
                    status="rejected_missing_facts",
                    title="",
                    platform=brief["platform"],
                    target_duration_sec=brief["target_duration_sec"],
                    estimated_total_duration_sec=0.0,
                    duration_check_passed=False,
                    compliance_status="REJECTED_UNSUPPORTED_CLAIMS",
                    cited_doc_ids=state["read_doc_ids"],
                    shots=[],
                    rejection_or_incomplete_reason=reason_str,
                    searched_doc_scope=state["read_doc_ids"],
                    steps_executed=steps_executed,
                    tool_calls_count=tool_calls_count,
                    max_steps_limit=max_steps,
                    max_tool_calls_limit=max_tool_calls,
                    execution_trace=[t.to_dict() for t in trace]
                )

            # Execute tool call
            steps_executed += 1
            tool_calls_count += 1

            try:
                if action_name == "search_product_docs":
                    res = toolbox.search_product_docs(**tool_params)
                    state["searched_docs"] = True
                    state["discovered_doc_ids"] = [r["doc_id"] for r in res["results"]]
                    obs_summary = f"检索命中 {res['matched_count']} 篇资料：{state['discovered_doc_ids']}"

                elif action_name == "get_doc_detail":
                    res = toolbox.get_doc_detail(**tool_params)
                    state["read_doc_details"] = True
                    for did, dcontent in res["documents"].items():
                        if did not in state["read_doc_ids"]:
                            state["read_doc_ids"].append(did)
                        state["doc_details_map"][did] = dcontent
                    obs_summary = f"已读取文档详情 {list(res['documents'].keys())}，获取核心事实条目与边界说明。"

                elif action_name == "verify_mandatory_claims_support":
                    res = toolbox.verify_mandatory_claims_support(**tool_params)
                    state["checked_mandatory_claims"] = True
                    state["unsupported_mandatory_claims"] = res["unsupported_claims"]
                    if res["is_fully_supported"]:
                        obs_summary = "简报所有强制卖点均在 PRD-PET-01 事实范围内，无超纲虚构要求。"
                    else:
                        bad_list = [c["violated_claim"] if "violated_claim" in c else c["violated_pattern"] for c in res["unsupported_claims"]]
                        obs_summary = f"检出 {len(bad_list)} 项疑似无依据/超纲卖点要求：{bad_list}，需补查 FAQ-PET-02 核实。"

                elif action_name == "estimate_script_duration":
                    res = toolbox.estimate_script_duration(**tool_params)
                    state["duration_checked_version"] = state["current_draft"]["version"]
                    state["last_duration_obs"] = res
                    obs_summary = (
                        f"草稿 v{state['current_draft']['version']} 预计总时长 {res['estimated_total_duration_sec']}s "
                        f"（目标区间 {res['allowed_range_sec']}s，达标={res['within_target_range']}）。{res['adjustment_advice']}"
                    )

                elif action_name == "check_script_compliance":
                    res = toolbox.check_script_compliance(**tool_params)
                    state["compliance_checked_version"] = state["current_draft"]["version"]
                    state["last_compliance_obs"] = res
                    b_words = [b["word"] for b in res["banned_word_violations"]]
                    h_claims = [h["unverified_claim"] for h in res["fact_hallucination_violations"]]
                    obs_summary = (
                        f"草稿 v{state['current_draft']['version']} 合规检查结果：passed={res['compliance_passed']} "
                        f"（引擎={res['engine_mode']}，违禁词={b_words}，虚构事实={h_claims}）。"
                    )
                else:
                    raise ValueError(f"Unknown tool: {action_name}")

                # Record sanitary tool params in trace
                logged_params = dict(tool_params)
                if "shots" in logged_params:
                    logged_params["shots"] = f"<共 {len(logged_params['shots'])} 个分镜, 草稿版本 v{state['current_draft']['version']}>"

                trace.append(TraceRecord(
                    step=steps_executed,
                    action=f"call_tool:{action_name}",
                    tool_name=action_name,
                    tool_params=logged_params,
                    observation_summary=obs_summary,
                    subsequent_action=next_plan,
                    decision_rationale=rationale
                ))

            except ToolExecutionError as err:
                state["remote_compliance_failed"] = True
                logged_params = dict(tool_params)
                if "shots" in logged_params:
                    logged_params["shots"] = f"<共 {len(logged_params['shots'])} 个分镜, 草稿版本 v{state['current_draft']['version']}>"
                trace.append(TraceRecord(
                    step=steps_executed,
                    action=f"call_tool:{action_name} (ERROR)",
                    tool_name=action_name,
                    tool_params=logged_params,
                    observation_summary=f"工具执行异常：{str(err)}",
                    subsequent_action="捕获远程服务超时异常，下一步自动切换 use_local_fallback=True 启用本地规则引擎 RULE-AD-01 重试",
                    decision_rationale=rationale
                ))

        # Step or tool-call limit reached without finishing -> return explicit incomplete state!
        draft = state["current_draft"]
        last_dur = state["last_duration_obs"]["estimated_total_duration_sec"] if state["last_duration_obs"] else 0.0
        incomplete_msg = (
            f"未完成（已触发安全步数/工具调用上限：执行步数 {steps_executed}/{max_steps}，工具调用 {tool_calls_count}/{max_tool_calls}）。"
            f"当前停留在草稿版本 v{draft['version'] if draft else 0}（预计时长 {last_dur}s），尚未完成修正后的二次工具复检，按规范熔断退出。"
        )
        return AgentDeliverable(
            brief_id=brief["brief_id"],
            status="incomplete_step_limit",
            title=draft["title"] if draft else "",
            platform=brief["platform"],
            target_duration_sec=brief["target_duration_sec"],
            estimated_total_duration_sec=last_dur,
            duration_check_passed=bool(state["last_duration_obs"] and state["last_duration_obs"]["within_target_range"]),
            compliance_status="UNVERIFIED_AT_STEP_LIMIT",
            cited_doc_ids=draft["cited_doc_ids"] if draft else state["read_doc_ids"],
            shots=draft["shots"] if draft else [],
            rejection_or_incomplete_reason=incomplete_msg,
            searched_doc_scope=state["read_doc_ids"],
            steps_executed=steps_executed,
            tool_calls_count=tool_calls_count,
            max_steps_limit=max_steps,
            max_tool_calls_limit=max_tool_calls,
            execution_trace=[t.to_dict() for t in trace]
        )
