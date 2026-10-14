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
| `references/spec-contract.md` | 给 worker 写 spec 时，任何通道、任何票型 |
| `references/gate-acceptance.md` | 票据收尾、要选门禁时；合并项目 PR 或结算 worker 时 |
| `references/inbox-and-waiting.md` | 派活前（身份绑定、收件、唤醒与失联恢复） |
| `references/worker-start-and-recovery.md` | `turnStart` 未确认、权限提示或 worker 失联 |
| `references/gates-docs-planning.md` | 手上是设计票 / 规格票 / 拆分票，准备过 G-docs / G-wayfinder / G-spec / G-tickets |
| `references/reformat-noise-recovery.md` | §4.0.1 检出万行级未提交改动（格式化重排噪声） |
| `references/failed-dispatch-recovery.md` | `worker-start` 回执 `state: failed` |
| `references/failure-and-reporting.md` | CLI 起不来、熔断触发、或 Orca app 运行中重启时 |

## 0. 执行编排时初始化；编辑本 skill 不启动编排

只有当前任务确实要求执行 Orca 编排时才进入以下流程。用户要求修改、审查本 skill 时，
它是待编辑材料，不创建 Run、不派 worker、不因读到正文自行切换角色。

先按 §1 判断本轮是否真的要派 worker。只有需要派活时才读实时 worker 设置；纯问答或纯报告不依赖该设置。用户点名优先于默认值；禁用项仍须检查。

从当前 Orca CLI 读取本 profile 的实时设置，只取两个字段：当前默认 TUI agent、以及当前被禁用的 TUI agent 列表。
**这次查询的结果是本机偏好的唯一事实来源**：

- 先用实时 CLI 定位 profile 目录（例如 `orca agent hooks status --json` 报出的设置路径），
  再读取该 profile 的 settings 文档，取默认 TUI agent 与禁用 TUI agent 列表。
- 具体的文件、表与字段名是**随 Orca 版本变化的实现细节**：以当前 CLI help 与当前 Orca
  skill guide 为准，不要照抄旧版本写死的形式。若你打算使用的命令与当前公开文档不一致，
  不要猜，带证据通过 `ask` 提出。
- 不要从过期导出文件、旧快照、同目录的备份文件、技能正文里的具体 agent 名称、eval
  夹具或旧日志推断当前默认值或禁用列表。本文中带日期的本机观察只描述当时行为，不是当前设置。

用户没点名 worker 时，照当前读到的默认值填 worker；用户点名时按点名选择。两种情况都要检查本次读到的禁用列表：
被禁用就停止并报告，不要换一个猜测值继续派活。查询失败、没有设置行或关键字段为空时，也停止并报告设置不可读。

```text
模式 orchestra-auto | 通道 <A|B|C> | 意图 <任务类型> | 前置 skill <实际路径 / 无> | worker <实际 agent / 无> | 交付终点 <答复 / 报告 / 项目改动合并 / 用户明确指定的其他终点>
```

六栏都要给**具体值**，不许写「待定」。不派活时 worker 写「无」；派活时前置 skill 栏必须是那个 skill 的实际绝对路径——
写「待定」等于把最需要当下定下来的那件事推给未来的自己，而实测表明这一步一推就再也
捡不回来了（B 通道是 `implement`，C 通道是 `grill-with-docs`，§1 的表现在就能定）。
worktree 名派活时再取 slug，不属于交付终点。

**worker 栏怎么定**：用户点名了就用点名的（「用 pi 跑」→ `pi`），**点名优先于默认设置**——
用户明确要的东西永远压过本机偏好。没点名就跑上面的读取，读到什么用什么；两种路径都受实时
禁用列表检查约束。

为什么跟随 Orca 设置而不是写死：worker 的 harness 是本机偏好，写死之后用户换了默认 agent，
skill 还在派旧的那个，而这类偏差只在「worker 行为不对」时才暴露，那时已经烧掉一轮派活。
还有一个更直接的理由——`worker-start` 在本地路径上**不查**这个设置：agent 缺失或无法识别时
它直接抛 `agent_unconfigured`，没有「不传 `--agent` 就用默认」这回事；那个默认只服务 GUI
composer 路径。也就是说 **CLI 派活时唯一的取值途径就是先读出来再显式传**。取值决定
`--agent` 与 §4.3.1 要盯的横幅字符串，两处都在派活时立刻要用（对照表在 §4.3）。

