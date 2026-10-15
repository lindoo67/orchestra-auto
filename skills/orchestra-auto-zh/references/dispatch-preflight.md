# 派活前检查：tick sheet 与收尾检查

**什么时候读**：每次派活之前（逐项打勾），以及 worker 报 `worker_done` 之后、宣称门禁通过之前的收尾阶段。

### 实时 worker 设置查找

仅在 Run 即将派活时查询。用实时 Orca CLI 定位当前 profile（例如读取 `orca agent hooks status --json` 的
`result.settingsPath` 并赋给 `SETTINGS_PATH`，其文件所在目录作为 `PROFILE_DIR`）；该路径只用于定位 profile，
**不要从 `orca-data.json` 读取 agent 设置**。

从该 profile 目录下的 `profile-state.db` 只读查询设置。当前 schema 将设置保存在
`profile_state_documents` 表中 `domain = 'settings'` 的 `payload` JSON，默认 TUI agent 和禁用列表分别是
payload 顶层的 `defaultTuiAgent` 与 `disabledTuiAgents`。例如：

```bash
PROFILE_DIR="$(dirname "$SETTINGS_PATH")"
sqlite3 -readonly "$PROFILE_DIR/profile-state.db" \
  "SELECT json_object(
     'defaultTuiAgent', json_extract(payload, '$.defaultTuiAgent'),
     'disabledTuiAgents', json_extract(payload, '$.disabledTuiAgents')
   ) FROM profile_state_documents WHERE domain = 'settings';"
```

确认结果中 `defaultTuiAgent` 非空，且 `disabledTuiAgents` 是数组（空数组有效）。若数据库、表、字段或值不可读，
先依据当前 CLI help 与 Orca guide 核对 profile-state schema；仍无法确认时停止并报告，不能回退到
`orca-data.json`、过期导出、快照、备份、本 skill 文本、eval 夹具或旧日志。

用户点名 agent 时优先使用点名值，否则使用实时默认值；两种情况都核对实时禁用列表，并确认 `worker-start --help` 能识别所选 agent。
若被禁用、不受支持或设置不可读，停止派活。

### 4.0 派活前 tick sheet（逐项打勾，未全绿不 dispatch）

唯一作用是让「我是不是漏了哪条」变成一次勾选，而不是靠记性——长 spec 写到后半段时，前面
已经确认过的约束最容易悄悄掉队。括号里是它的归属小节。

- [ ] **CLI 活着**：`<ORCA>` 可解析（`ORCA_CLI_COMMAND` / `orca`），`orca status --json`
      报 app up。起不来 → 按 §9 报告精确错误并停，不换可执行文件、不猜命令。
- [ ] **指南在盘上**：§4.2 的 `skills get orchestration` 已写入 `/tmp`，本轮不再重复抓取。
- [ ] **通道已判定，且若探索过就已复核**（§1 末尾「探索后必须重判」）。
- [ ] **票型已判定，且 spec 里写了票型行**（§4.4）：研究、设计、规格、票据拆分或实施。
      派活前依据 Target、Change 和预期文件判断；worktree 尚未创建，不运行针对它的 `git diff`。
      文档票只写适用的文档门禁，不把源码测试或双轴源码 review 写成验收项。完成后再以真实 diff 复核票型。
- [ ] **spec 五要素齐**：Target / Change / Constraints / Ownership / Observable acceptance，
      且开头两段是 BEHAVIOR RULE 与前置 skill 绝对路径（§4.4）。
- [ ] **worktree 参数对**：`--worktree new-top-level` + `--name <票 slug>` + `--agent <§0 的 worker>`；
      会话 cwd 与目标 repo 不一致时已加 `--repo <selector>`（§4.3）。
- [ ] **main 铁律自检真的过了一遍**（§2）：本轮不会在 main 工作区修改项目文件或创建提交；仅 §6.5.1 已合并成果的快进同步可更新主分支。
- [ ] **票据正本位置明确**：正本在任务 worktree 内，worker 负责 Status 流转与 Answer 追加；
      coordinator 在 main 上只读验收（§4.4）。
