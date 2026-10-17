# 长程票图：implement-spec、单集成 PR、门感知合并

**什么时候读**：G-tickets 已验收完整票图且本轮要实施时；准备派发或验收长程 worker 时；
判断集成 PR 能否自动合并时；或出现流程错误、需要做 retro 时。

## 目录

- [1. 入口条件：票图完整](#1-入口条件票图完整)
- [2. 只派一个长程 worker](#2-只派一个长程-worker)
- [3. 嵌套拓扑与 worktree 能力](#3-嵌套拓扑与-worktree-能力)
- [4. 协调者验收](#4-协调者验收)
- [5. 门感知合并](#5-门感知合并)
- [6. 流程错误后的 retro](#6-流程错误后的-retro)
- [7. 回退与停止条件](#7-回退与停止条件)

## 1. 入口条件：票图完整

`implement-spec` 需要一份 spec 加一张任务图。派发前，以下条件必须全部成立：

- 存在 spec 指针（spec 文件或父 issue）。若本轮只产出票，从父 issue 或设计文档合成指针；
  既无 spec 也无父 issue 时回 `to-spec`，不要凭空编一份。
- 每张票都有标题、**要构建什么**、验收标准，以及 tracker 能关闭的状态。本地文件 tracker
  使用 `.scratch/<feature>/issues/<NN>-<slug>.md`；真实 tracker 有原生阻塞边时优先用原生边。
- 每个 blocker 都指向真实存在的票。图无环，且 frontier 上至少有一张票可拿。依赖指向不存在
  或已废弃关闭的票，是坏图，不是 frontier。
- tracker 可达：`docs/agents/issue-tracker.md` 存在，worker 能用它的命令面（`gh` / `glab`
  已登录，或本地票文件从 worktree 可见）。被 gitignore 的 `.scratch` 不会出现在新 worktree，
  因此要通过共享文件系统上的绝对路径暴露给 worker，或把票文件提交进仓库；否则读不到票。
- 每张票能装进一个新鲜 context；预重构与 expand–contract 票排在前面。票太大就回
  `to-tickets`，不要让 `implement-spec` 做到一半才发现。

已定案的单票仍走 B 通道。这条路径是给票图用的，不是给单票套壳。

## 2. 只派一个长程 worker

为整张票图启动一个 supervised worker，而不是一票一个：

```text
worker-start --spec "<长程 spec>" --worktree new-top-level \
  --name <feature-slug>-integration --setup run --agent <实时 agent> --json
```

spec 是一组指针，不是票的副本。必须包含：

```text
前置 skill：<绝对路径>/implement-spec/SKILL.md——开工前完整读。
skill 解析：有 Skill tool 时用它调用 `tdd` / `code-review`；没有就直接读
<绝对路径>/tdd/SKILL.md 与 <绝对路径>/code-review/SKILL.md，不许转述。
PR skill：<绝对路径>/pr/SKILL.md——用它写唯一的集成 PR 正文。
Tracker：<docs/agents/issue-tracker.md 或本地票目录绝对路径>。
Spec：<绝对路径或 issue URL>。
Tickets：<tracker 查询 / 本地目录；写明 frontier 与阻塞边>。
Integration branch：<名称>；base：<默认 base ref>。
并发：最多 <N> 个 implementer；用户或仓库未另说时默认 3。
```

这个 worker 是**编排者**，不得自己实现票。它维护图和 frontier，为每张就绪票启动一个新鲜
implementer，通过 merger 步骤合入各自分支，跑最终 review 并开 PR。spec、票、笔记与 commit
的上下文指针就是通信方式；不要在每个 prompt 里重述整张图。

每个 implementer 报告自己的 worktree、branch、commit、测试，以及从 integration branch
合入了什么。所有决策类问题——scope、用户可观察行为、方案分叉或五类 escalation——都经顶层
worker 上抛给协调者。worker 不得替人类作答。

## 3. 嵌套拓扑与 worktree 能力

`implement-spec` 假设每个 implementer 有自己的 worktree。这个假设要在花掉整张图之前得到
证明。worker 的首次报告必须说明：

1. 它能创建隔离 worktree（`git worktree add` 或 `orca worktree create`），分支从 integration
   branch 切出；
2. 它能在后台并行跑 implementer，或明确改为串行；
3. 它能合并分支而不编辑主工作副本。

隔离成立时，按 frontier 并行跑 implementer，最多到并发上限。每个 implementer 确认自己的
worktree 基于 integration branch，调用 `tdd`，在报告完成前把 integration tip 合入自己的分支，
并保持分支干净。merger 子代理——harness 没有子代理时就是 worker 自己——按 DAG 顺序把完成
的分支合入 integration branch，每次合并后重跑受影响测试。

隔离无法证明时，**绝不让两个 implementer 共用一个 worktree**。改为串行，一次一张票，在
worker 自己的工作区内完成，并记录降级。worker 完全不能跑子代理时，回退到 §7 的逐票 Orca
worker 模型，并在报告里说明原因。

implementer 若是 Orca 嵌套 worker，必须遵守 `nested_worker_depth_exceeded`；新建 Run 不会
重置深度。若是 harness 子代理，它们不携带 Orca 生命周期：顶层 worker 仍对它们的 worktree、
分支与产出负责。

## 4. 协调者验收

协调者验收的是**集成 PR**，不是每个嵌套分支。检查：

- 整张图只有一个 PR（或已记录的回退方案）；head 与最终验收 SHA 一致；标为 ready 前，
  integration branch 已 rebase 到当前默认 base。
- 每张票的分支都已合入；没有票只留在 worktree 里。每张票按 tracker 的关闭方式关闭，
  PR 正文带 spec 与 tickets 的 `Closes` 链接。
- 最终 tree 通过适用的全量门禁。抽查至少两张票的证据——它们的测试与验收标准——不要只信
  摘要。逐票 TDD 是 implementer 的契约；integration branch 上的一次双轴 `code-review` 是
  本路径的 review 门禁。把这个选择记入报告。
- worker 清理了嵌套 worktree；主工作副本未被改动；没有无法解释的未提交改动。

分支缺失、测试红、票未关闭或 head 过期时，把发现打回顶层 worker。协调者不进入嵌套
worktree，也不自己补完一张票。

## 5. 门感知合并

worker 用 `pr` skill 写 PR 正文，包含 `Door`、`Blast Radius` 与证据。协调者随后用真实 diff
核对门声明。worker 的标签是输入，不是证明。

**单向门触发项**——任意一项成立，整个 PR 就是单向门：

- schema 或数据迁移、回填、删除；
- 破坏性的公共 API、CLI、SDK 或持久化格式变更：删除或重命名已导出符号、修改既有签名/
  语义/默认值，或改变存储格式。纯增量、向后兼容的新增，若不改数据或外部契约，是双向门；
- 认证、权限、密钥或信任边界变更；
- 计费、定价或权益变更；
- 部署、基础设施或运行时配置变更；
- 不可逆的外部副作用；
- 移除功能，或主版本依赖升级；
- 影响面很宽且没有简单回滚。

diff 里出现触发项时，即使正文写 two-way，也按单向门处理。打回 worker 修正正文，再按单向门
处理。拿不准就按单向门。双向门是必要条件，不是充分条件：仍要过 G-merge，仓库规则仍然优先。

- **双向门 + G-merge 全绿 + 仓库允许** → 自动合并、同步 main、关闭票。
- **单向门、拿不准、门禁红或规则阻止** → 停在开放 PR。报告门、证据、影响面与人类手动合并的
  确切动作。不合并、不同步 main、不再请求一次自动批准。由人类手动合并；本轮终点就是开放 PR。

## 6. 流程错误后的 retro

产品 bug 走打回。**流程错误**是可能复发的 harness 缺陷：worker 绕过角色边界、门禁接受了红
结果、同一原因连续两次派发失败、唤醒停摆、票型判错、scope 漂移、合并门误判，或同一门禁
反复打回。

出现时先保留证据，安全时继续本轮。到安全点后，只读地跑 `retro`：读它的 skill 文件，再读
一手来源——会话、worker transcript、`git`/PR 证据、台账与门禁结果。`retro` 通常是用户触发的，
因此把本轮对这条流程的请求视为只读分析的授权，**不**构成落地授权。没有 Skill tool 时直接读
`writing-for-agents` 的 skill 文件。把 `retro-candidates.md` 存在**目标仓库之外**，按严重度
排序。每个候选写清类别（导航、自动化检查、编码标准、AGENTS.md、工具经济、无效指令、
信息获取）、证据、要改的确切文件或检查、验证方式与风险。

把候选单交给人类。不要自动落地。人类选定候选后，派 worker 按正常门禁落地：对本 skill 仓库
意味着两个语言变体、对应 eval、测试与 README；对目标仓库意味着遵循它的约定。用 `pr` skill
写 PR，并为每个被接受的候选加一个 eval，防止缺陷静默回归。本轮仍在进行时，改进落地要等到
本轮终点；retro 绝不在运行中途修改 skill。

## 7. 回退与停止条件

| 条件 | 动作 |
| --- | --- |
| 票图不完整（有环、blocker 缺失、无验收、tracker 不可达） | 打回 G-tickets / `to-tickets`；不派发。 |
| 只有一张已定案的单票 | B 通道；一个 worker、一个 worktree。 |
| worker 无法证明隔离 worktree | 在它自己的工作区内串行跑 implementer；记录降级。 |
| worker 不能跑子代理 | 逐票 Orca worker，默认并发 3；记录回退。 |
| 集成 PR 是单向门 | 保持开放；由人类手动合并。 |
| 嵌套 worktree 残留或 main 被改动 | 保留现场、打回、不验收。 |
| worker 停摆或失联 | 按 worker-start / inbox 恢复参考处理；不重复派编辑者。 |
