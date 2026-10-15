# 通信、唤醒与失联恢复

**什么时候读**：每个 Run 首次派活前，处理身份绑定、收件器、唤醒与失联恢复；后续派活只核对收件器仍有效。
命令语义以本轮 `orca skills get orchestration` 及其 messaging 与 worker-contract 参考为准。
本文件使用 `<ORCA>` 表示本轮选定的可执行文件；
脚本通过 `ORCA_CLI_COMMAND` 接收该路径。

## 1. 身份和收件器

创建 Run 后把实际返回的 Run ID、coordinator handle、各 Task/Dispatch/worker handle 写入
repo 外台账。句柄来自真实调用方身份，不从终端标题或“最新终端”推断。后台进程显式指定
`check --terminal <coordinator_handle>`；`check` 不使用 `--from`。

每个 Run 使用独立目录、唯一收件器。启动示例：

```bash
ORCA_CLI_COMMAND=<已确认的可执行文件路径> nohup <SKILL_DIR>/scripts/inbox-loop.sh \
  <run_id> /tmp/orch-<repo>-<run_id> <coordinator_handle> \
  > /tmp/orch-<repo>-<run_id>.log 2>&1 &
<SKILL_DIR>/scripts/inbox-loop.sh --status /tmp/orch-<repo>-<run_id>
```

脚本依赖 Python 3 标准库（POSIX 文件锁，适用 macOS/Linux/WSL）。启动时用文件锁排除同目录
双实例，目录绑定 Run/terminal/CLI 后禁止复用；Orca 的 waiter 槽仍是跨目录的最终约束。
不要迁入旧脚本运行目录：先确认并停止旧 loop 及其 waiter，保留旧消息，使用新的 Run 专属目录。

`--status` 只查看该目录的锁与状态，不扫描其他 Run 的进程，不消费队列。`phase=backoff`
期间没有 waiter 是正常状态，不能因此另起实例。`loop: DEAD` 时先查 `watch.log` 的错误与
当前 Run 绑定；绑定/权限/waiter 问题解决前不自动重启，不杀其他 Run 的进程。

脚本每轮先做无过滤 check，再最多等待 30 秒，防止心跳与普通消息积压。完整响应按 deliveryId
哈希原子写入 `deliveries/*.json`；文件不轮转删除。同一未确认批次只记录一次 PENDING，
随后按较长间隔复查，避免 FIFO 重放造成重复日志和 CLI 调用。`NEW-MESSAGE` 仅是最近落盘的提示，
**不是待办清单**；收到新消息或恢复会话时枚举全部 delivery 文件，对照台账处理。

错误显式落盘并退出，不能将 CLI 失败、JSON 错误或绑定失效解释成空队列。

## 2. 收件与确认

维护逐 message ID 的台账：`received → processing → handled`，记录 reply 回执、验收结果、
终端归属决定。恢复时先对账；重复 Delivery 不重复回复、不重复合并或 release。

1. 读完整 Delivery，验证其 Run/Task/Dispatch 属于本轮权威 attempt；旧 attempt 消息保留作证据，
   不据此完成新 attempt。
2. 提问用 `reply --id <message_id>` 回答；待人工决定的记录为 pending，不能超时自答。
   worker_done 对照真实 Dispatch 和产物验收；生命周期结算不等于交付验收通过。
3. 按当前 Orca 指南完成整批消息及必要的终端归属决定后，才 ack **这份已读快照**里的
   `.result.deliveryId`。保存 ack 的成功回执；失败保持台账并重新核验，不假定已确认。
4. 一条等待人类决定的问题堵住 FIFO 时，执行 `check --run <run_id> --terminal <handle>
   --all --json` 只读查看后续消息，先处理其他 worker 的问题/完成报告并登记；`--all` 不提供
   可 ack 的 Delivery，不编造 ID。原批次完成后逐批消费，对已处理消息只对账。

脚本只会自动 ack 已落盘且**每条都是 heartbeat**的非空批次；混合批次和未知类型一律交给
coordinator。类型过滤只决定 waiter 何时醒来，不改变整批处理义务。脚本不会删除本地待办，
队列为空也不说明台账都已完成。

## 3. 协调者持续运行与唤醒

`send` 成功是 durable enqueue；wake/nudge 是 best effort。`nohup`、文件出现、后台
收件器存活都不等于 agent 会产生新 turn，不能据此宣称“会自动继续”。

