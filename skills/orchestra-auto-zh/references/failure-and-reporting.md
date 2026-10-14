# 失败与上报纪律

**什么时候读**：CLI 起不来、`worker-start` 回执为 `state: failed`、熔断触发、或 Orca app 运行中重启时。

## 9. 失败与上报纪律

- CLI 起不来、orchestration 指南拿不到：报告精确错误并停止，**不换可执行文件、不猜命令**。
- **`worker-start` 回执 `state: failed` 时，先取证再决定，不直接 relaunch**。实测一次
  `failedStage: agent_readiness` / `lastError: terminal_handle_stale`：看回执像终端没了，
  实际取证发现**两个终端都在、worktree 也建好了**，只是 setup 终端 `status: exited` 且
  `tail: []`（零输出）——就绪检查抢在 setup 前面判了失败。完整 6 步取证与重派姿势见
  `references/failed-dispatch-recovery.md`（只在收到 `state: failed` 时读）。三步骨架：

  1. **读回执四个字段**（`failedStage` / `lastError` / `recovery` / `residualResources`），
     再取证终端与 worktree 是否其实都在——判据与命令见该文件。
  2. **验证 hook 本身**：在 worktree 里手动跑一次 setup 那条命令，跑通即证明是瞬态。
  3. **按 recovery 重派**：`--retry-of` 配 `--task`，先 release 掉失败 Dispatch，重派后
     照 §4.3.1 确认 turn 开始。

  **为什么单列**：`terminal_handle_stale` 读起来像「不能重派」，而 recovery 的正向指引就在盘上。**「不许 relaunch」指的是不许无条件重试，不是不许按 recovery 重试。**
- 任何环节触发熔断（单票：连续 2 次过不了同一门禁；run 级：§6 打回协议的累计阈值）或
  escalation 类问题（冻结该票、其余照常，§5.1）→ 立即停下问人，说明卡在哪个阶段、已有的
  证据、需要人决定什么。
- **Orca app 中途挂掉/重启**：症状是前台 `check` 报错、后台收件箱进程退出。恢复三步：
  ① `orca status --json` 确认 app up；② `orchestration worker-list --include-remote --json`
  盘点各 Dispatch 的 liveness 与 attention（Run / Task / 终端状态由 Orca 持久化，重启不丢）；
  ③ 按 §4.5 第 1 条重起收件箱，对在跑 worker 按 §4.3.1 重新确认标题。app 未确认 up 之前
  不重发任何 orchestration 命令；更不要据此判定 worker 死了——§4.5 第 6 条：无证据从不
  授权 stop。
- **Run 绑定丢失或 consumer_fenced**：停止该身份上的消费与生命周期操作，读当前版本
  的恢复参考，核验真实 session/terminal 与原 Run。`check` 用 `--terminal`，不接受 `--from`；
  不要凭标题猜句柄、伪装 worker 或无条件新建 Run。
  旧 Dispatch 未盘点且归属未厘清前，不创建重复编辑者；无法恢复时保留产物、报告绑定阻塞。
- 已获授权的实施工作不因任务小或 repo 缺 `WORK_SCOPE` 而跳过派活；纯问答、报告及超出
  本轮交付终点的后续阶段不派活。范围不明时先只读探索并按 §1 复核。
- 后续阶段已在本轮范围内时直接推进；不在范围内时在报告写明状态与下一步入口。
- 设计术语遵循仓库语言；需要架构分析时使用 codebase-design 的词汇帮助表达。