设置读不到，或 `worker-start --help` 与 Orca 命令注册表都无法确认该 agent → 按 §9 报告并停，
**不要猜，也不要顺手派一个没验证过的 harness**：没有可用的启动判据时，§4.3.1 就会退化成
「凭感觉看标题」。agent 已被 Orca 识别但尚无表项时，按上面的取证步骤确认后再派活并补表。

**判断能否派活要读实时设置**：所选 agent 必须被 `worker-start --help` 识别，并且不在本次查询的
禁用列表中。§4.3 的表记录各 agent 的启动/标题判据，不是默认值或禁用状态的来源。
若所选 agent 尚无表项，先核对 `worker-start --help`、Orca agent 注册表中的
working / permission / idle 标签，以及实时禁用列表。确认被 Orca 支持且未禁用后照常派活；
启动判据优先使用回执提供的 `turnStart: observed`，否则按 §4.3.1 观察实时标题，并将验证到的形态补入表。

## 1. 通道与交付终点

先记录用户要求的工作内容与停止位置；项目改动默认自动创建并合并 PR。探索可改变实施路径，不能扩大工作内容。

| 请求 | 通道 | 处理 |
| --- | --- | --- |
| 解释、状态、讨论或仅需口头研究结论 | A | 直接回答；无 worker、无写入 |
| 明确的小改动、修 bug、已有 spec 或票 | B | 只读探索后派实施 worker；修 bug 先用 `diagnosing-bugs` |
| 要落盘的研究、设计、规格或票据 | B/C | 使用相应 `research`、`grill-with-docs`、`to-spec`、`to-tickets`；到指定产物为止 |
| 多票或方案未定的完整实施请求 | C | 先收敛需求和依赖，再按 DAG 派实施 worker |
| 外部 issue/PR、冲突或术语治理 | B/C | 使用仓库可用的 triage、冲突处理或 domain-modeling 流程 |

fog 重、尚不能形成稳定需求时，可用 `wayfinder` 产出 map 和决策票；先读目标仓库的
Wayfinding 映射，缺失时不要自造标签。改动会推翻既有 ADR 或计划决断时，先处理该决策。
完整实施请求通常经历 `grill-with-docs → to-spec → to-tickets → implement`，
但已存在有效 spec/票时从相应阶段进入。只要求设计时，在设计产物的 PR 合并后停止，
不自动进入实施；明确要求只交开放 PR 时按该例外停止。

§4.1 的只读探索若发现多票、方案分叉或跨模块 seam，应重判通道并重述模式声明。
范围本身不清楚时按 §5 提请用户决定；不得把讨论请求转成实施授权。

## 2. 角色边界：coordinator 规划与验收，worker 编辑与提交

- coordinator 负责只读探索、任务拆分、派活、收发消息、回答问题、运行验收和执行已授权的 PR 合并。
- 所有项目文件的新增、修改、格式化、还原、冲突解决、暂存、commit、push、PR body 编写，
  都交给 worker 在该票 worktree 内完成；包括治理文档、票据 Status/Answer 和一行修补。
  **禁止 coordinator 到 worker worktree 代改、代提交，也禁止用脚本或其他 agent 绕过此边界。**
- coordinator 可以在 repo 外写任务 spec、通信台账、证据、报告；`/tmp` 用于过程产物，
  用户主目录下的持久审计目录用于长期留档。项目内落盘由 worker 完成。
- 每次写操作前检查执行者和写入目标。项目文件、index、分支内容会改变 ⇒ 派 worker；
  验收产生的缓存/产物放临时验收目录，不更新用户 main 工作副本。
- coordinator 可创建隔离验收 worktree、fetch、运行检查、合并 PR，并在每次合并后
  按 §6.5.1 **拉取已合并的主分支代码**。这是同步已验收成果，不是自行实现或创建提交。
  仅允许干净主工作区的 `git pull --ff-only`；不 reset、不自动 stash、不切换用户当前分支。
  合并后的验证可在临时 worktree checkout 对应远端 main commit，以隔离缓存与测试产物。
- 发现漏改、格式化噪声、缺 commit/PR 或合并冲突：列出证据并打回 worker。worker 失联时
  按通信恢复协议确认状态、恢复或更换 worker，coordinator 不接手实现。

## 3. 轻量实施

单票、方案已定、影响面可圈定的改动走 B：一个独立 worktree、简短 spec、与风险相称的验证。
修复类要有能在旧代码复现、在新代码通过的回归证据。纯文案、样式或配置改动用适用的
检查与可观察结果验收，不强制制造红绿测试。项目文件改动默认提交 PR 并自动合并。

