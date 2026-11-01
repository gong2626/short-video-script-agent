#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI entry point for running the Short-Video Script Agent and generating evaluation traces."""

import argparse
import json
import os
import sys
from typing import Dict, Any, List

from src.agent import ShortVideoScriptReActAgent


def format_markdown_trace(deliverable_dict: Dict[str, Any], brief: Dict[str, Any]) -> str:
    """Format an AgentDeliverable into a human-readable Markdown trace report."""
    lines = [
        f"# 运行记录与决策轨迹：{brief['brief_id']} - {brief['title']}",
        "",
        "## 1. 输入简报与约束条件",
        f"- **简报 ID**：`{brief['brief_id']}`",
        f"- **主题 / 平台**：{brief['topic']}（{brief['platform']}）",
        f"- **目标受众**：{brief['audience']}",
        f"- **目标时长与合格区间**：目标 `{brief['target_duration_sec']}s`（允许区间 `{brief['duration_range_sec'][0]}~{brief['duration_range_sec'][1]}s`）",
        f"- **安全步数与工具调用上限**：`max_steps={brief['max_steps']}`, `max_tool_calls={brief['max_tool_calls']}`",
        "",
        "## 2. 执行结果摘要",
        f"- **最终完成状态 (`status`)**：**`{deliverable_dict['status']}`**",
        f"- **执行步数 / 工具调用次数**：`{deliverable_dict['steps_executed']} / {deliverable_dict['max_steps_limit']} 步`，工具调用 `{deliverable_dict['tool_calls_count']} / {deliverable_dict['max_tool_calls_limit']} 次`",
        f"- **预计总时长 (`estimated_total_duration_sec`)**：`{deliverable_dict['estimated_total_duration_sec']}s`（时长达标：`{deliverable_dict['duration_check_passed']}`）",
        f"- **合规检查状态 (`compliance_status`)**：`{deliverable_dict['compliance_status']}`",
        f"- **已查阅资料范围 (`searched_doc_scope`)**：`{deliverable_dict['searched_doc_scope']}`",
    ]
    if deliverable_dict.get("rejection_or_incomplete_reason"):
        lines.append(f"- **拒绝或未完成原因**：{deliverable_dict['rejection_or_incomplete_reason']}")

    lines.extend([
        "",
        "## 3. ReAct 动态决策与工具调用轨迹（Step-by-Step Trace）",
        "",
        "| 步骤 | 动作 / 工具名称 | 工具输入参数 | 工具返回摘要 (Observation) | 后续动作计划 | 简要决策依据 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ])

    for t in deliverable_dict["execution_trace"]:
        params_str = json.dumps(t["tool_params"], ensure_ascii=False)
        lines.append(
            f"| Step {t['step']} | `{t['action']}` | `{params_str}` | {t['observation_summary']} | {t['subsequent_action']} | {t['decision_rationale']} |"
        )

    if deliverable_dict["shots"]:
        lines.extend([
            "",
            f"## 4. 最终交付分镜脚本：《{deliverable_dict['title']}》",
            "",
            "| 镜号 | 画面与运镜描述 | 旁白台词 (Voiceover) | 底部字幕 (Subtitle) | 预计时长 | 引用依据 ID |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ])
        for s in deliverable_dict["shots"]:
            lines.append(
                f"| Shot {s['shot_id']} | {s['visual_description']} | {s['voiceover']} | {s['subtitle']} | `{s['estimated_duration_sec']}s` | `{', '.join(s['cited_doc_ids'])}` |"
            )

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Short-Video Script ReAct Agent CLI")
    parser.add_argument("--brief-id", type=str, default="ALL", help="Brief ID to run (BR1, BR2, BR3, BR4, or ALL)")
    parser.add_argument("--max-steps", type=int, default=None, help="Override max steps limit")
    parser.add_argument("--output-dir", type=str, default="examples", help="Directory to save trace outputs")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    out_dir = os.path.join(base_dir, args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(data_dir, "briefs.json"), "r", encoding="utf-8") as f:
        briefs: List[Dict[str, Any]] = json.load(f)

    agent = ShortVideoScriptReActAgent(data_dir=data_dir)

    filename_map = {
        "BR1": "case1_br1_normal_refine",
        "BR2": "case2_br2_missing_facts",
        "BR3": "case3_br3_tool_failure_recovery",
        "BR4": "case4_br4_step_limit_exceeded"
    }

    selected = [b for b in briefs if args.brief_id == "ALL" or b["brief_id"] == args.brief_id]
    if not selected:
        print(f"Error: Brief ID '{args.brief_id}' not found.", file=sys.stderr)
        sys.exit(1)

    for b in selected:
        if args.max_steps is not None:
            b = dict(b)
            b["max_steps"] = args.max_steps
        result = agent.run(b)
        res_dict = result.to_dict()
        prefix = filename_map.get(b["brief_id"], b["brief_id"].lower())
        json_path = os.path.join(out_dir, f"{prefix}_trace.json")
        md_path = os.path.join(out_dir, f"{prefix}_summary.md")

        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(res_dict, jf, ensure_ascii=False, indent=2)
        with open(md_path, "w", encoding="utf-8") as mf:
            mf.write(format_markdown_trace(res_dict, b))

        print(
            f"[{b['brief_id']}] status={res_dict['status']} | steps={res_dict['steps_executed']}/{res_dict['max_steps_limit']} "
            f"| duration={res_dict['estimated_total_duration_sec']}s | compliance={res_dict['compliance_status']} -> Saved to {prefix}_trace.json"
        )


if __name__ == "__main__":
    main()
