# worker-start 回执 `state: failed` 的取证与重派

**什么时候读这份文件**：只在 `orchestration worker-start` 的回执里出现 `state: failed` 时。
正常路径不读它——读它本身不该成为你每次派活的固定开销。

**为什么单列成文件**：它有 6 步、约 700 token，而 `state: failed` 是低频事件。
留在 SKILL.md 里意味着每次会话都要为一件不常发生的事付这份上下文。

**唯一要记住的一句话**：「不许 relaunch」指的是**不许无条件重试**，不是不许按 recovery 重试。
上一次差点把 `terminal_handle_stale` 读成「不能重派」，而正向指引就在盘上。

---

## 这套顺序的由来（每一步的理由都出自这里）

某次 `worker-start` 回执：

```text
failedStage: agent_readiness
lastError:   terminal_handle_stale
```

读起来像「终端没了，重派也没用」。实际取证发现**两个终端都还在、worktree 也建好了**，
只是 setup 终端 `status: exited` 且 `tail: []`（零输出）——**就绪检查抢在 setup 完成之前
判了失败**。故障不在票上，也不在配置上。

---

## 处置顺序（6 步，顺序有意义）

### 1. 读回执的四个字段

```text
failedStage         失败发生在哪个阶段
lastError           错误码
recovery            ← 最重要：直接给出下一条命令（那次给的是 worker-release）
residualResources   残留资源，据此决定要不要先清理
```

`recovery` 字段通常已经把该跑的命令写好了。**先读它再想**，不要一上来就设计重试方案。

### 2. 取证，不是猜

三条只读命令，各自回答一个问题：

```bash
<ORCA> terminal show --terminal <setup句柄> --json   # 两个终端是否还在（看 orphaned 字段）
git worktree list                                     # worktree 是否真建了
<ORCA> terminal read --terminal <setup句柄> --json    # setup 终端的 status 与 tail
```

**判据**：终端在 + worktree 在 + setup 零输出退出 ⇒ **失败在就绪检查，不在你的票**。
这个组合一旦成立，就不要往配置方向排查——那条路会把你带偏两轮。

### 3. 验证 hook 本身是好的

在 worktree 里**手动跑一次该仓库 setup hook 实际执行的命令**，先从回执或仓库配置确认命令。

```bash
cd <worktree> && <该仓库的 setup 命令>
```

跑通 ⇒ **瞬态**，不是配置问题，可以安全重派。
跑不通 ⇒ 按真实 setup 错误处理，不要盲目重派。

### 4. 读 recovery 参考

```bash
<ORCA> skills get orchestration --reference references/recovery-and-cleanup.md
```

它的状态表写着：

> `failed` or `stopped` → Start a replacement with `--retry-of`; repeat placement explicitly

所以**不是不能重派，是要用对姿势**：

```bash
<ORCA> orchestration worker-start --task <task_id> \
  --retry-of <failed_dispatch_id> \
  --worktree <显式 selector> --agent <§0 的 worker> --json
```

两个必须注意的约束：

- **`--retry-of` 必须配 `--task`**。配 `--spec` 会另建一个 Task，等于换了一张票。
- **placement 不静默继承**。`--worktree` 要显式给（用 `--repo` 或
  `id:<repo-id>::<worktree 绝对路径>`），别指望它从失败的 Dispatch 那里继承过来。

### 5. 先 release 掉那个失败 Dispatch

```bash
<ORCA> orchestration worker-release --dispatch <failed_dispatch_id> --json
```

它从未跑过 Task，属它的终端却仍占着配额。**先 release 再重派**，否则新 worker 可能因为
配额或 waiter 槽位起不来。顺序不能倒。

### 6. 重派后照 §4.3.1 确认 turn 真的开始

回执 `ready` 仍然证明不了任何事——这条对首次派活和重派一样成立。
按 §4.3.1 读标题、判空闲横幅、必要时补**一次**裸 Enter。

---

## 什么时候该停

- 第 3 步手动跑 setup **失败** ⇒ 不是瞬态，按真实错误排查，别重派。
- 同一张票反复 `failed` ⇒ 已达 §6 打回协议的单票熔断（连续 2 次过不了同一门禁），
  或该走 §9 的「报告并停」。别在重派上无限循环。
- 取证发现 worktree 里有**未提交的真实改动** ⇒ 那不是「失败」，那是「做了一半」。
  按 §6 G-impl 第 5 条先确认交付物是否已持久化，再决定收留还是打回。

## 相关

- SKILL.md §4.3.1 — 派活后确认 turn 开始（重派后同样适用）
- SKILL.md §6 打回协议 — 单票熔断与 run 级熔断
- SKILL.md §2 — 一切写操作不得落在 main；取证命令全部是只读的
