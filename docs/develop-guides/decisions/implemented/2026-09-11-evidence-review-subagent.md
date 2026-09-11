# 事实证据审查子智能体

状态：implemented
类型：feature
Owner：backend/package/yuxi/agents/buildin/evidence_review/graph.py

## 问题

案件结构化解析结果需要按待证事实核对证据，通用子任务缺少稳定的输入、输出和事实证据审查边界。

## 决策

注册专用子智能体后端，复用现有 task、SubagentRunService、PostgreSQL checkpoint 和文件后端。输入接收 Case JSON 与可选原文路径；独立提示词约束专业分析，Pydantic 校验模型输出和证据标识，确定性处理空事项与缺失证据。结果经现有子任务消息返回主 Agent，前端在 task 与异步结果中呈现专业结果。

内置定义的 slug 为 `evidence-review`，后端为 `EvidenceReviewSubagent`。主 Agent 的子智能体配置为空时沿用“全部可见”语义；明确配置白名单时需要包含此 slug。用户在现有对话中要求事实证据审查，由主 Agent 传入解析 Skill 的案件结果，不新增首页入口或独立案件系统。

主 Agent 调用已有工具，参数示例：

```json
{
  "subagent_slug": "evidence-review",
  "description": "{\"case_json\":{\"violations\":[{\"violation_id\":\"V1\",\"behavior\":\"收入事项\",\"fact_summary\":\"报告认定收入100万元\",\"evidence_ids\":[]}],\"evidence\":[]},\"original_materials\":[]}"
}
```

`schema.py` 拥有输入输出契约：`EvidenceReviewInput` 包含完整 `case_json` 和可选的 `original_materials` 文本窗口。输出 `FactEvidenceReviewResult` 包含 `review_type`、`overall_status`、`summary`、`violation_reviews`、`evidence_conflicts`、`evidence_gaps`、`review_findings`、`message`、`limitations`。每项待证事实保留证据映射、四级充分程度、三级风险及补证建议。

`review.py` 校验证据 ID 与事项关联，证据名称、类型及证明内容取自输入材料；推论留在分析字段。事项总评和数量从事实评级生成。原文引用只接受已有定位，只有实际读取的文件才提供预览链接。专业提示词固定在 `prompt.py`，模型结构或引用校验失败最多纠正一次，仍失败则明确终止，不交付伪成功结果。

## 替代方案

仅配置通用子智能体提示词无法强制结构校验。新建案件系统会重复权限、消息和运行生命周期，因此使用现有平台扩展点。

## 后果

模型的专业判断仍需人工复核；Schema 只能验证结构与来源标识，不能证明材料真实。原文读取失败或只提供结构化材料时明确标记核查范围。保留原文与结构化内容分歧，不替代其他审查岗位或最终审理决定。

模型需要支持 function calling 结构化输出。Word/PDF 沿用前置解析能力；本岗位读取最多十份已解析文本窗口，每份最多 4000 行。现有文件预览可打开原文，页码、段落和 chunk 保留为定位文字，未新增精确页内跳转。没有原文时仍可审查 Case JSON，但不宣称已回查。

## 验证

2026-09-12 在独立验证容器、独立 PostgreSQL/Redis 和合成案件中验证；没有更新生产部署或读取真实案件。

- `python -m pytest test/unit -m "not slow" -q -p no:cacheprovider`：2004 passed；补充成功原文读取用例后，本功能定向测试 24 passed。覆盖空输入、重复标识、未知/跨事项证据、未读取来源、原文不可读、证据证明内容不可改写、总评一致性和 v3 图输出。成功读取用例执行真实 `aread` 转换，在文件服务边界使用合成文本替身，核对原文进入模型上下文及输出引用。
- `EVIDENCE_REVIEW_PROBE_URL=<测试端点> EVIDENCE_REVIEW_PROBE_MODEL=DeepSeek-V4 python -m pytest test/integration/services/test_evidence_review_model_probe.py --confcutdir=test/integration/services -q -p no:cacheprovider`：六类真实模型案例全部通过（互证、孤证、金额缺口、笔录与流水冲突、无证据、重复个人收款证据）。
- `EVIDENCE_REVIEW_E2E_MODEL=<测试模型标识> python -m pytest test/e2e/test_evidence_review_e2e.py -q -p no:cacheprovider`：增强 SSE 断言后 1 passed（119.79 秒）。真实 HTTP、worker、SSE 与 PostgreSQL 验证主 Agent 调用 task，子 Run 输出绑定自身 request/run，主 Run 的工具结果收到相同审查数据；每条 SSE 事件绑定当前 Run，消息和 end 事件完整交付，终态 request_id 对应父 Run。凭据通过独立测试环境注入。
- 新模块及测试 Ruff 检查通过；`pnpm lint:check`、`pnpm test:unit`（329 passed）、`pnpm build` 通过；补充嵌套字段缺失校验后，结果解析与 Vue 渲染定向测试 21 passed。task 和 subagent_await 的真实 Vue 渲染测试验证风险及来源展示；浏览器检查真实模型结果卡片的低风险和高风险视图，以及原文按钮向预览回调传递准确路径。浏览器组件预览不代替上述后端 E2E；完整沙盒文件读取至预览内容的 E2E 尚未验证。
- `python scripts/verify_engineering_contracts.py` 通过；`python -m unittest scripts.test_verify_engineering_contracts` 在 Linux 验证容器中 62 项通过；文档 `pnpm build` 通过。前端与文档构建保留既有大 chunk 警告。