双轴 review 可对可圈定的小改动省略，理由写入 spec 与 Answer；跨票、共享接口或影响面
不明时按 G-impl 选择更宽的验证。文档/规划票走自身门禁，不套用源码测试。
任务小不改变已授权实施工作由 worker 在独立 worktree 编辑的角色边界。

## 4. 派活（B / C 通道）

### 4.0 派活前 preflight

按 [派活前检查](references/dispatch-preflight.md) 逐项打勾，未全绿不 dispatch。其中两条机械判据——
实施票 spec 里必须出现 `code-review`、以及每个基线数字都要核过 base commit——才是真正抓住
错误的那些。

### 4.0.1 收尾时的格式化噪声

worker 报 `worker_done` 之后、宣称门禁通过之前，按
[派活前检查](references/dispatch-preflight.md) 跑收尾检查。

### 4.1 只读探索

先在 main 上把写 spec 需要的事实读齐（最大 3 行，三行并列）。

**探索的终点是 spec，不是动手。** 一旦心里冒出「我可以直接改这一行」——那正是要派活的信号，
不是免派活的许可。

### 4.2 取编排指南（只取一次，存盘）

```bash
<ORCA> skills get orchestration > /tmp/orchestration-guide-<repo>.md
```

之后 grep 盘上文件。不要反复 `head -120` / `sed -n '250,420p'` 翻同一个输出——那会白白烧掉
几十次工具调用（实测有会话为此花掉几十次 bash）。只存在 `/tmp`（§2）。遇到具体 action gate
时再 `--reference references/<file>.md`。

### 4.3 ★ 覆盖 Orca 的默认落点（本 skill 最关键的一条）

**Orca 默认把 worker 放进当前（= main）工作区**——「A fresh worker means a fresh agent
terminal, **not** a new Git worktree」。这与 §2 的铁律直接冲突，**orchestra-auto 明确覆盖
Orca 的这条默认**。

**项目绑定来自调用方 Orca 上下文，不是 shell 的 cwd。** coordinator 通常就站在目标 repo 里；
但若会话 cwd 与目标 repo 不同（对 fixture、对另一个仓库派活），必须显式加 `--repo <selector>`，
否则 worktree 会被建到 cwd 所属项目里去。这条是实际派活时踩出来的。

每个任务 worker 一律：

```bash
<ORCA> orchestration worker-start --spec "<spec>" \
  --worktree new-top-level --name <票 slug> --setup run --agent <§0 的 worker> --json
```

- `--worktree new-top-level`：独立顶层 worktree，从仓库默认 base ref 切。
  **不许 `current`，不许 `new-child`**——前者就是 main，后者可能落在 main 的子目录里。
- `--name`：用票 slug，方便事后认领与打回时定位。
- `--agent <§0 的 worker>`：**必须显式写，没有「用默认」的写法**——`worker-start` 在 `--agent`
  缺失或不被识别时直接抛 `agent_unconfigured`，它不查默认 TUI agent（那个默认只服务于
  GUI composer 路径）。所以这一栏不能省，但它的**值**来自 §0 的 worker 栏。

  不同 agent 的标题、权限提示和 TUI 恢复判据见 [启动与恢复参考](references/worker-start-and-recovery.md)；仅在回执未确认 turn 开始或遇到交互提示时读取。

- 判断某个 agent 能不能用，以 §0 查询到的实时**禁用列表**为准，而不是 `which`；
  Orca 可能识别某个 agent，但当前 profile 仍将它禁用。实时设置查询是唯一的配置判据；本表中的
  带日期的观察只用于解释已验证的启动行为，不能用来推断当前默认值或可用性。
- `--spec` 一次成型（`worker-start --spec` 会同时建 Task 与 attempt）。只有在多票有依赖、
  需要计划式 fan-out 或重试已知 Task 时才用 `task-create` + `worker-start --task <id>`。
- 回执拿到后**立刻**走 §4.3.1 确认 turn 真的开始，并核验 §4.5 的收件器与等待方式。

### 4.3.1 派活后确认 turn 开始

`state: ready` 仅表示 Dispatch 就绪。优先看回执 `turnStart: observed`；若为
`unsupported`、`unobserved` 或缺失，读取[启动与恢复参考](references/worker-start-and-recovery.md)
并用该 agent 实际支持的证据确认开始。Orca 允许无终端 worker，先看 `worker-show` 的句柄，
不能对无终端 worker 强行使用 `terminal show`。无法证实时按 §9 取证，不进入盲等。

