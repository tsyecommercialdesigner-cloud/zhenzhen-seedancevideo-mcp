# 成员安装与维护手册

本文对应已发布的 `v0.1.0.dev3` 开发预发行版；实际验收范围及仍待核实的事项见下方记录。

## 1. 环境准备与适用范围

固定版本命令对应已发布的 [v0.1.0.dev3 开发预发行版](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-seedancevideo-mcp/releases/tag/v0.1.0.dev3)，标签提交 SHA 为 `66a9c1075a1253361c2fb532f7dfc91f3c4a852e`。源码包 SHA-256 为 `82c9a32a03b45113a4eb254ab6c51f62f6aad7cad1af520f15811139f798ddd4`，wheel SHA-256 为 `e4dc85f5ba53f7f3222bbf2048d8f3b7797933cf9443f90ae9ea80f3442ec342`。新 Schema 实际 Host 展示、完整产物集合和部分模型仍待核实，协议探针曾偶发失败且根因未定位，Job 生命周期限制未修复。

仅 Windows；需要 Git、PowerShell 7、uv、可获得的 Python 3.12.14 和 GitHub/包源访问权限。锁定 MCP SDK 2.3.0；传输为本地 stdio，协议版本由客户端与 SDK 协商，具体版本以检查输出为准。uv 安装时按锁文件取得依赖；代理／包源问题应在安装阶段处理。MCP 的网络代理配置不会自动配置 uv。Codex Desktop、Claude Desktop和DeepSeek Harness Desktop已有工具发现/共享查询证据，Codex与DSH已有跨Host主视频交付证据；具体版本和范围见[验证记录](docs/verification-add-local-video-generation-service.md)，不代表任意Host兼容保证。

本版本默认 provider，填写密钥后正式提交的新任务可自动上传、生成、查询和下载，可能产生费用；显式 local 不执行供应商及下载网络请求。旧版本的实际 Host 验收范围不能推广至本次变更；完整产物集合仍待核实。Job 生命周期调查已关闭，兼容性限制未修复。请勿用“任务 accepted”判断已向供应商提交。

**想要生成视频？** 本版本新安装默认 `provider`；填写密钥后，正式提交新任务可能产生费用。旧安装显式配置的 `local` 不会因升级自动改变，详见[启用供应商生成](#启用供应商生成)。

## 2. 项目初始化与固定版本安装

使用 Git 固定发布标签安装；目标目录必须不存在，已有 Git 安装目录按升级步骤处理。

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-seedancevideo-mcp'
$ExpectedCommit = Read-Host '输入已发布 Release 中经核对的完整标签提交 SHA'
if ($ExpectedCommit -notmatch '^[0-9a-fA-F]{40}$') { throw '需要完整的 40 位提交 SHA。' }
if (Test-Path -LiteralPath $ProjectDir) { throw '目标已存在，请按升级步骤处理。' }
New-Item -ItemType Directory -Path 'D:\MCP' -Force | Out-Null
git clone --branch v0.1.0.dev3 --single-branch https://github.com/tsyecommercialdesigner-cloud/zhenzhen-seedancevideo-mcp.git $ProjectDir
if ($LASTEXITCODE -ne 0) { throw 'clone 失败，请检查仓库权限和网络。' }
$ActualCommit = (git -C $ProjectDir rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $ActualCommit -ne $ExpectedCommit) { throw '标签提交不匹配。' }
uv --directory $ProjectDir sync --frozen --no-dev
if ($LASTEXITCODE -ne 0) { throw '锁定安装失败。' }
uv --directory $ProjectDir run --no-sync zhenzhen-seedance-video --version
if ($LASTEXITCODE -ne 0) { throw '入口检查失败。' }
if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir '.env'))) {
    Copy-Item -LiteralPath (Join-Path $ProjectDir '.env.example') -Destination (Join-Path $ProjectDir '.env') -ErrorAction Stop
}
```

版本预期输出 `0.1.0.dev3`；标签 checkout 为 detached HEAD 是正常的。安装后用本地编辑器填写安装目录 `.env`。文件是明文，应限制 NTFS ACL，仅授权实际运行账户和必要管理账户读取。安装不依赖维护者 `.venv`、测试文件或用户 HOME 中的 `.env`。

### 配置与初始化

用编辑器填写实际安装目录 `.env` 的 `ZHENZHEN_SEEDANCE_API_KEY`，不填通用 API_KEY。示例密钥为空，未填写会明确失败；如要使用环境变量，删除该字段再配置进程／Windows 当前用户环境变量。文件优先，仅缺失字段回退；空、重复或非法值不回退。不要把密钥写进 Host JSON、命令行、截图或版本库。代理、CA、输出目录等见 [配置说明](docs/configuration.md)。

在 PowerShell 中运行以下命令；如安装在其他目录，先将 `$ProjectDir` 改为实际安装路径。命令保留已有 `.env`，缺失时从空密钥模板创建，然后用 Notepad 打开：

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-seedancevideo-mcp'
$EnvPath = Join-Path $ProjectDir '.env'
$EnvExamplePath = Join-Path $ProjectDir '.env.example'
if (Test-Path -LiteralPath $EnvPath) {
    Write-Host '保留已有 .env，请检查需要更新的字段。'
} else {
    if (-not (Test-Path -LiteralPath $EnvExamplePath -PathType Leaf)) {
        throw '缺少 .env.example，请核对安装目录。'
    }
    [IO.File]::Copy($EnvExamplePath, $EnvPath, $false)
}
notepad $EnvPath
if ($LASTEXITCODE -ne 0) { throw '无法打开 .env，请使用本地文本编辑器编辑。' }
```