派活时依据当前 harness 的实际工具契约选择并记录等待方式：

- 有已确认的任务完成通知：用该机制等待本地新 delivery 或检查期限到达；每次通知返回后
  先处理消息，再重新安装下一次等待。通知机制自身的完成与续装必须可观察。
- 没有可靠通知：保持 coordinator 当前 turn，用工具有界等待，每次不超过 60 秒，返回后
  读收件箱与台账并继续其他已授权工作。不能发 final 后假定后台脚本会叫醒自己。
- 环境必须结束 turn：明确报告仍在运行的 Dispatch、最后进展、台账目录与无法自动唤醒的
  限制；恢复入口是读该台账及 Orca 当前状态。不能把这个状态写成已完成。

每次长操作返回后检查消息；空闲时不超过 60 秒检查一次。连续三轮无进展，枚举当前 Run 的
`worker-list --include-remote --json`（有分页须读完），检查 projection.nextAction 和
liveness.reason，并对相关 Dispatch 读取 worker-show/worker-read。检查本地文件、服务端
队列、worker 状态三处，不能只盯 NEW-MESSAGE，也不能只等 worker_done。

## 4. worker 必须执行的通信契约

这些要求必须写进 §4.4 的 spec，worker 不会自动看到本文件：

- 使用 live preamble 的真实可执行文件、handle、Task ID、Dispatch ID 与附加 authority 参数。
- 每次自然检查点主动 `check --terminal <自己的句柄>`，包括开工、测试后、换文件前、完成前。
  coordinator 对运行中的 worker 用 `send --to dispatch:<id>`；发送后需有读取/执行证据。
- ask 超时用同一 message ID resume；心跳遵循 preamble；不直接开用户提问界面。
- 成功或失败都从自己的终端发送一次 worker_done，显式 outcome、三句摘要与真实产物路径；
  发送成功回执留作证据后结束回合。plain final、PR 已开、心跳或“我完成了”不算生命周期报告。
- 发送结果不明先查 Dispatch/消息事实；已结算不重发。仅确认未结算、报告未入队且 authority
  仍有效时允许一次重试；仍失败则保留产物、报告通信阻塞。consumer_fenced 时立即停止。

## 5. 缺完成报告与失联恢复

| 观察 | 动作 |
| --- | --- |
| Dispatch 已结算，收件箱没 worker_done | 用 `check --all`、真实结算状态及产物对账，补记录并继续验收；不要求重发、不另派重复编辑者 |
| worker 回合已结束、未结算、最后 turn 无 worker_done | 读当前 Orca recovery 指南。确认该终端仍属于原 active Dispatch 且允许恢复时，发一次明确的补收尾指令：检查 follow-up、核验产物、从自己的 preamble 报 worker_done；复核 turnStart/transcript |
| send 入队但 worker 未读 | 检查是否卡在 ask、权限提示或回合已 idle；对已确认的本地空闲终端可用终端续跑机制提醒其读取原 Dispatch 邮箱，不能把正文重复派成新 Task |
| liveness=unverifiable / agentWait=null / 标题空闲 | 仅为缺证据；读 transcript/worker-show 和 nextAction，不 stop、不 release、不重派 |
| 有真实退出证据且无法恢复 | 按 recovery 指南处理 stop/abandon/retry，保留产物，旧 attempt 权威结束后才派恢复 worker |
| 身份/Run 绑定错误、consumer_fenced | 停止该身份操作，核验真实调用方与权威关系；不伪装 handle、不无条件新建 Run |

补收尾或唤醒尝试最多一次，随后复核证据；仍无进展时保留状态并报告阻塞，不循环注入 Enter、
不重复报告、不以静默授权重派。coordinator 永远不代发 worker_done，不替 worker 改代码或提交。

## 6. 收尾

完成报告、验收和合并分别记录。release 仅在真实结算且产物已持久化后按生命周期协议执行；
已结算但待验收/合并的终端不得静默遗留，需在台账保留明确的下一步与处理期限。
所有预期 Dispatch 处理完且台账无待办后，停止本 Run 的收件器（读取本目录的 loop PID，
先确认进程身份再 SIGTERM）；脚本会回收自己的 CLI 子进程。nohup 不会随会话结束自动退出。
持久审计报告保存关键回执和结论后，才考虑清理临时消息文件。