### 4.4 spec 契约

按 [spec 契约](references/spec-contract.md) 里的模板写 spec；那里的每一项都是必需的，包括行为规则、
前置 skill 绝对路径、票型与门禁行、以及「本票不跑」行。worker 只看得到 spec，你漏写的，
它就不会做。

### 4.5 通信闭环：入队、收件、处理、唤醒分别核验

派活前读 [通信与恢复协议](references/inbox-and-waiting.md)。每个 Run 维护一份 repo 外台账：
Run/coordinator handle、Task/Dispatch/worker handle/worktree、最后进展、消息 ID、处理状态、
完成回执、PR、下一次检查时间。上下文压缩或恢复后先读台账与真实 Orca 状态，不凭旧对话猜身份。

- 首个 worker 启动前准备唯一收件器与等待方式；每次派活后核验 turn 已开始并检查收件器。
- 每个 Run 一个后台收件器，绑定真实 coordinator handle；消息按 deliveryId 原子保存，
  重启不覆盖、不轮转删除未处理证据。脚本不提供 agent 唤醒能力。
- 每条消息按 message ID 去重，验证 Run/Task/Dispatch。处理整批及所需终端归属决定后才 ack。
  当前批次被人类决策阻塞时用只读 `check --all` 检查后续消息，及时处理其他 worker；
  不能把 ack 当回复，也不能从另一次 check 抽取一个未审阅的 deliveryId 来 ack。
- 长操作结束后与空闲时都收件。单次前台等待不超过 60 秒；连续三轮没有进展便查
  worker-list/worker-show/worker-read、队列与本地台账，按证据恢复，不能无限盲等。
- 除环境强制结束的例外外，主动结束仍有在途任务的 coordinator turn 前必须有**已确认能触发下一 turn 的通知机制**。未验证的后台进程、
  消息文件或 send 成功不算。没有自动唤醒时保持当前 turn 有界轮询；环境必须交还控制权时，
  明确说明尚在运行、不能自动唤醒和恢复入口，不声称会自动继续，不默认要求用户定期催促。
- worker 缺 worker_done 或已 idle 的恢复、错误与停止条件，按 reference 执行。

## 5. 应答协议：决策问人，细节代答

worker（grill / wayfinder / prototype 等）的每个提问，先分类再决定谁来答。
本 skill 的核心仍在：让流程不因提问停摆——但「不问人」不再是默认值。
已授权项目改动的 PR 合并属于 §6 的执行步骤，不是需要重新请示的产品决策；
只有合并会改变用户指定范围或需要额外外部授权时，才按本节升级。
grilling 格式里的 `➡️ <recommended>` 只是 worker 的一条参考信息：**任何提问都不允许
不经分类直接把推荐当答案。**

### 5.1 分类判据（逐条对照；满足任一即决策类）

1. **影响交付物形态或用户可观察的行为**：产品方向、需求取舍、UI / 文案 / 交互的可见取舍。
2. **方案分叉**：多个可行实现路径，选型影响架构、依赖、seam 或后续票的划分。
3. **scope 边界**：某功能做不做、Out of Scope 放什么、验收标准宽严。
4. **原 escalation 五类**：凭证、第三方账号、付费、人工审批、不可逆 live 数据操作——
   这类跳过其余判据，立即停下，把问题原样转给人类，等人工答复再继续。宁可多停，不可代答。
   **「停」的是这条 worker，不是整个 run**：多票并行时，escalation 冻结出事的那张票，
   其余票照常推进门禁——一张票的凭证问题不该冻结整条流水线。全局冻结只发生在 §6
   打回协议的 run 级熔断触发时。

四条都不沾——只涉及命名、目录位置、实现手法、测试写法、库内 API 用法等——才是**细节类**，
由你代答（§5.3）。自检同 §3：写不出「它为什么不沾这四条」，就当决策类处理——
理由写不出，分类就不成立。

注意方向与旧版相反：旧版把「需求不清楚 / 拿不准用户想要哪个方案」列为永不问人、必须自裁；
**现在这类恰恰是判据 1 / 2 覆盖的决策类，必须问人。**用户明确要求「不能都按推荐直接回答」
——决策类问人是目标行为，不是打断。

### 5.2 决策类：附倾向请人定夺

暂停回复 worker，先把三样东西摆给人：

