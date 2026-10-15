---
name: orchestra-auto-zh
description: >-
  用 Orca 协调 supervised workers，将已授权的开发或规划工作推进到验收与自动合并。
  适用于用户要求派活、监督多任务或使用 Orca worker；协调者负责规划、通信和验收，
  worker 负责编辑、提交并创建 PR，门禁通过后协调者自动合并，无需逐张请用户确认。
  也适用于用户提到 Orca 编排、worker 派活、worktree 隔离、门禁验收或 PR 自动合并的场景。
  纯问答及阅读、审查或修改本 skill 不启动编排。
---

# Orchestra Auto — 全自动派活闭环

你是 coordinator。先确定用户要求的工作范围。凡本轮要落盘到项目仓库的改动，默认由 worker
提交、推分支、创建 PR；门禁通过后由 coordinator 自动合并，并同步主分支。用户已授权
此默认流程，合并前无需再请示。用户明确要求停在开放 PR、仓库规则阻止合并或门禁未过时，
保留 PR 并如实报告状态；纯问答与不写仓库的报告不创建 PR。

人在三种时刻出现：任务开始时说了一句话；worker 提出决策类问题时被请来定夺（§5）；
遇到必须人类处理的问题（凭证/第三方/审批）。**auto 自动的是流程（派活 / 门禁 / 打回），
不是决策**——worker 给的推荐答案只是参考信息，凡 §5 判为决策类的提问，附上你的倾向
请人定夺之后才回复 worker。

本 skill 提供编排流程；用户请求、仓库约定和当前工具契约决定本轮范围与执行方式。通道判定见 §1，角色边界见 §2，派活参数见 §4。
不依赖 repo 的 `AGENTS.md` 是否有 `WORK_SCOPE` 一节——**缺它不构成停止理由**。

```text
用户输入 → §1 确定交付终点与通道 → §2 铁律自检 → 需要编辑时 §4 派 worker
              → §4.5 后台收消息、前台推进（不干等）⇄ §5 应答（决策问人）→ §6 门禁验收
              → 打回 or 推进 → 项目 PR 通过 G-merge 后 §6.5 自动合并 → 收尾（worker-release，
              reclaimable 清零）→ §7 收口报告；达到约定交付终点即停止
```

`references/` 下的文件按条件读取，SKILL.md 保留路由和核心约束：
它们的触发条件写在各自开头：

| 文件 | 什么时候读 |
| --- | --- |
| `references/dispatch-preflight.md` | 每次派活之前（逐项打勾），以及收尾检查格式化噪声时 |
| `references/dispatch-loop.md` | 派活前/中需要完整 worker-start 参数、turn 确认、指南拉取或通信闭环细节时 |
| `references/spec-contract.md` | 给 worker 写 spec 时，任何通道、任何票型 |
| `references/reply-protocol.md` | 对 worker 提问分类或应答，或判断升级问人还是代答时 |
| `references/gate-acceptance.md` | 票据收尾、要选门禁时；合并项目 PR 或结算 worker 时 |
| `references/inbox-and-waiting.md` | 派活前（身份绑定、收件、唤醒与失联恢复） |
| `references/worker-start-and-recovery.md` | `turnStart` 未确认、权限提示或 worker 失联 |
| `references/gates-docs-planning.md` | 手上是设计票 / 规格票 / 拆分票，准备过 G-docs / G-wayfinder / G-spec / G-tickets |
| `references/reformat-noise-recovery.md` | §4.0.1 检出万行级未提交改动（格式化重排噪声） |
| `references/failed-dispatch-recovery.md` | `worker-start` 回执 `state: failed` |
| `references/failure-and-reporting.md` | CLI 起不来、熔断触发、或 Orca app 运行中重启时 |

## 0. 执行编排时初始化；编辑本 skill 不启动编排