在编辑器中填写并以 UTF-8 保存；不要把密钥写入 PowerShell 命令或历史。`.env` 是明文，限制 NTFS ACL，只允许运行账户和必要管理账户读取；修改后重启 Host 管理的服务。

### 启用供应商生成

1. 在实际安装目录 `.env` 填写 `ZHENZHEN_SEEDANCE_API_KEY`；本版本模板默认 `provider`，v0.1.0.dev2 模板默认 `local`。第 3 节的本地检查可选；隔离探针不要求更改用户配置，不调用供应商。其他版本按其标签中的手册操作。
2. 若有效模式为 `local`，需要生成时将安装目录 `.env` 中的模式行改为 `ZHENZHEN_SEEDANCE_EXECUTION_MODE=provider`；该行缺失但旧版本仍默认为 local 时，添加该行。保存为 UTF-8，不要重复添加同名字段。有效模式只有 `local` 和 `provider`。使用进程／用户环境变量时须先删除或注释 `.env` 中对应字段，因为文件优先且空值不回退。
3. 正常退出同一 Windows 用户下连接此服务的**所有 Host**，等待并确认共享后端退出，然后重新启动 Host。不能确认旧后端退出时先停止排查；不要强杀后端或删除任务库。不同 Host 显式配置冲突时，新接入方会被拒绝。
4. 在 Host 中调用 `get_service_status({})`。期望 `execution_mode=provider`、`generation_execution=adapter_installed`；在 Host 已连接且后端正常调度时 `dispatch_allowed=true`。若仍显示 `local` 或 `not_implemented`，检查正在使用的安装目录 `.env`、配置优先级和旧后端是否退出；若显示配置冲突，统一各 Host 设置后重新启动。`provider=unverified` 表示未通过启动健康探测验证上游，并不证明供应商连接成功。
5. 检查模型能力并可选运行无生成副作用的预检。确认用户已授权费用后，正式提交**新任务**，使用该新任务独有且稳定的 `request_key`；后端自动提交、查询和下载。正式提交可能产生费用，预检通过或任务 `accepted` 不代表上游已经接收或生成成功。