- [ ] **门禁已点名且可判定**：本阶段该过哪几道（G-docs / G-spec / G-tickets / G-impl /
      G-merge），每条的证据形式都能按 §6 机械判定。实施票多勾两笔：
      ① 按 §6 G-impl 第 1 条选定测试档（窄/宽），若选「窄」已能说出为何影响面可圈定；
      ② 若本票要省双轴 review，已按 §3 的可数判据确认并写明理由。
      **机械判定法**：实施票 spec 的 `Observable acceptance` 里必须**逐字出现 `code-review`**
      （连同「双轴 / Standards + Spec」字样），除非按 §3 省掉。跑一句
      `grep -c 'code-review' <spec>`，得 0 就是没写、不许 dispatch。
      常见故障：一轮实施票的 spec 全文 `review-mentions=0`，因为它们的前置 skill 指向
      `implement`（其正文写着要用 `/code-review`），我据此以为「worker 会自己做」——
      但 worker 只按 spec 里写明的验收清单交付，**前置 skill 里的大原则不会自动变成它的
      交付项**。清单里没有的，它不会加。
- [ ] **spec 里的每个基线数字都核过 base commit**：凡你在 spec 里引用「改动前基线：Test Files X / Tests Y」这类
      实测数字，必须确认那条日志来自**与本票 worktree 相同的 base commit**。
      常见事故：一个带新测试的**分支**上的全量日志，被当成另一票（从 main 切出）的
      改动前基线，用例数因此对不上。worker 的双轴 review 把这个不自洽当成 P1 提了出来，完全正确——
      而如果它没提，这个错就会变成一张“门禁已过”的假绿。
      **机械判据**：贴基线前比较产生该日志的 worktree 与本票 base 的 commit，两者不同就**不要用**
      那个数字——或者明写「基线来自 `<commit>`，与本票 base 差 N 个 commit，仅作量级参考」。
- [ ] **本仓库若确有自动格式化风险，已写入针对性的预防与安全恢复要求**（§4.4）。
- [ ] **派活后已确认 turn 真的开始**（§4.3.1），同时确认 §4.5 的唯一后台收件器正常。

打回与熔断不在这张表里——照 §6 的「打回协议」执行（带具体缺项清单；同一票连续 2 次不过
同一门禁则停下问人）。

### 4.0.1 收尾时必查：格式化噪声

worker 报 `worker_done` 之后、宣称门禁通过之前，**先跑这三条**（§6 的 G-impl 第 0 步）：

```bash
cd <任务 worktree>
git status --porcelain
git diff --numstat | awk '{a+=$1; d+=$2} END {print "worktree 未提交:", a, "增", d, "删"}'
```

- 未提交为空 → 干净，继续验收。
- 有未提交且总量是**万行级** → 整份重排噪声，读 `references/reformat-noise-recovery.md` 恢复。
- 有未提交且量正常 → 问 worker 为什么有未提交改动，不要默认收下。

**判据一句话**：改动文件的 `git diff --numstat` 出现四位数以上，就去看行宽是否被压到 80
附近——编辑器插件与仓库 formatter 在写文件时会按自己的默认行宽重排**整个文件**，而仓库
没有 formatter 配置时这一动作不受约束，很多仓库源码本是宽行风格。

**恢复由 worker 执行，coordinator 只存证并打回。** 先备份完整 diff、未跟踪文件与 index，
再逐文件确认哪些内容是真实工作。`git diff --cached` 非空也不能证明工作区其余改动全是噪声；
确认并留底之前不得 checkout。完整恢复顺序见参考文件。

**治本**：只有确认当前 worker 确实加载了会重排的插件、且仓库存在自动重排风险时，才按
[恢复参考](reformat-noise-recovery.md) 配置本地忽略的覆盖项；其他环境不引入该配置。