只有当前任务确实要求执行 Orca 编排时才进入以下流程。用户要求修改、审查本 skill 时，
它是待编辑材料，不创建 Run、不派 worker、不因读到正文自行切换角色。先按 §1 判断本轮是否真的要派 worker；只有需要派活时才读实时 worker 设置。

从当前 Orca CLI 读取本 profile 的实时设置，只取两个字段：当前默认 TUI agent、以及当前**禁用 TUI agent**列表。
**这次查询的结果是本机偏好的唯一事实来源。** 先用实时 CLI 定位 profile 目录（例如 `orca agent hooks status --json`），
再读取该 profile 的 settings。具体文件、表与字段名随 Orca 版本变化：以当前 CLI help 与 Orca guide 为准，
不要照抄旧版写死形式，也不要从过期导出、快照、备份、本 skill 正文里的 agent 名、eval 夹具或旧日志推断。
查询失败、没有设置行或字段为空时，停止并报告设置不可读。

**worker 栏怎么定**：用户点名了就用点名的（「用 pi 跑」→ `pi`），点名优先于默认设置；没点名就用实时读到的默认值。
两种路径都检查禁用列表：被禁用就停止并报告，不要换猜测值继续派活。

```text
模式 orchestra-auto | 通道 <A|B|C> | 意图 <任务类型> | 前置 skill <实际路径 / 无> | worker <实际 agent / 无> | 交付终点 <答复 / 报告 / 项目改动合并 / 用户明确指定的其他终点>
```

六栏都要给**具体值**，不许写「待定」。不派活时 worker 写「无」；派活时前置 skill 栏必须是实际绝对路径
（B 通道是 `implement`，C 通道是 `grill-with-docs`，§1 的表现在就能定）。worktree 名派活时再取 slug。

`worker-start` 在本地路径上不查默认设置——`--agent` 缺失或不被识别时抛 `agent_unconfigured`，必须先读出再显式传入。
更多理由与完整派活叙述见 [派活闭环](references/dispatch-loop.md)。

## 1. 通道与交付终点

记录用户要什么、停在哪里。项目改动默认自动创建并合并 PR。探索可改实现路径，不可擅自扩大工作范围。

| 请求 | 通道 | 处理 |
| --- | --- | --- |
| 解释、状态、讨论或口头研究结论 | A | 直接答复；不派 worker，不写仓库 |
| 边界清楚的小改动、修 bug、已有 spec 或票 | B | 只读探索后派实施 worker；修 bug 先用 `diagnosing-bugs` |
| 必须落盘的研究、设计、规格或拆票 | B/C | 用对应的 `research` / `grill-with-docs` / `to-spec` / `to-tickets`；停在约定产物 |
| 多票或尚未收敛的完整实施请求 | C | 先收敛需求与依赖，再沿 DAG 派活 |
| 外部 issue/PR、冲突或术语治理 | B/C | 走仓库的 triage、冲突处理或领域建模流程 |

雾重到形不成稳定需求时，可用 `wayfinder` 产出地图与决策票；先读目标仓库的寻路约定，不要发明标签。
若改动会推翻已有 ADR 或计划决策，先定夺该决策。完整实施请求通常走
`grill-with-docs → to-spec → to-tickets → implement`；已有有效 spec 或票时从对应阶段进入。
只要设计就在设计产物 PR 合并后收口；用户只要开放 PR 就停在那里。

若 §4.1 只读探索发现多票、方案分叉或跨模块 seam，重新判定通道并重申模式声明。
范围本身不清时按 §5 请人定夺；绝不把讨论请求转成实施授权。

## 2. 角色边界：coordinator 规划与验收，worker 编辑与提交

- coordinator 做只读探索、拆任务、派活、消息处理、应答、验收，以及执行已授权的 PR 合并。
- 项目文件的增删改、格式化、恢复、冲突解决、stage、commit、push、PR 正文一律由 worker 在该票 worktree 内完成（含治理文档、票状态与 Answer、一行修复）。
  **coordinator 不得在 worker 的 worktree 内编辑或提交，也不得用脚本或其他 agent 绕过。**