`local` 模式已接收的旧任务不会因切换到 `provider` 自动获得供应商执行授权；启动时仍处于自动执行状态、未结束且未在本地取消的未授权任务会转为待处理，标记 `PROVIDER_EXECUTION_NOT_AUTHORIZED`。重复原 `request_key` 只会找回原任务，不会补授权。先查询并核对旧任务；对于结果不明的远端提交，不要更换请求标识盲目重新生成。具体边界见[配置说明](docs/configuration.md#发行入口执行保护)。

任务库与默认输出位于 `%LOCALAPPDATA%\ZhenzhenSeedanceVideo`，独立于安装目录；显式输出目录按任务接收时固定。删除／切换安装目录不会自动删除状态或产物。若自行把输出指定到安装目录内，则不享有此物理分离保证，删除前必须另行保存。

### 日常启动

日常启动复用已安装环境，不同步依赖：

```powershell
uv --directory 'D:\MCP\zhenzhen-seedancevideo-mcp' run --no-sync zhenzhen-seedance-video stdio
```

等待协议输入时无普通输出是正常行为，不要向 stdout 写日志。仅版本命令成功不代表业务闭环。客户端先发现 Tools，然后调用 get_service_status 和 get_capabilities；execution_mode=local／generation_execution=not_implemented表示当前未启用；provider模式下为adapter_installed。provider=unverified表示没有通过启动健康探测验证上游。Resources、Prompts 当前为空。

## 3. 本地可用性检查

本版本协议检查使用独立 local 配置和状态，不要求切换用户的 provider 配置。v0.1.0.dev2 检查行为见该标签的手册；v0.1.0.dev0 不包含此模块。

v0.1.0.dev2 的受控发布准备在 Windows CI 中分别安装源码包与 wheel，并运行版本及 local 协议检查；依赖通过锁文件获取，不代表空缓存离线安装通过。实际 Host 对本版本新 Schema 的展示尚未验证。

```powershell
uv --directory 'D:\MCP\zhenzhen-seedancevideo-mcp' run --no-sync python -m zhenzhen_seedance_video.protocol_probe
if ($LASTEXITCODE -ne 0) { throw '本地协议检查失败，请查看脱敏错误。' }
```

预期退出码 0，输出协商协议版本、工具数、`resources=0 templates=0 prompts=0 local=ok`；检查使用独立临时配置和状态、占位密钥、120 秒异步超时及只读查询，不提交任务、不调用供应商。超时后的进程收尾可能额外耗时；失败时仅报告错误类别和隔离目录路径，隔离目录可能保留。成功信息仅在清理成功后输出。此脚本仅覆盖 SDK stdio，不代表实际 Host 或供应商验收。Host 可另外调用以下只读工具：

1. 发现 `get_service_status` 与 `get_capabilities`；缺失即连接或发现失败。
2. 调用 `get_service_status({})`，检查 `execution_mode` 和 `storage_fault`。provider 模式下正常调度为 `adapter_installed`；`provider=unverified` 不表示上游已验证。
3. 调用 `get_capabilities({})`，预期列出 `seedance-video` 26 个模型与独立 `zhenzhen-upscaler`；返回错误或超时均不视为通过。

Host 只读检查自身不提交生成任务，但连接会启动或接入本地后端并访问同用户状态库；provider 模式启动可能恢复此前已授权的任务并访问供应商。要保证隔离检查不触发这些行为，请使用专用隔离 Windows 用户或环境及显式 local 配置。Host 的调用超时和错误按实际客户端显示，不把版本命令当作协议验证。Sandbox 的 SDK stdio 验证及实际 Host 验证范围见[验收记录](docs/verification-add-local-video-generation-service.md)。

## 4. 本地客户端配置

编辑前私有备份，合并目标服务项，保留其他服务和认证；保存、启用并按 Host 要求重启，再执行上面的检查。当前证据覆盖 Codex Desktop、Claude Desktop 和 DSH Desktop 的工具发现／共享查询；Codex 与 DSH 有跨 Host 主视频交付证据，但不代表所有版本或所有 Host 已验证。Host 配置无需包含 API Key。

Codex Desktop 的 TOML 服务表：

```toml
[mcp_servers.zhenzhen-seedancevideo-mcp]
command = "uv"
args = ["--directory", "D:\\MCP\\zhenzhen-seedancevideo-mcp", "run", "--no-sync", "zhenzhen-seedance-video", "stdio"]
```

Claude Desktop（Claude-3p）的 JSON 服务项；仅合并 `mcpServers` 下的目标项：

```json
{
  "mcpServers": {
    "zhenzhen-seedancevideo-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "D:\\MCP\\zhenzhen-seedancevideo-mcp",
        "run",
        "--no-sync",
        "zhenzhen-seedance-video",
        "stdio"
      ]
    }
  }
}
```

DeepSeek Harness 的 `cordis.patch.yml` 中合并以下独立 `insert`，先检查现有条目，避免相同 serverName 重复。旧配置可能使用 `seedance-video` 或 `zhenzhen-seedance-video`；核对归属后手动迁移到统一名称，避免同一 Host 重复注册。不会自动修改 Host 配置。新名称在实际 Host 的表现尚未验证。

```yaml
- insert:
    - id: zhenzhen-seedancevideo-mcp
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: zhenzhen-seedancevideo-mcp
        transport: stdio
        command: uv
        args:
          - '--directory'
          - 'D:\MCP\zhenzhen-seedancevideo-mcp'
          - 'run'
          - '--no-sync'
          - 'zhenzhen-seedance-video'
          - 'stdio'
        env:
          NO_PROXY: 'localhost,127.0.0.1,::1'
          no_proxy: 'localhost,127.0.0.1,::1'
```

这两个变量为该 MCP 子进程覆盖代理旁路列表，用于规避部分 DSH 版本注入 `[::1]` 后 Python HTTP 客户端解析失败的问题。合并前先核对原有 `NO_PROXY`／`no_proxy` 和该服务已有 `env`：将仍需直连的域名、内网地址等旁路项加入上述两个值，保留其他环境变量及设置，不要只保留示例中的回环地址；不要加入 `[::1]`。此处不放 API 密钥。本项目的供应商 HTTP 客户端使用独立网络策略，代理及旁路配置见[配置说明](docs/configuration.md)，不要将这里的 Host 兼容设置当作供应商网络策略。

示例的命令形式及旁路值已在 Windows 隔离 local 环境中通过 DSH 0.2.1-rc.5 MCP 客户端插件及实际 DSH Desktop 检查：Desktop 验收使用临时服务名、隔离安装路径和额外的隔离环境变量，并在入口记录旁路值；子进程通过大小写两种名称均读取到覆盖后的值，状态和能力工具调用成功。保留自定义旁路项仅经隔离插件宿主测试。未复现所述 HTTP 客户端启动错误，不能证明所有版本的问题已修复。配置生效后应重新发现工具并检查本地服务状态。详见[验证记录](docs/verification-add-local-video-generation-service.md)。

Desktop 使用 desktop profile；文档显示各随附 profile 使用同一 MCP 客户端机制，web 与 multica 可按其各自 profile 合并，但本项目这两个 profile **尚未实测**，不能外推 Desktop 的成功。目标文件为 `[]` 时替换为上述列表；已有条目时追加为同一顶层列表项，已存在相同服务则就地合并；保留注释、其他插件和私有配置。临时补丁与持久 profile 的生效范围以所用版本为准，修改后按客户端要求加载或重启并验证。Claude Code／其他 Host 的具体 schema 和 CLI 注册及 PowerShell、Bash、Zsh 对应组合未单独验收；配置或 Host 版本变更后重新发现工具。

API Key 用于供应商；本地前后端 RPC 使用受当前用户目录权限保护的随机令牌，两者不同。不要手动复制令牌或编辑发现文件。同用户所有 Host 共享任务，不做项目权限隔离。

## 5. 功能与启动排障

按 [工具手册](docs/agent-tools.md) 查询能力、可选预检、优化授权、提交／找回、等待、恢复与复制。授权询问在提交前；正式提交即授权自动执行。request_key 防止本地重复接收，不代表上游幂等。提交结果不明不能换 key 自动重提。取消工具等待不撤销已接受任务；放弃跟踪可能仍计费且会清理托管输入。

视频以绝对路径和摘要交付，不通过 MCP 返回二进制。相对复制目标须提供 workspace_root，越出工作区需显式绝对路径。默认不覆盖，默认长期保留视频；素材仅清理登记副本。查询与下载预算独立，费用未返回是未知，不是免费。SUCCESS及实扣完整响应已有脱敏证据；其他未明规则见供应商契约台账。

启动报配置冲突时，仅新 Host 被拒绝；统一配置并退出所有 Host 后重启。无法确认旧后端退出、schema 过新或库损坏时停止操作，不强杀生产后端，不删库或标记文件。排障见 [本地运行](docs/local-rpc.md) 和 [状态维护](docs/storage-recovery.md)。

### 升级与回滚

以下适用于以 `git clone` 安装的目录。先正常退出同一 Windows 用户下的全部 Host，并确认共享后端已退出；无法确认时停止。记录当前版本、完整提交 SHA 和 Host 路径；按[离线维护](docs/storage-recovery.md)在私有位置备份 `.env`、其权限、任务状态、托管素材及实际输出目录。**备份不能替代下面的数据兼容检查。**

从目标版本的 Release 核对标签与完整提交 SHA，并阅读该版本升级说明及数据库兼容要求。每次发布候选须提前将首次安装和下方升级命令中的目标标签、预期版本更新为本次目标，核对包版本及锁文件；尚未发生的发布和验收标为待确认。发布后按实际 Release 回填完整提交 SHA、Release 信息及验收范围，保留未验证项，不改写已发布标签及资产。原目录 `.env` 保持原样；如新版本有必需配置字段，按说明手动合并，不用新模板覆盖。建议将新任务的输出配置在安装目录外；已接收任务记录的输出目录不会自动改址，保留原产物并另行备份。

安装时按标签克隆会处于 detached HEAD，因此不使用 `git pull` 跟随分支。下面先获取指定标签、核对 SHA，再切换到该标签；请替换目录和目标标签，输入 Release 中核对过的完整 SHA：

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-seedancevideo-mcp'
$TargetTag = 'v0.1.0.dev3' # 目标标签发布后使用；其他版本请替换
$ExpectedCommit = Read-Host '输入目标 Release 中经核对的完整提交 SHA'
if ($ExpectedCommit -notmatch '^[0-9a-fA-F]{40}$') { throw '需要完整的 40 位提交 SHA。' }
$Origin = git -C $ProjectDir remote get-url origin
if ($LASTEXITCODE -ne 0 -or $Origin -ne 'https://github.com/tsyecommercialdesigner-cloud/zhenzhen-seedancevideo-mcp.git') { throw '仓库地址不符，请先核对。' }
$Changes = git -C $ProjectDir status --porcelain --untracked-files=normal
if ($LASTEXITCODE -ne 0) { throw '无法检查仓库状态。' }
if ($Changes) { throw '存在本地改动或未跟踪文件；请先安全保留并处理，不要强制覆盖。' }
$PreviousCommit = git -C $ProjectDir rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw '无法记录原提交。' }
Write-Host "升级前提交：$PreviousCommit；请妥善记录供回滚。"
git -C $ProjectDir fetch origin tag $TargetTag
if ($LASTEXITCODE -ne 0) { throw '获取标签失败，请核对网络及本地标签。' }
$TargetCommit = git -C $ProjectDir rev-parse --verify "refs/tags/$TargetTag^{commit}"
if ($LASTEXITCODE -ne 0 -or $TargetCommit -ne $ExpectedCommit) { throw '目标标签提交与 Release 不一致，停止升级。' }
git -C $ProjectDir switch --detach --no-overwrite-ignore "refs/tags/$TargetTag"
if ($LASTEXITCODE -ne 0) { throw '切换失败；请检查文件冲突，保留配置与数据。' }
uv --directory $ProjectDir sync --frozen --no-dev
if ($LASTEXITCODE -ne 0) { throw '锁定安装失败；不要启动 Host。' }
uv --directory $ProjectDir run --no-sync zhenzhen-seedance-video --version
if ($LASTEXITCODE -ne 0) { throw '入口检查失败；不要启动 Host。' }
```

核对入口版本与目标 Release 一致后，在停机状态按第 3 节执行适用于目标版本的本地协议检查，再重启 Host 并检查工具发现和服务状态。原安装路径不变时无需修改 Host 路径；若保留的 `.env` 显式设置 `local`，升级不会自动改成 `provider`。本地检查不代表已验证供应商或跨版本升级。

工作区中的未跟踪产物不一定阻止 Git 更新，但若目标版本需要写入同一路径则 Git 会拒绝；已跟踪文件的本地修改也可能造成冲突。本手册命令更保守：只要 `git status` 报告本地改动或未跟踪文件就停止。`.gitignore` 不涵盖所有输出目录，且被忽略文件不出现在普通状态中；`--no-overwrite-ignore` 会拒绝覆盖与目标版本冲突的忽略文件。不要用 `git reset --hard`、`git clean` 或强制切换处理产物。

需要回滚时，先退出全部 Host 并确认后端停止，核对旧版本能够读取当前数据库 schema；不兼容时停止并保留当前库。确认兼容且工作区干净后，可用 `git -C $ProjectDir switch --detach --no-overwrite-ignore $PreviousCommit` 切回记录的提交，再执行 `uv --directory $ProjectDir sync --frozen --no-dev`、版本和本地协议检查。分别检查每条命令是否成功；失败不要启动 Host。回滚代码不会回滚数据或撤销远端任务。v0.1.0.dev1 → v0.1.0.dev2 → v0.1.0.dev1 已在 Windows 隔离 local 环境演练，使用合成本地任务和登记的测试产物；不代表真实用户数据、其他版本、schema 迁移或供应商任务均兼容，详见[验证记录](docs/verification-add-local-video-generation-service.md)。

数据备份不能当作程序回滚。旧备份会遗漏备份后发生的远端请求；禁止恢复 queued 快照后直接启动派发。必须先在离线副本中将所有未结束任务置为需要核对、保留未知占位，结合原库和远端可靠证据处理窗口。未核实上游反查时保持待处理，不自动重派。详见状态维护说明；首期无自动恢复备份工具。

## 6. 文件清单

仓库包含 `src/`、`pyproject.toml`、`uv.lock`、`.python-version`、测试、OpenSpec、CI、README 和本手册；`.venv`、本地缓存和构建输出由本机生成。默认安装目录为 `D:\MCP\zhenzhen-seedancevideo-mcp`，运行入口为 `zhenzhen-seedance-video`；任务库和默认产物位于 `%LOCALAPPDATA%\ZhenzhenSeedanceVideo`，输出目录可配置。不存在额外的成员 ZIP 交付。

## 7. 资源清单

当前提供 23 个 Tools：`get_service_status`、`get_capabilities`、`preflight_video_task`、`submit_video`、`upscale_video`、`find_task_by_request_key`、`get_task`、`list_tasks`、`wait_task`、`refresh_task`、`resume_task_tracking`、`retry_unsubmitted_task`、`cancel_task`、`abandon_task`、`repair_task_materials`、`retry_material_cleanup`、`retry_task_download`、`list_artifacts`、`verify_artifact`、`copy_artifact`、`get_prompt_optimization_policy`、`set_prompt_optimization_policy` 和 `get_diagnostic`。Resources、资源模板和 Prompts 当前无业务内容。参数及调用示例见[工具手册](docs/agent-tools.md)和实际 Host 的工具 schema；历史阶段记录以[最新验证记录](docs/verification-add-local-video-generation-service.md)为准。

## 8. 功能说明

先查询服务状态和模型能力，可选预检；正式提交时提供稳定 `request_key` 与模型参数，后端排队、提交、轮询及下载。查询或有界等待观察任务状态；生成成功与本地产物就绪分别报告。按产物复制到显式目标，默认不覆盖。独立超分单独提交，不自动产生额外付费任务；具体流程见[工具手册](docs/agent-tools.md)。

## 9. 注意事项

同一 Windows 用户下所有 Host 共享任务，不进行项目权限隔离；Host 账号须有安装目录、状态库、输入及输出的必要权限。`.env` 为明文并需限制 ACL。超时、取消、有限重试及结果不明处理应按工具状态操作；`request_key` 仅是本地去重，不能保证上游幂等。产物完整集合仍待核实；Job 生命周期调查已关闭，兼容性限制未修复。

## 10. FAQ 与验证范围

- 为什么安装后不能生成，或看到 `not_implemented`？检查实际安装目录、模式及共享后端。显式 `local` 不派发供应商任务；按[启用供应商生成](#启用供应商生成)设置 `provider` 并重启后，新接收任务才获执行授权；旧 local 任务不会自动获得授权。
- 多个 Host 是否会多开生成额度？同一 Windows 用户共享后端与总额度；已有跨 Host 接续证据，特定 Host 与异常退出兼容性仍须按版本核对。
- 更新 `.env` 是否立即生效？后端统一配置，重启生效；提示词优化授权是可即时修改的独立业务偏好。
- 能否删除任务库修复？不能。未知付费任务仍可能运行，应保留记录并核对。
- 是否经过干净 Windows 验收？Windows Sandbox 中已验证离线冻结安装及 SDK stdio；实际 Host 是在本机另行验收，不将两者合并成全场景通过。
- Git、标签或依赖获取失败？核对仓库地址、权限、网络、包源、代理与 TLS；不要删除锁文件或浮动升级依赖。
- 入口缺失或 stdout 被污染？核对安装目录和 `uv sync --frozen --no-dev`，启动使用 `--no-sync`；stdout 仅用于协议，诊断查看 stderr。
- 超时或结果未知？按原 request_key 找回任务和异常名单，不换 key 盲目重提；回滚前核对 schema 和远端事实。

实际命令与结果见 [实施记录](docs/implementation-progress.md)。不会由成员启动命令自动安装依赖、修改 Host 或发起收费测试。


## 验收记录

Windows Sandbox 安装、三款实际 Host 工具发现和 Codex／DSH 的一次真实跨 Host 主视频交付分别有证据；见[验证记录](docs/verification-add-local-video-generation-service.md)及[业务验收](docs/host-delivery-acceptance-plan.md)。同版本安装切换隔离演练不代表跨版本升级／回滚通过；历史[验收模板](docs/windows-host-acceptance.md)中的旧状态按记录时点阅读。

v0.1.0.dev3 的本地 Windows 全量隔离测试为 637 项通过；功能 PR 的 Windows 检查通过，发布候选复用该检查并重新构建资产，受控发布准备分别验证了源码包和 wheel 的版本与 local 协议检查。既有真实 Host 和供应商业务证据不代表本版本的新 Schema 或完整产物集合已实测；协议探针历史偶发失败仍未定位。

启用与旧任务保护的详细步骤见[执行保护](docs/configuration.md#发行入口执行保护)。实际Host零调用验收必须保持local，不要为检查工具发现切到provider。
