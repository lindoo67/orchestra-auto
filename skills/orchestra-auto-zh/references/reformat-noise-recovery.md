# 格式化重排噪声：取证与恢复

**何时读取**：worker 完成后发现异常大的未提交 diff，且逐文件检查显示大面积纯格式变化。
行数异常只是调查信号，不能据此断定内容可丢弃。

## 先保护真实工作

由 worker 在所属 worktree 执行恢复；coordinator 保存证据、验收结果并给出具体打回项。
任何还原或 stash 前，保存以下证据到 repo 外、权限受控的目录，并确认文件可读：

```bash
git status --porcelain=v1 -uall
git diff --binary > <证据目录>/worktree.patch
git diff --cached --binary > <证据目录>/index.patch
git ls-files --others --exclude-standard > <证据目录>/untracked.txt
```

未跟踪文件需逐个复制或归档；patch 不包含它们。若 patch 可能含凭证，限制访问并避免贴进消息。
逐文件比较 `HEAD`、index、工作区和 worker 的编辑记录，标出真实修改与格式噪声。
`git diff --cached` 非空只说明 index 有内容，**不能证明工作区其他内容可丢弃**。

## 恢复

优先从 worker 编辑历史或已提交版本重建真实改动。仅在逐文件确认并备份其全部真实改动后，
才对该文件使用 `git restore` / `git checkout`；恢复后核对 diff 与测试结果。混合 hunk 难以
可靠拆开时，保留证据并让 worker 在干净副本重做，避免靠去空白比较猜测语义等价。
两轮仍不能把 diff 收敛到预期范围时停止自动修补，向 coordinator 报告。

## 预防条件

仅当当前 worker 确实加载了会重排的 formatter、且其自动格式化与仓库风格冲突时，在**该
worktree** 根目录写入本地 formatter 覆盖项：

```json
{"format":{"enabled":false}}
```

把该文件加入该 worktree 的本地忽略（不是被跟踪的忽略文件），不提交。其他 worker 或已有格式
规范的仓库遵循其原有工具配置。此设置是针对已确认故障的本地修复，不是每票固定前置步骤。