- worker 的原问题（含它给的推荐与理由，若有）；
- 你的倾向与一句理由（依据项目上下文 / ADR / spec / 用户原话）；
- 其余选项的一句话代价。

人确认或改选后，才用 `reply --id <原 message_id> --body <答案>` 回复 worker。人的选择与你不同时以人为准，
不二次游说；确有强烈技术理由可以说一次，人不改就按人的走。worker 的 ask 是阻塞的——
它等你答了才继续，所以一次把问题说清，减少来回。

### 5.3 细节类：coordinator 代答

用项目上下文、ADR、spec、用户原话做依据，选最贴近用户已表达意图与现有架构的选项；
worker 的推荐与依据不冲突时照推荐答，冲突时在应答里说明为何弃推荐。理由写进应答。

### 5.4 记录（两类都要）

在任务线程（或 Answer 的 Decisions 小节）追加 `Q → A（人定 / 代答）→ 一句理由`；
问人的把人的选项要点也记下。§7 报告汇总这份审计清单，人可事后推翻任何一条代答。

### 5.5 应答通道

应答走同一 orchestration 通道回（`reply`），不引入其他工具回 worker。
问人用本会话的提问通道——这是 coordinator 侧唯一被允许且被要求的提问动作；worker 侧的禁令不变（§4.4 BEHAVIOR RULE 1）。

## 6. 门禁验收

coordinator 自行核验可观察结果与证据，失败就列明缺项打回。按票型选门禁，具体见
[门禁验收](references/gate-acceptance.md)。该文件同时覆盖 G-impl 逐条判据、G-merge 的组合规则、
§6.5 合并执行与 §6.5.1 本地主分支同步，以及 worker 生命周期与打回协议。

## 7. 落盘、实施与收口

每轮以 §0 声明的工作范围为准。完整实施请求在需求尚不明确时依次走
`grill-with-docs → to-spec → to-tickets → implement`；已有清楚 spec 或已开票时从对应阶段进入。
只要设计、规格或票据的请求就在该阶段产物的 PR 合并后收口，不擅自进入实施。
用户明确要求保留开放 PR 时按该例外收口。

- 设计票按 G-docs 或 G-wayfinder 验收。若本轮包含 to-spec / to-tickets，继续落盘并核对 tracker：
  需求锚点标签与状态符合仓库约定，实施票已创建，依赖关系可查询。若本轮不包含这些阶段，
  报告明确记录后续入口，不把未授权阶段标成缺陷。
- 多票按 DAG frontier 派活；有依赖的下游票等上游结果进入约定 base 后再启动。
  同时在途 worker 默认最多 3 个；若资源、配额或任务独立性不同，可在台账中记录调整理由。
- 每张实施票在自己的 diff 上完成适用的测试和 review；跨票集成按 §6 的合并前门禁处理。
  相同字段或接口跨调用点修改时，Answer 清点所有相关位置与处理结果。
- 术语和票据写法优先遵循仓库现有约定。拆票选项说清票数、每票交付物及依赖，
  避免未定义的简称。

收口报告写在 repo 外持久目录；报告本身应可独立理解，不依赖 /tmp 长期存在。记录：
本轮请求与交付终点、实际产物及其 commit/PR/合并状态、关键验收结果与证据位置、
人定和代答的决策、未完成项、worker 生命周期清点。项目改动列逐 PR 合并 SHA、
本地同步结果及最终主分支 HEAD；未能合并时写明原因。只有用户明确要求停在开放 PR，
或仓库规则/门禁阻止合并时，开放 PR 才是本轮终点。

## 8. 规划依赖初始化（按需）

只有本轮确实要使用 `grill-with-docs`、`to-spec`、`to-tickets` 或 `triage`，
且它们需要的仓库配置缺失时，才检查该仓库的规划初始化要求。
先复用仓库已有的 issue tracker 与 domain docs 配置。初始化若会新增治理文件、标签或 PR，
须确认这些属于用户请求的规划范围；不因运行本 skill 就自动改动无关配置。
初始化实际需要时，由 worker 在独立 worktree 落盘，coordinator 负责验收。

## 9. 失败与上报纪律

CLI 起不来、`worker-start` 回执 `state: failed`、熔断触发、或 Orca app 重启时，按
[失败与上报](references/failure-and-reporting.md) 处置，不要临时发挥。那里每一条的共同形状是：
先取证再决定、报告精确错误、绝不无条件 relaunch。
