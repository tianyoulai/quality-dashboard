# QC 统一看板本机调度草稿（launchd）

这套目录只放 **macOS 本机定时任务示例**，对应当前项目最适合落地的两条本机链路：

1. `com.qc.dashboard.daily-refresh.plist.sample`
   - 13:05 / 17:35 跑 `jobs/daily_refresh.py`
   - 默认按 **T-1** 业务日期扫描企微缓存，并在结束后推送企微群状态消息
   - 负责主数据链：企微缓存扫描、Google Sheet 申诉拉取、入库、数仓刷新、告警刷新

2. `com.qc.dashboard.daily-newcomer-refresh.plist.sample`
   - 17:10 跑 `jobs/daily_newcomer_refresh.py --scan-days 3 --deep-scan`
   - 负责新人专项链：最近 3 天候选文件扫描、回填补导、必要时刷新相关结果

## 为什么放在本机

因为这两条链都依赖企业微信客户端缓存目录：

- `~/Library/Containers/com.tencent.WeWorkMac/Data/Documents/Profiles`

所以它们不适合直接搬到 GitHub Actions。

## 使用步骤

### 1. 先准备日志目录

```bash
mkdir -p /Users/laitianyou/WorkBuddy/20260326191218/logs/launchd
```

### 2. 复制 sample 为正式 plist

```bash
cp /Users/laitianyou/WorkBuddy/20260326191218/ops/launchd/com.qc.dashboard.daily-refresh.plist.sample ~/Library/LaunchAgents/com.qc.dashboard.daily-refresh.plist
cp /Users/laitianyou/WorkBuddy/20260326191218/ops/launchd/com.qc.dashboard.daily-newcomer-refresh.plist.sample ~/Library/LaunchAgents/com.qc.dashboard.daily-newcomer-refresh.plist
```

### 3. 挂载并立即生效

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.qc.dashboard.daily-refresh.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.qc.dashboard.daily-newcomer-refresh.plist
launchctl kickstart -k gui/$(id -u)/com.qc.dashboard.daily-refresh
launchctl kickstart -k gui/$(id -u)/com.qc.dashboard.daily-newcomer-refresh
```

> `daily-refresh` sample 已开启 `RunAtLoad=true`，首次挂载后会立即跑一次，方便你立刻验证“今天会不会发群消息”。

如果之前已经挂过同名任务，先执行：

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.qc.dashboard.daily-refresh.plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.qc.dashboard.daily-newcomer-refresh.plist
```

## 查看运行情况

```bash
tail -f /Users/laitianyou/WorkBuddy/20260326191218/logs/launchd/daily-refresh.log
tail -f /Users/laitianyou/WorkBuddy/20260326191218/logs/launchd/daily-newcomer-refresh.log
launchctl print gui/$(id -u)/com.qc.dashboard.daily-refresh | egrep "state =|runs =|last exit code"
launchctl print gui/$(id -u)/com.qc.dashboard.daily-newcomer-refresh | egrep "state =|runs =|last exit code"
```

## 我建议先这样用

- 主链先上：`daily-refresh`
- 新人链观察 2~3 天后再决定是否长期保持 `--deep-scan`
- 云端日报继续留给 `.github/workflows/daily-report.yml`
- AI 开发推进继续留给 WorkBuddy 自动化，不要和业务数据链混在一起
