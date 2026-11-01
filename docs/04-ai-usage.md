# 04. AI 辅助使用记录：使用范围、个人修改与验证过程

根据笔试考核规则（*“允许使用 AI 辅助工具，须如实记录使用范围、个人贡献与验证结果”*），本文档如实记录开发过程中 AI 工具的辅助范围、AI 初始产出的缺陷以及个人主导的架构重构与验证工作。

## 1. AI 辅助工具使用范围
1. **合成测试语料起草（`data/`）**：利用 AI 辅助起草了智能宠物饮水机的初始产品规格描述文案与常见广告法违禁词列表，节省了编写基础 JSON 语料的时间。
2. **脚手架与样板代码生成**：利用 AI 辅助生成了 `src/schemas.py` 中 `dataclass` 的基础字段定义以及 `src/cli.py` 中将 JSON Trace 格式化为 Markdown 表格的排版函数。

## 2. 个人核心贡献与对 AI 初始代码的重大修改
在审查 AI 最初生成的 Agent 逻辑时，我发现了 **3 处违背题目红线要求的关键缺陷**，并进行了彻底的人工重构：

### 修改 1：根治“修改后跳过工具复检直接输出”的假闭环缺陷（一票否决项修复）
- **AI 初始代码缺陷**：AI 最初生成的循环逻辑在检测到初稿超时（48s）或含违禁词后，仅调用了一次 `_refine_draft()` 修改文本，随后直接 `return draft` 结束循环，**跳过了对修改稿的二次工具复检**（直接触犯题目“跳过复检直接返回属于关键缺陷”的红线）。
- **个人重构方案**：我在 `src/agent.py` 的状态字典中引入了版本号绑定锁 `duration_checked_version` 与 `compliance_checked_version`。每当生成新草稿版本 `v2` 时，由于 `duration_checked_version (1) != current_draft.version (2)`，状态机从结构上禁止进入 `FINISH_COMPLETED` 分支，强制 Agent 必须对 `v2` 重新调用 `estimate_script_duration` 和 `check_script_compliance`，只有当最新版本同时满足 `within_target_range == True` 且 `compliance_passed == True` 时才允许交付。

### 修改 2：将固定检索改为“发现存疑 → 动态补查 `FAQ-PET-02` → 拒绝编造”的多跳决策（`BR2`）
- **AI 初始代码缺陷**：AI 初版代码在启动时一次性把所有文档全部读入内存，并用简单的 `if/else` 直接报错，无法体现题目要求的“模型根据观察结果动态调整下一步动作（补查）”。
- **个人重构方案**：我将知识库读取拆分为两阶段：初始仅读取核心规格书 `PRD-PET-01` 和创作规范 `SPEC-BRAND-03`；当 `verify_mandatory_claims_support` 观察到简报含有疑似超纲卖点（如“UV杀菌”、“静音提升50%”）时，Agent 才会在下一步动态发起对内部合规备忘 `FAQ-PET-02` 的补充读取，并在确认冲突后输出包含完整 `searched_doc_scope` 的拒绝结论。

### 修改 3：精确对齐中文口播时长核算公式与步数熔断边界（`BR1` & `BR4`）
- **个人修改与校准**：我在 `src/tools.py` 中使用正则 `re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", vo)` 剥离标点符号干扰，按每秒 4.0 个有效汉字 + 每镜 0.5 秒转场缓冲精确建模，校准 `BR1` 初稿为精确的 `48.0s`、修订稿为 `32.4s`；并设计了 `BR4`（`max_steps=5`）熔断用例，确保在初稿未完成二次复检即耗尽步数时，严格返回 `incomplete_step_limit` 与 `UNVERIFIED_AT_STEP_LIMIT`。

## 3. 验证方法与结果
通过编写 `tests/test_agent_acceptance.py` 自动化验收测试套件，对上述 4 个场景及每一条 Trace 的工具调用次数、状态迁移、防幻觉词条进行了严格断言（`python3 -m unittest discover -s tests -v` 4 项测试全部 OK）。
