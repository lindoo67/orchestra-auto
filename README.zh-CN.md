# orchestra-auto

用 Orca 协调 supervised workers，把已授权的开发或规划工作推进到验收与自动合并的一套工作流。

本仓库发布**两个可安装的 Agent Skill**，同一套流程、两种语言：

| Skill | 语言 | 安装 |
| --- | --- | --- |
| [`orchestra-auto`](skills/orchestra-auto/SKILL.md) | English | `npx skills add whutlichao/orchestra-auto --skill orchestra-auto` |
| [`orchestra-auto-zh`](skills/orchestra-auto-zh/SKILL.md) | 简体中文 | `npx skills add whutlichao/orchestra-auto --skill orchestra-auto-zh` |

英文说明见 [README.md](README.md)。

> **Orca 专用前提。** 两个 skill 都驱动 **Orca CLI**（`orca orchestration …`）。它们不是通用的
> agent 编排层，未安装 Orca 或 CLI 不可达时无法工作。安装前请先读
> [前提与能力边界](#前提与能力边界)。

## 它做什么

coordinator 负责规划、通信与验收；worker 负责编辑、提交与创建 PR。门禁通过后由 coordinator
合并——不再逐张票据请人确认。完整票图交给一个长程 `implement-spec` worker：它让 implementer
在各自 worktree 实施，合入 integration branch，只开一个集成 PR。PR 的 Merge Danger 决定最后
一步：双向门在 G-merge 通过后自动合并，单向门保留给人类手动合并。流程错误（不是产品 bug）
产出只读 retro 候选单，由人类选定后 worker 再落地。

skill 不会拿来交换的安全不变量：

- **隔离**：每个 worker 都有自己的顶层 worktree；长程 worker 的嵌套 implementer 各有自己的
  worktree 与分支；coordinator 绝不在 worker 的 worktree 里编辑或提交，也绝不在主工作副本上这么做。
- **真实启动证据**：`state: ready` 不等于 turn 已开始；skill 要求按 agent 取得实际证据（或回执的
  `turnStart: observed`）。
- **实时 worker 设置**：worker harness 来自 Orca 的当前设置，并与当前禁用列表比对——不凭习惯、
  不读过期快照。
- **消息身份**：投递按 delivery ID 原子落盘、按 ID 去重，且只有在整批处理完之后才 ack。
- **决策问人**：范围、方案分叉与 escalation 五类（凭证、第三方、付费、人工审批、不可逆
  live 数据操作）绝不代答。单向 Merge Danger 门也必须由人类合并，不自动合并。
- **门禁按票型**：设计票不跑源码测试；实施票不跳过自己的 review。
- **先验收后合并**：合并等门禁；异常 diff 先留证，再谈处理。门要用 diff 核对，不能只信 PR 正文。
- **流程错误留痕**：retro 候选单存在目标仓库之外，经人类选定后才由 worker 落地。
- **失败有停止阈值**：有界重试、单票熔断与 run 级熔断。
- **生命周期收尾**：已结算 worker 被 release、retain 或派 follow-up Task——没有静默遗弃。

## 全流程（端到端）

四个面板，按顺序读就是完整流程。蓝色是流程步骤，橙色菱形是判定，紫色是要人来定夺的地方，绿色是本轮
终点或某条恢复流程的起点，红色是失败与打回，淡色底框是下一步之前必须全绿的打勾清单。

### 1 · 把 worker 派起来（§0–§4.4）

用户一句话的请求，要变成一个跑在独立顶层 worktree 里的 worker。没有 turn 启动证据，下面任何一步都到
不了。

```mermaid
%%{init: {"themeVariables": {"fontSize": "14px"}, "flowchart": {"nodeSpacing": 18, "rankSpacing": 22, "padding": 6, "diagramPadding": 4, "useMaxWidth": true}}}%%
flowchart TD
    START["用户用一句话提出本轮请求"] --> DECL["§0 六栏声明：模式 / 通道 / 意图 / 前置 skill 绝对路径 / worker / 交付终点——不许写「待定」"]
    DECL --> CH{"§1 这个请求走哪条通道？"}
    CH -->|"A——解释、状态、讨论、口头研究结论"| ANS["直接答复：不派 worker、不写仓库"]
    ANS --> DONE_A["没有要派的话，也没有要合并的东西"]
    CH -->|"B——边界清楚的小改动、修 bug、已有 spec 或票"| SCOUT["§4.1 在 main 上做只读探索——终点是 spec，不是动手"]
    CH -->|"C——多票、或需求尚未收敛的完整实施"| CONV["§1 先收敛需求与依赖：grill-with-docs、to-spec、to-tickets；G-tickets 验收票图后，一个长程 implement-spec worker"]
    CONV --> PLAN8["§8 本轮真正需要的规划配置，由 worker 在独立 worktree 落盘、coordinator 验收"]
    PLAN8 --> HARD
    SCOUT --> HARD
    HARD["§2 铁律自检：凡项目文件写入都归 worker 在其 worktree 内完成——绝不写主工作副本，绝不写 worker 的 worktree"]

    HARD --> PF
    subgraph PF["§4.0 派活前检查——逐项打勾，未全绿不 dispatch"]
        P1["CLI 存活，编排指南已落盘"]
        P2["通道与票型已定，票型和门禁是 spec 里的一行"]
        P3["spec 完整：BEHAVIOR RULE 与前置 skill 路径，Target / Change / Constraints / Ownership / Observable acceptance"]
        P4["落点显式：new-top-level、票 slug、选定的 agent"]
        P5["spec 里每个基线数字都出自本票的 base commit"]
        P6["实施票写明 code-review，除非 §3 豁免且理由已写下来"]
    end
    PF --> SETTINGS
    SETTINGS["§0 / §4 读实时 worker 设置：当前默认 TUI agent 与禁用列表"]
    SETTINGS --> USABLE{"所选 agent 被识别且未被禁用？"}
    USABLE -->|"否"| FAILSTOP["§9 报精确错误并停止；绝不猜，也不擅自替换 worker"]
    USABLE -->|"是"| DISPATCH["§4.3 worker-start --worktree new-top-level --name 票 slug --setup run --agent 所选 agent --json"]
    DISPATCH --> TURN{"§4.3.1 回执是 turnStart: observed？"}
    TURN -->|"是"| LIVE
    TURN -->|"否"| PROVE{"证据能证明 turn 真的开始了？"}
    PROVE -->|"是"| LIVE
    PROVE -->|"否"| FAILSTOP
    LIVE["worker 已在它自己的顶层 worktree 里跑起来——继续看面板 2 的通信闭环"]

    classDef phase fill:#eef4ff,stroke:#4b74d8,color:#101828,stroke-width:1.5px
    classDef gate fill:#fff4e5,stroke:#c77700,color:#3b2400,stroke-width:1.5px
    classDef stop fill:#ffecec,stroke:#d13438,color:#5a0d0d,stroke-width:1.5px
    classDef ok fill:#e8f7ee,stroke:#1f9254,color:#08281a,stroke-width:1.5px
    class START,DECL,HARD,P1,P2,P3,P4,P5,P6,SETTINGS,DISPATCH,SCOUT,CONV,PLAN8,LIVE phase
    class CH,USABLE,TURN,PROVE gate
    class FAILSTOP stop
    class ANS,DONE_A ok
```

### 2 · 通信闭环（§4.5–§5）

最容易做错的一段：coordinator 不是在轮询，而是在被唤醒——收件器**结束进程**就是唤醒。处理批次与装回
下一次等待是一步，提问先分类再决定谁来答。

```mermaid
%%{init: {"themeVariables": {"fontSize": "14px"}, "flowchart": {"nodeSpacing": 18, "rankSpacing": 22, "padding": 6, "diagramPadding": 4, "useMaxWidth": true}}}%%
flowchart TD
    LIVE["worker 正在跑——这一面板就是让它持续前进的通信闭环"] --> INBOX["§4.5 每个 Run 装唯一收件器，作为 harness 能呈现的长调用——不用 nohup——台账存在仓库外"]

    INBOX --> LOOP["§4.5 闭环本体：收件器在唤醒事件上结束进程，这个结束就是唤醒"]
    LOOP --> WAKE["唤醒线：新的非心跳批次、worker 状态变化，或收件器自身出错"]
    WAKE --> HANDLE["处理整批：核对 Run、Task、Dispatch，按 message ID 去重"]
    HANDLE --> CLS{"§5 分类这条消息"}
    CLS -->|"提问"| HUM["决策类或 escalation 五类：附上你的倾向请人定夺——worker 的推荐只是参考"]
    CLS -->|"提问"| DET["细节类：coordinator 依据 ADR、spec 或用户原话代答"]
    CLS -->|"escalation"| ESC["escalation 只冻结该票；其余票照常推进门禁"]
    HUM --> REPLY["reply --id message-id"]
    DET --> REPLY
    ESC --> REPLY
    REPLY --> ACKF["整批处理完才 ack，用那次读取快照的 deliveryId"]
    ACKF --> REARM["装回下一次等待——唤醒之后没有新等待就是静默停摆"]
    REARM --> WAKE
    CLS -->|"worker_done"| ACCEPT["§6 门禁验收——面板 3"]
    INBOX --> BOUND["harness 没有唤醒通道？把 turn 保持在 ≤60 秒的有界等待里，三轮无进展就按证据恢复"]
    BOUND -.-> WAKE

    classDef phase fill:#eef4ff,stroke:#4b74d8,color:#101828,stroke-width:1.5px
    classDef gate fill:#fff4e5,stroke:#c77700,color:#3b2400,stroke-width:1.5px
    classDef human fill:#f3e8ff,stroke:#8b5cf6,color:#2e1065,stroke-width:1.5px
    classDef ok fill:#e8f7ee,stroke:#1f9254,color:#08281a,stroke-width:1.5px
    class LIVE,INBOX,LOOP,WAKE,HANDLE,DET,REPLY,ACKF,REARM,BOUND phase
    class CLS gate
    class HUM,ESC human
    class ACCEPT ok
```

### 3 · 验收、合并与收尾（§6–§7）

`worker_done` 不等于验收通过：先跑收尾检查，再按票型选门禁，只有全绿才进入合并。同一票同门禁连续失败
两次暂停该票；跨票打回累计五次暂停整个 run。

```mermaid
%%{init: {"themeVariables": {"fontSize": "14px"}, "flowchart": {"nodeSpacing": 18, "rankSpacing": 22, "padding": 6, "diagramPadding": 4, "useMaxWidth": true}}}%%
flowchart TD
    ACCEPT["面板 2 的 worker_done 送到这里——门禁验收起点"] --> NOISE{"§4.0.1 收尾检查：在 worktree 里 git status --porcelain 与 diff --numstat"}
    NOISE -->|"万行级"| REFORM["格式化重排噪声：先留证，由 worker 恢复，然后打回"]
    NOISE -->|"正常未提交改动"| WHY["追问 worker 为什么还有未提交内容——不默认接受"]
    NOISE -->|"干净"| PROP["§3 / §6 深度：可圈定的单票跑受影响测试，共享接口或影响面不明跑全量；省略双轴 review 必须把理由写进 spec 与 Answer"]
    REFORM --> SEND
    WHY --> SEND
    PROP --> GATES["§6 按票型选门禁：研究查来源 / G-docs / G-wayfinder / G-spec / G-tickets / G-impl"]
    GATES --> GREEN{"门禁在可观察结果与证据上全绿？"}
    GREEN -->|"否"| SEND["打回：哪个门禁没过、缺什么证据、具体要补什么"]
    SEND --> BREAK{"同一票同门禁连续失败两次，或 run 级打回累计五次？"}
    BREAK -->|"是"| STOP9["§9 停止派活，把人要的状态与证据交给人"]
    BREAK -->|"否"| RECYCLE["派 follow-up Task，或对复用终端写明原 worktree selector；新 turn 重跑 §4.3.1——回到面板 2 的闭环"]
    GREEN -->|"是"| MERGE["§6 在最终集成 head 上跑 G-merge：用 diff 核对 PR 的 Door 声明；双向门也必须门禁全绿"]
    MERGE --> EXC{"单向门或拿不准、用户明确要求保留 PR，或有规则/门禁挡住？"}
    EXC -->|"是"| KEEP["保留 PR；单向门由人类手动合并；如实报告状态与确切合并动作"]
    EXC -->|"否"| SYNC["双向门：自动合并，再按 §6.5.1 只在干净副本上拉取已合并 main，并用 merge-base --is-ancestor 校验"]
    KEEP --> REPORT
    SYNC --> LIFE["§6.5 worker 生命周期：follow-up、retain 或 release，然后查 reclaimable 并逐项结清"]
    LIFE --> REPORT["§7 收口报告写在 repo 外持久目录：产物与合并 SHA、验收证据、人定决策、未完成项、生命周期清点"]
    REPORT --> DONE_B["§7 到达约定交付终点即停止——通常是项目改动已合并"]

    classDef phase fill:#eef4ff,stroke:#4b74d8,color:#101828,stroke-width:1.5px
    classDef gate fill:#fff4e5,stroke:#c77700,color:#3b2400,stroke-width:1.5px
    classDef human fill:#f3e8ff,stroke:#8b5cf6,color:#2e1065,stroke-width:1.5px
    classDef stop fill:#ffecec,stroke:#d13438,color:#5a0d0d,stroke-width:1.5px
    classDef ok fill:#e8f7ee,stroke:#1f9254,color:#08281a,stroke-width:1.5px
    class ACCEPT,NOISE,WHY,PROP,GATES,MERGE,SYNC,LIFE,REPORT phase
    class GREEN,BREAK,EXC gate
    class STOP9 human
    class REFORM,SEND,KEEP,RECYCLE stop
    class DONE_B ok
```

### 4 · 失败分支（§9）

失败不是一个节点：每个入口都有自己的处置流程，而它们的共同形状是——先取证、再决定、报精确错误、绝不
无条件 relaunch。

```mermaid
%%{init: {"themeVariables": {"fontSize": "14px"}, "flowchart": {"nodeSpacing": 18, "rankSpacing": 22, "padding": 6, "diagramPadding": 4, "useMaxWidth": true}}}%%
flowchart TD
    E1["CLI 起不来，或取不到编排指南"] --> R1A["报精确错误并停止——不换可执行文件，不猜命令"]

    E2["worker-start 回执 state: failed"] --> R2A["① 读回执四字段：failedStage / lastError / recovery / residualResources"]
    R2A --> R2B["② 三条只读命令：terminal show、git worktree list、terminal read"]
    R2B --> R2C{"终端还在、worktree 已建、setup 零输出退出？"}
    R2C -->|"是——是 readiness 判早，不是票的问题"| R2D{"③ 在该 worktree 里手跑仓库的 setup 命令"}
    R2C -->|"否"| R2E["查真实错误——不盲目重派"]
    R2D -->|"通过——瞬时竞态，重派安全"| R2F["④ 读 recovery 参考，⑤ 先 worker-release 失败 Dispatch，⑥ 用 --retry-of 配 --task 并显式给落点重派"]
    R2D -->|"失败"| R2E
    R2F --> R2G["重新确认 turn 开始——ready 回执依然什么都不证明"]

    E3["Orca app 运行中死掉或重启"] --> R3A["① orca status --json 确认 app 已起——在此之前不发任何编排命令"]
    R3A --> R3B["② worker-list --include-remote --json 清点每个 Dispatch；Run、Task、终端状态由 Orca 持久化，扛得住重启"]
    R3B --> R3C["③ 重装收件器，并逐个重确认在跑 worker 的 turn"]
    R3B -.-> R3D["重启不构成 worker 已死的证据"]

    E4["消息从 worker 出去了，coordinator 就是没收到"] --> R4A["按顺序查五个断点：唤醒、队头未 ack、身份或邮箱、消费者死亡、worker 根本没发"]
    R4A --> R4B["三源对账：本地 --status 与 deliveries、服务端 check --all、worker-list / worker-show / worker-read"]
    R4B --> R4C{"生命周期分支"}
    R4C -->|"已结算但无 worker_done"| R4D["对账产物后继续验收——不要求重发，不派第二个编辑"]
    R4C -->|"turn 结束、未结算"| R4E["确认终端仍属原 Dispatch，再发一次收据提醒"]
    R4C -->|"liveness 无法证实或标题空闲"| R4F["这只是缺证据：不停止、不 release、不重派"]
    R4C -->|"绑定丢失或 consumer_fenced"| R4G["停手，核对真实调用身份，绝不冒用 handle"]

    E5["worker 卡在权限提示上，或 turn 始终没被确认"] --> R5A["读它请求的操作、目标路径与风险，只批准本轮已授权的操作"]
    R5A --> R5B["额外的权限、第三方账号、付费或不可逆操作，按 §5 请人定夺"]
    R5B -.-> R5C["Enter 从来不是万能批准，绕过模式也不是捷径"]

    E6["worker 报完后出现万行级未提交改动"] --> R6A["先留证：worktree patch、index patch、untracked 清单"]
    R6A --> R6B["逐文件比对 HEAD、index、工作区与 worker 的编辑记录"]
    R6B --> R6C["确认并备份完每个真实改动之后才可恢复该文件——恢复由 worker 做，coordinator 负责验收"]
    R6C -.-> R6D["本地 formatter 覆盖是确认性失败的修复，不是每个票的固定前置"]

    R1A ~~~ E2
    R2E ~~~ E3
    R2G ~~~ E3
    R3C ~~~ E4
    R3D ~~~ E4
    R4D ~~~ E5
    R4E ~~~ E5
    R4F ~~~ E5
    R4G ~~~ E5
    R5B ~~~ E6
    R5C ~~~ E6

    classDef fail fill:#ffecec,stroke:#d13438,color:#5a0d0d,stroke-width:1.5px
    classDef step fill:#eef4ff,stroke:#4b74d8,color:#101828,stroke-width:1.5px
    classDef ask fill:#f3e8ff,stroke:#8b5cf6,color:#2e1065,stroke-width:1.5px
    classDef branch fill:#fff4e5,stroke:#c77700,color:#3b2400,stroke-width:1.5px
    classDef entry fill:#e8f7ee,stroke:#1f9254,color:#08281a,stroke-width:1.5px
    class R1A,R2E,R3D,R4G,R6D fail
    class R2A,R2B,R2F,R2G,R3A,R3B,R3C,R4A,R4B,R4D,R4E,R4F,R5A,R6A,R6B,R6C step
    class R2C,R2D,R4C branch
    class R5B,R5C ask
    class E1,E2,E3,E4,E5,E6 entry
```

## 安装

两个 skill 都用社区 [`skills` CLI](https://github.com/vercel-labs/skills) 安装
（`npx skills add …`）。按需要选语言版本；它们是两个独立包，不是互备的翻译兜底，团队双语的话
两个都装也可以。

```bash
# English
npx skills add whutlichao/orchestra-auto --skill orchestra-auto

# 简体中文
npx skills add whutlichao/orchestra-auto --skill orchestra-auto-zh
```

加 `--global` 装到用户级而不是当前项目，加 `--agent <name>` 指定目标 agent：

```bash
npx skills add whutlichao/orchestra-auto --skill orchestra-auto --global --agent claude-code
```

也可以从本仓库的本地检出安装**两个**变体：

```bash
git clone https://github.com/whutlichao/orchestra-auto
npx skills add ./orchestra-auto --skill orchestra-auto --skill orchestra-auto-zh
```

`orca skills install` 是 Orca 自己对同一条 `npx` 命令的封装，但它只覆盖 Orca 本地注册表里的那些
skill。跑 `orca skills install --skill orchestra-auto` 会报 `Unknown skill`——这两个包不在那个注册表
里；本仓库请用上面的 `npx skills add` 命令。

### 安装这条命令做了什么、没做什么

- **GitHub 是来源。** skill 内容住在本仓库，CLI 在安装时从 GitHub 读取，不会把你机器上的东西
  上传。
- **安装由 `skills` CLI 完成，不是本仓库。** 这条命令就是社区 CLI 去拉一个公开仓库，这里没有
  投稿步骤，也没有审核队列。
- **skills.sh 是自行聚集的目录。** 按
  [skills.sh FAQ](https://skills.sh/docs/faq)，只要有人运行安装命令，仓库就会通过匿名安装遥测
  自动出现在排行榜上——不存在面向作者的投稿表单。**因此本 README 不声称本仓库已收录在
  skills.sh 上**，任何人也不能替项目做这个声明：收录是真实安装带来的可观察结果，不是作者提交
  的动作。当前状态可以自己看：`https://skills.sh/whutlichao/orchestra-auto`。
- **遥测是排名输入，且可退出。** CLI 上报的是聚合安装遥测，其中包含公开仓库与 skill 标识；按
  skills.sh FAQ，它不携带个人信息或设备信息。`DISABLE_TELEMETRY=1` 与 `DO_NOT_TRACK=1` 可以关掉
  （CLI 文档所列）。在自己机器上设置其中任意一个都没问题，不影响本仓库。任何人都不要为了刷一个
  数字去安装。
- **本仓库不带加载脚本。** 这两个 skill 是 Markdown 说明加一个仅用标准库的 Python 脚本；
  安装本身不执行任何东西。

## 前提与能力边界

这两个 skill 是 **Orca 专用**的。装之前请读这一节。

| 要求 | 说明 |
| --- | --- |
| Node.js 与 `npx` | 社区 `skills` CLI 通过 `npx` 运行，安装命令需要本机装有 Node.js。除此之外本仓库不需要 Node。 |
| Orca | 已安装 [Orca](https://www.onorca.dev/) 且 CLI 可达。skill 会调用 `orca orchestration worker-start`、`check`、`send`、`reply`、`worker-release` 等。 |
| Orca CLI 可执行文件 | 按 Orca 文档的方式解析：`ORCA_CLI_COMMAND` → 平台二进制名 → `orca`。 |
| Orca 的 `orchestration` 指南 | skill 要求 coordinator 用 `orca skills get orchestration` 取回它，并以**实时**指南为准，而不是以 skill 自己的叙述为准。 |
| worker agent | 你的 Orca profile 已启用的那些 TUI agent。skill 读取当前默认值与当前禁用列表，而不是写死某一个。 |
| Python 3 | 仅用于可选的内置收件循环（只用标准库：POSIX 文件锁，故限 macOS/Linux/WSL）。 |

**能力边界。** 这套流程是针对 Orca 的 orchestration 动词写的。其中的判断——通道选择、门禁选择、
决策分类——是可以迁移的，别的编排器也能借鉴；但*命令*不可移植，skill 也不会假装它可以。
如果你的 CLI 不提供 `orca orchestration`，这个 skill 不适合你。

凡是涉及版本相关细节的地方（具体的设置文件、回执字段名），skill 刻意指向**当前** CLI help 与
**当前** Orca 指南，而不是写死某个值；并明确要求 coordinator 在计划用的命令与公开文档不一致时，
带证据提问，而不是猜。

## 验证

仓库用 `python3 -m unittest discover` 检查，跑两个套件。不联网、不需要凭证、不依赖任何特定机器：

```bash
python3 -m unittest discover -s tests -v
```

- `tests/test_inbox_loop.py` 用一个桩 CLI 驱动真实的收件脚本，断言那些安全关键行为：原子落盘、
  重读时内容完整、重复 delivery 不覆盖首次读取、只有 heartbeat 的批次才 ack（普通批次与混合
  批次不 ack）、CLI 错误显式失败而不是伪装成空队列、以及单消费者文件锁。它还钉住唤醒契约——
  新落盘的非心跳批次要以一行可解析 stdout 结束进程，纯心跳批次不能，worker 状态变化要——并覆盖
  原生 `check --wait` 路径、其 stderr keepalive，以及超时后重新装上等待。
- `tests/test_package_content.py` 检查包本身：两个语言变体结构一致、frontmatter 合法且 `name`
  与目录一致、所有相对链接可解析、随包发布的每个 reference 都可达并声明了自己的触发条件、
  eval JSON 的形状与唯一性、`eval.yaml` 白名单、Python 的 `py_compile`、shell wrapper 的
  `bash -n`、MIT 许可，以及脱敏扫描。

已记录结果为 **78 OK（1 skipped）**。这是主要的结构与行为门禁。

想单独跑某一条也可以：

```bash
python3 -m py_compile skills/*/scripts/inbox-loop.py
bash -n skills/*/scripts/inbox-loop.sh
python3 -c "import json,glob;[json.load(open(p)) for p in glob.glob('skills/*/evals/*.json')+['skills.sh.json']]"
```

### 按需加载与激活成本

按 Agent Skills 约定，宿主会在 skill 激活时注入完整的 `SKILL.md`；只有路由表指示时，才读取
`references/` 下的文件。[PR #2](https://github.com/whutlichao/orchestra-auto/pull/2) 将派发循环细节移至
`references/dispatch-loop.md`，将回复细节移至 `references/reply-protocol.md`。始终加载的入口文件保留
路由表与硬规则，包括 `--worktree new-top-level`、显式 `--agent`、`state:ready` ≠ `turnStart`，以及派发前的
`worker-start --help` / 注册表确认。

与精简前的提交 `fbb09b9` 相比，入口文件大小如下：

| 变体 | `SKILL.md` 字节数 | 估算 token（字节 ÷ 4）|
| --- | ---: | ---: |
| 英文 | 30,208 → 20,287（−32.8%） | 7,552 → 5,071 |
| 中文 | 24,359 → 15,963（−34.5%） | 6,089 → 3,990 |

这里的 token 节省**口径是字节数 ÷ 4**，不是 tokenizer 实测。细节仍保留在 references 中，因此整个包的字节总量
几乎不变。如果某一轮同时读取两个新 reference，激活时的节省不等于整轮的节省。

### 自动脱敏扫描

`tests/test_package_content.py` 里的 `LeakScanTests` 是脱敏检查的自动化部分。它扫描每个已发布的
文本文件，找那些绝不能出厂的形态：主目录绝对路径、某个具体的 profile 数据库文件名、凭证类变量名，
以及 token 字面量。有四点和模式本身同样重要：

1. **不写下任何私有字面量。** 扫描器只持有通用**形态**，绝不写具体的私有仓库名、账号名或凭证变量名
   ——把那些写进一个公开扫描器，等于公开了扫描本来要挡住的标识本身。精确值走带外核验：
   `PRIVATE_IDENTIFIERS=<a,b,c> python3 -m unittest tests.test_package_content` 会拿你给的值跑同一套
   扫描。没有这个变量时该用例会 **skip** 并说明原因，因此绝不会被误当成它并不具备的覆盖。
2. **可解释。** 每条例外都按**（文件，模式）对**授予，不按文件授予。整文件豁免会连带免掉路径、凭证
   与 token 检查——脱敏扫描正是这样悄悄失去对「最常被编辑的那些文件」的覆盖的。测试断言：唯一
   自我豁免的文件是扫描器自身源码、每条豁免都对应一个确实出现在那里的模式、且被豁免文件里出现
   其他模式仍会失败。
3. **不误报。** 收件脚本用随机 UUID 作为临时文件名 token。
   `test_random_uuid_tokens_are_not_reported_as_credentials` 这条断言这些 UUID 不匹配任何凭证
   模式，真实发现不会被噪声淹没。
4. **通用形态仍要有牙齿。** `test_generic_credential_pattern_catches_a_realistic_secret_name` 断言
   凭证形态能匹配现实中的变量名（例如带 `_TOKEN` 或 `_API_KEY` 后缀的全大写名字）且不误伤普通文字，
   这样把字面量换成形态不会悄悄把检查变成空操作。

另有两项人工检查与它并列，且都无法从仓库内部自动化：

- **自己读一遍 diff，找任何可识别的信息。** push 之前逐文件过一遍 `git diff <base>...HEAD`。
  真正泄露在散文里的东西，往往没有任何模式预料到，靠的就是这一步。
- **核对署名面。** 版权人出现在 `LICENSE`、两个 README 与 launch kit 里是刻意的；出现在别处就是
  脱敏事故。

## 评估集

每个语言变体都带一份 `evals/evals.json`，20 个提示词层面的场景，覆盖通道判定、worker 栏取值、
启动确认、门禁选择、review 安排、打回判断、决策分类、升级、合并例外，以及「先唤醒、再重装」的契约。

这些是**场景检查，不是端到端证明**：它们看的是一个读过本 skill 的 agent 是否按 skill 的意图推理，
并不证明编排在真实 Orca 主机上能跑通——那是脚本行为测试和真实使用的事。每份文件都在 `_note`
里写明同样的保留，且没有任何场景假设某台特定机器：没有主目录路径、没有私有仓库或票据名、
没有本机 agent 偏好、也没有任何主机的设置快照。像「这台机器默认用哪个 agent」这样的场景，
一旦写进公开评估集就等于泄露本仓库刻意排除的数据；所以场景考的是**推理**（去读实时设置、
不要猜），而不是某个值。

## 仓库结构

```text
.
├── LICENSE                     MIT，版权 2026 whutlichao
├── CONTRIBUTING.md             如何改动这些包
├── SECURITY.md                 什么算这里的安全问题
├── README.md                   English README
├── README.zh-CN.md             本文件
├── skills.sh.json              skills.sh 目录页的分组配置
├── skills/
│   ├── orchestra-auto/         英文包
│   │   ├── SKILL.md            路由与核心约束
│   │   ├── references/         按条件读取的细节，9 个文件
│   │   ├── scripts/            可选的收件循环
│   │   ├── evals/evals.json    提示词层面的场景
│   │   └── eval.yaml           可选的外部 skill runner 用例
│   └── orchestra-auto-zh/      中文包，结构相同
│       └── …
├── launch-kit/                 定位、demo 讲稿、FAQ、各渠道草稿
└── tests/                      上面的 unittest 套件
```

## 状态与范围

- 这套流程对**过程**有主张，对你的产品没有：它不会替你决定做什么，拿不准就升级而不是猜。
- `launch-kit/` 下的发布材料是**草稿**。它们存在的意义是让维护者在审阅后自己发出去。准备这些
  材料不涉及登录账号、不接触社区、不代为发帖。
- 本仓库只放已发布的包、它们的检查与文档，不含 Orca 本身。

## 致谢

本仓库的监督式协作与 Agent Skills 流程，灵感来自 [Matt Pocock 公开的 agent skills](https://github.com/mattpocock/skills)
及其相关工程实践思路。本仓库将这些思路落地到 Orca（`orca orchestration`），由本仓库自行实现并适配；Matt Pocock 未参与本项目的开发或维护，也未为本项目背书。可参阅 [Matt Pocock 的 GitHub 个人资料](https://github.com/mattpocock)。

## 许可

[MIT](LICENSE)，版权 2026 whutlichao。欢迎贡献，见 [CONTRIBUTING.md](CONTRIBUTING.md)。
