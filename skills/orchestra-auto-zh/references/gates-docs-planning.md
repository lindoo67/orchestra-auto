# G-docs / G-wayfinder / G-spec / G-tickets — 文档与规划票的门禁

**什么时候读这份文件**：手上这张票是设计票、规格票或票据拆分票，准备收尾验收时。
**只读你要用的那一节**，不要通读——这四道门禁的判据互不通用（尤其 G-docs 与 G-wayfinder
的产物形态完全不同，判据不能互借）。

**实施票不走这四道门禁的任何一个**，它走 G-impl（见 SKILL.md §6）。

---

## 目录

- [G-docs — 需求对齐（grill-with-docs 那条路：文档结构完整性）](#g-docs--需求对齐grill-with-docs-那条路文档结构完整性)
- [G-wayfinder — wayfinder 那条路（map 与决策票）](#g-wayfinder--wayfinder-那条路map-与决策票)
- [G-spec — to-spec 落盘后](#g-spec--to-spec-落盘后)
- [G-tickets — to-tickets 落盘后](#g-tickets--to-tickets-落盘后)

---

## G-docs — 需求对齐（grill-with-docs 那条路：文档结构完整性）

**只管 grill 产出的设计文档。** wayfinder 那条路走 G-wayfinder。

- spec/文档文件存在，章节严格等于 repo effort 模板的章节，无自由发挥章节、无草案代码块残留。
- 术语决议已 inline 落进 `CONTEXT.md`（不是「待定」占位）。
- ADR 只在三条件全满足时存在；不满足时不存在 ADR（**少即是过**）。
- design tree 的 frontier 为空：没有悬而未决的问题、没有「open 决策」占位符。
- worker Answer 里能看到 grill 轮次记录与每轮应答去向。

### 过了 G-docs 之后还没完

完整实施请求通常经过 `grill-with-docs → to-spec → to-tickets → implement`。
G-docs 只验收设计阶段；设计文件的 PR 通过 G-merge 并自动合并后，若本轮只要求设计，
在报告里记录后续入口并停止；若本轮包含实施，继续 to-spec 与 to-tickets。见 SKILL.md §7。

---

## G-wayfinder — wayfinder 那条路（map 与决策票）

**适用条件**：§1 把输入判成「大到装不进一个 session、fog 重（多方向未定）」且本轮
使用 `wayfinder`。先检查目标仓库是否已有 Wayfinding 约定；缺失时不要自行假设标签和映射。

**先读仓库自己的 Wayfinding 操作节**再跑本节的判据：map 与子票、原生阻塞、frontier 查询、
认领、解决的具体命令都住在那里。**本节只管验收什么。**

- **map 存在且是单一个 issue**，挂 map 标签，正文含四节：destination / notes /
  decisions so far / not yet specified（+ out of scope 可选）。
- **每张子票是「决策票」而不是实施切片**：body 只回答「要定的是什么」，且带类型标签
  （`research` / `prototype` / `grilling` / `task`）。
  **判据**：票的产出是**一个决定**，不是一段交付物；若它是「做一件事」（写代码、改配置），
  那是 SKILL.md §7 的实施票，不属于这张 map。
- **blocking 用 tracker 的原生依赖关系**，不是正文里手写一行——原生关系才能在 tracker UI 里
  **看得见**地画出 frontier，而那正是人判断「下一张拿哪张」的界面。机器人线取 database id，
  不是 issue 编号（命令见仓库的 Wayfinding 操作节）。
- **frontier 为空才是这一阶段的终点**：map 的开放子票里，剔除有开放阻塞者、剔除有 assignee 的，
  剩下的应当为空；且 **not yet specified 里没有再能成票的东西**（fog 已散尽）。
  **两个条件要分别验**：frontier 空 ≠ fog 散尽（前者只是当前无票可拿，后者要求所有能成形的
  问题都已成形）。
- **decisions so far 的每一条指向它那张票**，不重述决定本身——map 是**索引**不是仓库，
  一条决定只活在一个地方（它的票里）。
- **收口信号不问「做完了吗」，问「路清了吗」**：wayfinder 默认只产决策（plan, don't do）；
  若 effort 要把它一路带到执行，那要么是 effort 在 notes 里显式覆盖了，要么是 fog 已散尽、
  该交到 §7 去拆实施票了。**这两种情形要在报告里说清是哪一种。**

---

## G-spec — to-spec 落盘后

- spec 已按本轮交付终点落盘；需要发布 tracker 时，标签与状态遵循目标仓库的约定。若仓库区分规格锚点与
  实施票，不把两者混用。上游 skill 与仓库约定冲突时先核对用户目标，再按本仓库规则落盘。
- seams 已声明且尽量少（理想一个）、尽量高；用 codebase-design 词汇。
- user stories 覆盖面足够长；Out of Scope 非空。

**seam 选址属 §5.1 判据 2（方案分叉）**，按 SKILL.md §5 附倾向请人定夺，答复记入审计清单。

---

## G-tickets — to-tickets 落盘后

- 每票是垂直 tracer bullet（穿全层、可独立验证、单 context 装得下），blocking edges 已声明；
  wide refactor 走 expand–contract 而不是硬切。
- 票据先推远端，worktree 从仓库默认 base ref 切。
- **有依赖的票：下游的 base 等 upstream 合并后再切**。下游票从默认 base ref 切会缺上游
  改动（接口对不上，写出来就是红的）；从上游分支切又引入 stacked PR 的合并顺序约束。
  默认在上游票合入 main 后从新的 base 切下游票；
  用户明确要求保留开放 PR 时，按仓库的 stacked PR 或依赖分支策略处理，上游暂不合并——
  frontier 语义天然支持这个排队。stacked PR 仅作显式例外（时间紧且依赖链短），采用时
  必须在票据上写明栈序，§6.5 按栈序合并，任何一张 rebase 全栈跟着 rebase。

**拆分粒度属 §5.1 判据 3（scope 边界）**，同样要问人。写拆票选项时用 to-tickets 的原语言
描述**票数与每票交付什么**，不要自造口语（SKILL.md §7 有禁令与替换表）。

---

## 相关

- SKILL.md §6 — 门禁按票型路由的总表（先看它确认该走哪道）
- SKILL.md §7 — 按交付终点推进、拆票语言与设计票收尾对账
- SKILL.md §5 — 决策问人细节代答（seam 选址与拆分粒度都走它）