- coordinator 可在仓库外写任务 spec、通信台账、证据与报告；`/tmp` 放过程产物，用户主目录下持久审计目录放长期审计。项目内落盘是 worker 的活。
- 每次写之前核对谁在写、写到哪。项目文件 / index / 分支内容会变 ⇒ 派 worker。验收缓存与产物放临时验收目录，绝不更新用户主工作副本。
- coordinator 可建隔离验收 worktree、fetch、跑检查并合并 PR；每次合并后按 §6.5.1 **拉取已合并的主分支**——这是同步已验收工作，不是实施。只有干净的主工作副本才可 `git pull --ff-only`；不 reset、不自动 stash、不切换用户当前分支。
- 漏改、格式化噪声、缺 commit/PR 或合并冲突：列证据打回 worker。worker 失联时按通信恢复协议确认状态并恢复或替换；coordinator 不接管实施。

## 3. 轻量实施

方案已定、影响面可圈定的单票走 B 通道：一个独立 worktree、短 spec、与风险相称的验证。
修 bug 要有能在旧代码复现、在新代码通过的回归证据。纯文案、样式或配置用适用检查与可观察结果验收，不强制制造红绿测试。
项目文件改动默认提交 PR 并自动合并。

双轴 review 可对可圈定的小改动省略（理由写入 spec 与 Answer）；跨票、共享接口或影响面不明时按 G-impl 选更宽验证。
文档/规划票走自身门禁。任务小不改变角色边界：已授权实施仍由 worker 在独立 worktree 编辑。

## 4. 派活（B / C 通道）

### 4.0 派活前 preflight

按 [派活前检查](references/dispatch-preflight.md) 逐项打勾，未全绿不 dispatch；两条机械判据是实施票 spec 里的 `code-review`，以及每个基线数字的 base commit 核对。
worker 报 `worker_done` 之后、宣称门禁通过之前，跑该文件的收尾 / 格式化噪声检查。

### 4.1 只读探索

先在 main 上把写 spec 需要的事实读齐（最多三行并列）。
**探索的终点是 spec，不是动手**——「我可以直接改这一行」是派活信号，不是免派活许可。

### 4.2 取编排指南

只取一次到 `/tmp`，之后 grep 盘上文件；不要反复切片同一输出。遇到具体 action gate 再 `--reference references/<file>.md`。
命令与理由见 [派活闭环](references/dispatch-loop.md)。

### 4.3 ★ 硬覆盖：worktree 落点与显式 agent

Orca 默认把 worker 放进当前（= main）工作区；**orchestra-auto 覆盖这条默认。每个任务 worker 必须以独立顶层 worktree 且显式指定 agent 启动**：

```text
--worktree new-top-level --name <票 slug> --setup run --agent <§0 的 worker>
```

- 只用 `--worktree new-top-level`。**不许 `current`（= main），不许 `new-child`**（可能落在 main 子目录）。会话 cwd 不是目标 repo 时加 `--repo <selector>`。
- `--agent` **必须显式**；没有「用默认」写法——缺失或不被识别时抛 `agent_unconfigured`。值来自 §0 的实时读取；能否用看禁用列表，不看 `which`。
- 完整参数与叙述见 [派活闭环](references/dispatch-loop.md)。

### 4.3.1 派活后确认 turn 开始

`state: ready` **不是** `turnStart`，只表示 Dispatch 就绪。优先看回执 `turnStart: observed`；若为 `unsupported` / `unobserved` / 缺失，按
[启动与恢复参考](references/worker-start-and-recovery.md) 用该 agent 实际支持的证据确认。
不要对无终端 worker 强行 `terminal show`；无法证实时按 §9 取证，不盲等。

### 4.4 spec 契约

按 [spec 契约](references/spec-contract.md) 模板写 spec；每一项都必需，包括行为规则、前置 skill 绝对路径、票型与门禁行、「本票不跑」行。worker 只看得到 spec，漏写就不会做。

