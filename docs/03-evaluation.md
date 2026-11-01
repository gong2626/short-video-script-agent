# 03. 效果评估：测试预期、实际结果、失败边界与已知限制

## 1. 验证材料与测试用例矩阵总览
我们在 `examples/` 目录下提交了 4 组完整覆盖正常、资料不足、工具失败及步数超限场景的真实运行记录（包含结构化 `.json` 与可读 `.md` 报告），并通过 `tests/test_agent_acceptance.py` 进行了自动化断言验证：

| 用例编号 | 对应简报与测试场景 | 覆盖验收点 | 预期结果 | 实际运行结果与引用文件 |
| :--- | :--- | :--- | :--- | :--- |
| **Case 1** | `BR1`：宠物饮水机 30s 抖音种草脚本（初稿 48s 超时 + 含违禁词与虚构卖点） | 初稿超时/违规后的“修改-复检”循环；引用文档依据；卖点真实性 | 初稿检出 48.0s 与违规项 → 修订为 v2 → 重新调用两项工具复检达标后输出 `completed` | **PASS**（耗时 8 步，7 次工具调用，终稿 `32.4s`，合规 `PASSED`）<br>详见：`examples/case1_br1_normal_refine_trace.json`、`examples/case1_br1_normal_refine_summary.md` |
| **Case 2** | `BR2`：强制要求宣传“UV 99.9%杀菌 + 40℃恒温 + 静音提升50%” | 资料缺失/冲突时主动补查；拒绝编造产品事实；列出已查文档范围 | 初检存疑 → 补查 `FAQ-PET-02` → 确认无事实依据后拒绝生成，返回已查文档 ID | **PASS**（耗时 5 步，4 次工具调用，状态 `rejected_missing_facts`，已查 `['PRD-PET-01', 'SPEC-BRAND-03', 'FAQ-PET-02']`）<br>详见：`examples/case2_br2_missing_facts_trace.json`、`examples/case2_br2_missing_facts_summary.md` |
| **Case 3** | `BR3`：夜间静音脚本 + 远程合规接口 HTTP 504 超时故障注入 | 工具失败捕获；动态切换备份参数降级重试；完成完整复检闭环 | Step 5 捕获 504 超时 → Step 6 自动切换 `use_local_fallback=True` 恢复检验并最终完成 | **PASS**（耗时 9 步，8 次工具调用，经历 1 次工具失败后成功恢复，终稿 `32.4s`）<br>详见：`examples/case3_br3_tool_failure_recovery_trace.json`、`examples/case3_br3_tool_failure_recovery_summary.md` |
| **Case 4** | `BR4`：严苛步数上限（`max_steps=5, max_tool_calls=5`） | 达到步数或工具调用次数上限时安全熔断；不把未复检初稿当成功返回 | 在完成初稿检验（Step 5，时长 48.0s）后达到 5 步上限，立即返回 `incomplete_step_limit` | **PASS**（执行 `5/5` 步后精准熔断，状态 `incomplete_step_limit`，明确提示未完成二次复检）<br>详见：`examples/case4_br4_step_limit_exceeded_trace.json`、`examples/case4_br4_step_limit_exceeded_summary.md` |

## 2. 核心案例轨迹对比分析

### 2.1 Case 1 (`BR1`)：初稿超时与违规后的动态修正复检轨迹
在 `examples/case1_br1_normal_refine_summary.md` 中，Agent 完整展现了 8 步 ReAct 决策链：
- **Step 1–3（检索与核实）**：调用 `search_product_docs` 发现 3 篇资料，调用 `get_doc_detail` 读取 `PRD-PET-01` 与 `SPEC-BRAND-03`，确认简报要求合法。
- **Step 4（初稿时长检验）**：生成初稿 `v1` 并调用 `estimate_script_duration`，工具返回：
  > `草稿 v1 预计总时长 48.0s（目标区间 [25, 35]s，达标=False）。当前总时长 48.0s 超出上限 35s（超出 13.0s），请删减旁白字数至 92~132 字以内并重新调用本工具复检。`
- **Step 5（初稿合规检验）**：调用 `check_script_compliance`，工具返回：
  > `草稿 v1 合规检查结果：passed=False（违禁词=['100%治愈']，虚构事实=['静音提升50%']）。`
- **Step 6–7（动态修订与二次复检）**：Agent 根据 Step 4 和 Step 5 的工具反馈生成修订稿 `v2`（删除“静音提升50%”改为 `PRD-PET-01` 记载的“实测低至二十八分贝”，将“100%治愈”替换为“温柔呵护”，并将总字数精简至 108 字），随后在 Step 6 再次调用 `estimate_script_duration`（返回 `32.4s`，`within_target_range=True`），在 Step 7 再次调用 `check_script_compliance`（返回 `passed=True`）。
- **Step 8（安全交付）**：双重验证通过，输出最终分镜脚本。

### 2.2 Case 2 (`BR2`)：补查知识库并拒绝编造轨迹
在 `examples/case2_br2_missing_facts_summary.md` 中，当简报要求必须宣传“UV 紫外线 99.9% 杀菌”与“静音提升 50%”时：
- Agent 在 Step 3 调用 `verify_mandatory_claims_support` 发现上述卖点不在 `PRD-PET-01` 中；
- 在 Step 4 动态决定调用 `get_doc_detail(doc_ids=["FAQ-PET-02"])` 补查边界说明；
- 观察到 `FAQ-PET-02` 明确记载“未内置 UV 杀菌灯管、无静音提升 50% 对比数据”后，于 Step 5 触发 `reject_unsupported_brief`，拒绝生成任何虚假分镜。

## 3. 失败场景处理与已知限制
1. **口播时长估算模型的物理局限**：当前 `estimate_script_duration` 基于线性字数速率（`4.0 字/秒 + 0.5 秒/镜转场缓冲`）估算时长，未考虑不同配音演员的情绪停顿、重音拖长或特殊英文缩写的发音时长差异。
2. **规则库静态匹配限制**：当前本地合规引擎 `RULE-AD-01` 基于关键词与正则模式匹配违禁词和虚构事实，对于高度隐晦的谐音违禁词（如“100%治俞”）或跨句隐式医疗暗示，需结合大模型语义级审查进一步增强。
