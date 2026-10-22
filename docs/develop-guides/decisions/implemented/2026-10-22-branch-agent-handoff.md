# 分支级 Agent 交接入口

状态：implemented
类型：process
Owner：AGENT_HANDOFF.md

## 问题

新会话需要识别 `basic` 与 `cydx` 的产品边界、运行入口和未完成事项。仅加载共同开发约定不能解释分支差异，把本地会话记录当作事实又会遗漏真实源码和验证状态。

## 决策

各分支在根目录维护一份 `AGENT_HANDOFF.md`，从 `AGENTS.md` 链接。交接入口只保存分支定位、源码与文档入口、新会话核查顺序和带日期的待核对快照；架构、测试命令和部署细节继续由原有 Owner 维护。分支与工作树状态必须在接手时重新读取。

## 替代方案

只依赖聊天历史无法供新会话稳定读取；扩充 `AGENTS.md` 会混合常驻约束与易变状态；在两分支保存一份相同的完整平台说明会重复事实并隐藏定制边界。

## 后果

交接快照随开发失效，接手者必须重新读取 Git、运行环境和 owning 材料；构建与源码检查不能替代业务链路验收。

根目录交接文档作为内部 Agent 入口，不加入面向用户的站点导航；新增常驻约定仅为根 `AGENTS.md` 的一条链接。详细产品事实继续在源码、Compose 和专题文档闭合，交接页不维护独立架构或测试命令全集。

## 验证

在 `basic` 工作树执行并核对：

- `Inspected`：分支源码、Compose、分支差异与已有未提交文件；员工侧栏和离线交付提案仍保留各自未验收范围。
- `Passed`：`python3 scripts/verify_engineering_contracts.py`；内联 Python 检查交接页、根约定与本记录的相对链接、锚点、空白及末尾换行。
- `Passed`：`cd docs` 后执行 `pnpm run build`。
- `Passed`：`git diff --check`。
- `Inspected`：不继承开发上下文的独立 Reviewer 核对完整需求、变更、源码和证据，分支边界与待办描述通过语义审查。

`python3 -m unittest scripts.test_verify_engineering_contracts` 执行 62 项，61 项通过，1 项因 Windows 无符号链接权限报错；编辑前后结果相同，未全通过。`docker compose exec api uv run --group test pytest test/unit -m "not slow"` 为 `Not run`：本机无 Docker 可执行文件，且无可用 WSL 发行版。产品和生产链路未执行，文档检查不提供该层证据。