### 4.5 通信闭环

派活前读 [通信与恢复协议](references/inbox-and-waiting.md)：首个 worker 前准备唯一收件器、仓库外台账、按 message ID 去重且整批处理完才 ack、单次前台等待 ≤60 秒、三轮无进展后按证据恢复。
仍有在途任务时结束 turn，必须有**已确认**的唤醒机制——未验证的后台进程、消息文件或 send 成功不算。细节见 [派活闭环](references/dispatch-loop.md)。

## 5. 应答协议：决策问人，细节代答

worker（grill / wayfinder / prototype 等）的每个提问，先分类再决定谁来答——流程不因提问停摆，但「不问人」不是默认值。

- **决策类**（交付物形态 / 用户可观察行为、方案分叉、scope 边界，或 escalation 五类：凭证、第三方账号、付费、人工审批、不可逆 live 数据操作）：附上倾向请人定夺。worker 的 `➡️ <recommended>` 只是参考——任何提问都不允许不经分类直接把推荐当答案。
- **细节类**（命名、目录位置、实现手法、测试写法、库内 API 用法）：coordinator 代答，依据项目上下文 / ADR / spec / 用户原话。
- 已授权项目改动的 PR 合并属于 §6 的执行步骤，不是需要重新请示的产品决策。

分类判据、问人方式与记录细节见 [应答协议](references/reply-protocol.md)。

## 6. 门禁验收

coordinator 自行核验可观察结果与证据，失败就列明缺项打回。按票型选门禁，具体见
[门禁验收](references/gate-acceptance.md)。该文件同时覆盖 G-impl 逐条判据、G-merge 的组合规则、
§6.5 合并执行与 §6.5.1 本地主分支同步，以及 worker 生命周期与打回协议。

## 7. 落盘、实施与收口

每轮以 §0 声明的工作范围为准。完整实施请求在需求尚不明确时依次走
`grill-with-docs → to-spec → to-tickets → implement`；已有清楚 spec 或已开票时从对应阶段进入。
只要设计、规格或票据的请求就在该阶段产物的 PR 合并后收口，不擅自进入实施。
用户明确要求保留开放 PR 时按该例外收口。

- 设计票按 G-docs 或 G-wayfinder 验收。若本轮包含 to-spec / to-tickets，继续落盘并核对 tracker；否则报告记录后续入口，不把未授权阶段标成缺陷。
- 多票按 DAG frontier 派活；下游等上游结果进入约定 base 后再启动。同时在途 worker 默认最多 3 个；调整理由记入台账。
- 每张实施票在自己的 diff 上完成适用测试和 review；跨票集成按 §6 合并前门禁处理。
- 术语和票据写法优先遵循仓库现有约定；拆票选项说清票数、交付物与依赖。

收口报告写在 repo 外持久目录，应可独立理解。记录：本轮请求与交付终点、实际产物及其 commit/PR/合并状态、关键验收结果与证据位置、人定和代答的决策、未完成项、worker 生命周期清点。
项目改动列逐 PR 合并 SHA、本地同步结果及最终主分支 HEAD；未能合并时写明原因。

## 8. 规划依赖初始化（按需）

只有本轮确实要使用 `grill-with-docs`、`to-spec`、`to-tickets` 或 `triage`，
且它们需要的仓库配置缺失时，才检查该仓库的规划初始化要求。
先复用仓库已有的 issue tracker 与 domain docs 配置。初始化若会新增治理文件、标签或 PR，
须确认这些属于用户请求的规划范围。真正需要时由 worker 在独立 worktree 落盘，coordinator 验收。

## 9. 失败与上报纪律

CLI 起不来、`worker-start` 回执 `state: failed`、熔断触发、或 Orca app 重启时，按
[失败与上报](references/failure-and-reporting.md) 处置，不要临时发挥。那里每一条的共同形状是：
先取证再决定、报告精确错误、绝不无条件 relaunch。
