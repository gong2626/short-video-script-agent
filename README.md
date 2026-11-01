# 短视频脚本 Agent（小影科技 2027 校招 AI Agent 笔试 · 第 4 题）

本项目面向**第 4 题：短视频脚本 Agent**，实现了一个基于 **ReAct（Reasoning + Acting）动态决策闭环** 的短视频分镜脚本生成与合规验证系统。Agent 能够根据创作简报（Brief）自主检索产品资料、估算分镜口播时长、执行广告法禁用词与事实防幻觉核查，并在初稿超时或违规时自动触发**“修改 → 工具二次复检”**闭环，同时具备资料缺失拒绝编造、工具超时降级恢复以及步数/调用次数上限安全熔断能力。

## 1. 目录结构（严格对齐 GitHub 交付规范）

```text
short-video-script-agent/
├── README.md                  # 环境、安装、运行、评审入口说明
├── requirements.txt           # 依赖说明（零第三方重度依赖，Python 3.10+ 原生可运行）
├── .env.example               # 环境变量模板（无变量时可直接离线运行）
├── src/
│   ├── __init__.py
│   ├── schemas.py             # 强类型数据结构：ShotItem, ScriptDraft, TraceRecord, AgentDeliverable
│   ├── tools.py               # 领域工具集：资料检索、详情读取、卖点事实校验、时长估算、合规与防幻觉检查
│   ├── agent.py               # ReAct 核心状态机（模型选择动作 → 执行工具 → 观察结果 → 动态调整或终止）
│   └── cli.py                 # CLI 命令行入口（支持单简报运行与批量生成 examples/ Trace）
├── data/
│   ├── briefs.json            # 4 组测试创作简报（BR1 正常修正复检、BR2 资料不足拒编、BR3 工具超时恢复、BR4 步数上限熔断）
│   ├── product_docs.json      # 品牌与产品资料库（PRD-PET-01 规格书、FAQ-PET-02 边界备忘、SPEC-BRAND-03 创作规范）
│   └── compliance_rules.json  # 平台广告法禁用词与事实防幻觉规则库（RULE-AD-01）
├── tests/
│   └── test_agent_acceptance.py # 可执行自动化验收测试套件（覆盖全部必测边界与一票否决项）
├── examples/                  # 真实运行生成的 4 组 JSON Trace 与 Markdown 可读报告
│   ├── case1_br1_normal_refine_trace.json
│   ├── case1_br1_normal_refine_summary.md
│   ├── case2_br2_missing_facts_trace.json
│   ├── case2_br2_missing_facts_summary.md
│   ├── case3_br3_tool_failure_recovery_trace.json
│   ├── case3_br3_tool_failure_recovery_summary.md
│   ├── case4_br4_step_limit_exceeded_trace.json
│   └── case4_br4_step_limit_exceeded_summary.md
└── docs/
    ├── 01-requirements.md     # 用户、目标、范围和成功标准
    ├── 02-solution.md         # 调用流程、动态决策、技术取舍
    ├── 03-evaluation.md       # 测试预期、实际结果、失败和限制（引用 examples/ 具体文件）
    ├── 04-ai-usage.md         # AI 辅助内容、个人修改及验证
    └── 05-retrospective.md    # 最难问题、学习收获、下一步
```

## 2. 环境要求与安装

- **Python 版本**：`Python 3.10+`（核心引擎采用 Python 标准库原生实现，无需安装额外重型框架即可在任意评审机器上一键运行）。
- **配置文件**：无需配置 `.env` 即可直接运行离线动态决策引擎；如需接入外部兼容 API，可复制 `cp .env.example .env` 并填入 `OPENAI_API_KEY`。

## 3. 一键运行命令与评审入口

### 3.1 运行全部 4 个测试场景并生成 `examples/` Trace 记录

```bash
python3 -m src.cli
```

运行后终端输出如下，并在 `examples/` 下生成对应的 `.json` 与 `.md` 运行轨迹文件：

```text
[BR1] status=completed | steps=8/10 | duration=32.4s | compliance=PASSED -> Saved to case1_br1_normal_refine_trace.json
[BR2] status=rejected_missing_facts | steps=5/10 | duration=0.0s | compliance=REJECTED_UNSUPPORTED_CLAIMS -> Saved to case2_br2_missing_facts_trace.json
[BR3] status=completed | steps=9/10 | duration=32.4s | compliance=PASSED -> Saved to case3_br3_tool_failure_recovery_trace.json
[BR4] status=incomplete_step_limit | steps=5/5 | duration=48.0s | compliance=UNVERIFIED_AT_STEP_LIMIT -> Saved to case4_br4_step_limit_exceeded_trace.json
```

### 3.2 单独运行指定简报或自定义步数上限

```bash
# 仅运行参考案例 BR1（初稿 48.0s + 违禁词“100%治愈” + 虚构“静音提升50%” -> 动态修正复检通过）
python3 -m src.cli --brief-id BR1

# 测试自定义步数上限（例如限制 4 步触发熔断）
python3 -m src.cli --brief-id BR1 --max-steps 4
```

### 3.3 运行自动化验收测试套件

```bash
python3 -m unittest discover -s tests -v
```

## 4. 评审快速导读

1. **核心代码审阅**：请查看 `src/agent.py`（ReAct 循环与动态修正策略）与 `src/tools.py`（时长核算、禁用词与防幻觉规则工具）。
2. **多路径 Trace 审阅**：请查看 `examples/case1_br1_normal_refine_summary.md`（修正-复检闭环）、`examples/case2_br2_missing_facts_summary.md`（补查后拒绝编造）、`examples/case3_br3_tool_failure_recovery_summary.md`（工具504超时降级恢复）与 `examples/case4_br4_step_limit_exceeded_summary.md`（步数上限熔断）。
3. **设计文档审阅**：请按顺序阅读 `docs/01-requirements.md` 至 `docs/05-retrospective.md`。
