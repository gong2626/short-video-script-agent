# 01. 需求分析：用户、目标、范围与成功标准

## 1. 业务背景与目标用户
在短视频内容电商与品牌营销（如抖音、小红书）场景中，内容编导与品牌运营人员需要将**创作简报（Creative Brief）**快速转化为可直接投入拍摄的**结构化分镜脚本（Shooting Script）**。传统单次 Prompt 生成（One-Shot LLM Generation）存在三大业务痛点：
1. **口播时长不可控**：模型对中文口播语速与镜头切换耗时缺乏精确感知，常将 30 秒简报写成 45~60 秒长文，导致拍摄剪辑超时。
2. **广告法违禁词风险**：容易出现“100%治愈”、“最静音”、“国家级”等平台与《广告法》明令禁止的极限词或医疗宣称。
3. **产品参数幻觉（Hallucination）**：模型常迎合简报或自行捏造产品规格书中不存在的参数（如在无实验数据支撑时编造“比上一代静音提升 50%”或虚构“UV 紫外线杀菌”功能）。

本项目构建的**短视频脚本 Agent**旨在通过 **ReAct（Reasoning + Acting）多步工具调用与验证闭环**，为内容创作者交付**时长精准达标、卖点有据可查、合规零违禁词**的可拍摄短视频分镜脚本。

## 2. 系统输入与交付物定义

### 2.1 输入数据与知识库（`data/`）
- **创作简报（`data/briefs.json`）**：包含简报 ID（`brief_id`）、主题（`topic`）、目标受众（`audience`）、发布平台（`platform`）、目标时长（`target_duration_sec`，如 30 秒及合格区间 `[25, 35]` 秒）、风格要求（`style`）、强制卖点要求（`mandatory_requirements`）及安全步数上限（`max_steps` / `max_tool_calls`）。
- **产品与创作知识库（`data/product_docs.json`）**：
  - `PRD-PET-01`：《小影萌宠·涌泉式智能宠物饮水机 Pro 产品规格书》（记载 304 食品级不锈钢水盘、四重活水过滤、实测 28dB 低噪水泵、2.5L 容量、缺水自动断电等核心事实）。
  - `FAQ-PET-02`：《智能宠物饮水机常见质询与功能边界说明》（明确声明产品**不含 UV 紫外线杀菌**、**不支持恒温加热**、**无“静音提升50%”对比实验数据**）。
  - `SPEC-BRAND-03`：《小影萌宠短视频视觉与镜头语言规范》（定义黄金前 3 秒痛点开场、每秒 4.0 字口播语速与 0.5 秒转场缓冲核算标准）。
- **合规与防幻觉规则库（`data/compliance_rules.json` - `RULE-AD-01`）**：包含广告法禁用词字典（如“100%治愈”、“零噪音”）与事实防幻觉匹配模式（如“静音提升50%”、“UV杀菌”）。

### 2.2 交付结果结构（`AgentDeliverable`）
Agent 最终输出强类型 JSON 结构与 Markdown 报告，包含：
- `title`：短视频标题
- `shots`：分镜列表（含 `shot_id` 镜号、`visual_description` 画面描述、`voiceover` 旁白台词、`subtitle` 底部字幕、`estimated_duration_sec` 单镜预计时长、`cited_doc_ids` 引用依据文档 ID）
- `estimated_total_duration_sec`：经工具核算的预计总时长
- `cited_doc_ids` / `searched_doc_scope`：引用的知识库文档 ID 与已检索文档范围
- `compliance_status`：合规检查状态（`PASSED` / `REJECTED_UNSUPPORTED_CLAIMS` / `UNVERIFIED_AT_STEP_LIMIT`）
- `status`：任务完成状态（`completed` / `rejected_missing_facts` / `incomplete_step_limit`）
- `execution_trace`：完整的 ReAct 步骤记录（含步骤号、工具名、参数、返回摘要、后续动作计划、简要决策依据）

## 3. 项目范围（In-Scope vs Out-of-Scope）
- **已完成核心范围（In-Scope，建议 3 小时核心链路）**：
  - 完整的 ReAct 状态机循环（支持真实 LLM API 与离线观察驱动引擎双模式）；
  - 4 个核心领域工具（文档检索、原文详情读取、强制卖点事实核验、口播时长精确估算、广告法合规与事实防幻觉审查）；
  - 初稿超时/违规后的自动修订与二次工具复检闭环；
  - 资料缺失时的二次补查与拒绝编造机制；
  - 工具异常（HTTP 504 超时）捕获与本地规则引擎降级重试；
  - 最大步数与最大工具调用次数熔断保护。
- **非必需范围（Out-of-Scope）**：图形化 Web 前端界面、分布式多 Agent 协同、线上容器化部署及真实视频画面渲染。

## 4. 成功与验收标准（Acceptance Criteria）
1. **修改-复检闭环验收（`BR1`）**：初稿预计 48.0 秒且含禁用词“100%治愈”与虚构参数“静音提升50%”时，Agent 必须根据工具返回摘要缩减台词、替换违规词、改用实测“28dB”参数，并**再次调用时长与合规工具复检通过（总时长落入 25~35 秒且合规 PASSED）**后方可返回 `completed`。
2. **反幻觉与拒绝编造验收（`BR2`）**：当简报强制要求宣传资料库中不存在或被明确排除的卖点（如“UV 杀菌”、“静音提升 50%”）时，Agent 必须主动补查 `FAQ-PET-02`，确认无依据后**拒绝编造**，返回 `rejected_missing_facts` 并列出已查文档范围 `['PRD-PET-01', 'SPEC-BRAND-03', 'FAQ-PET-02']`。
3. **工具容错降级验收（`BR3`）**：当远程合规服务超时报错时，Agent 能根据异常观察动态切换本地规则引擎参数完成校验。
4. **步数上限熔断验收（`BR4`）**：达到 `max_steps` 或 `max_tool_calls` 时立即停止并返回 `incomplete_step_limit`，绝不将未复检草稿伪装成成功结果返回。
