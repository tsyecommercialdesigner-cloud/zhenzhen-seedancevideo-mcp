# 成员安装与维护手册

## 1. 环境准备与适用范围

本手册对应 **0.1.0.dev1**，预期标签 **v0.1.0.dev1**（开发预发行版）。包版本、锁文件及入口版本为 0.1.0.dev1；发布、最终提交 SHA、资产摘要及发布验收结果待确认，请以对应 Release 的实际记录为准。完整产物集合和部分模型仍待核实，Job 生命周期限制未修复。

仅 Windows；需要 Git、PowerShell 7、uv、可获得的 Python 3.12.14 和 GitHub/包源访问权限。锁定 MCP SDK 2.3.0；传输为本地 stdio，协议版本由客户端与 SDK 协商，具体版本以检查输出为准。uv 安装时按锁文件取得依赖；代理／包源问题应在安装阶段处理。MCP 的网络代理配置不会自动配置 uv。Codex Desktop、Claude Desktop和DeepSeek Harness Desktop已有工具发现/共享查询证据，Codex与DSH已有跨Host主视频交付证据；具体版本和范围见[验证记录](docs/verification-add-local-video-generation-service.md)，不代表任意Host兼容保证。

默认发行入口已接通已核实供应商适配器，但EXECUTION_MODE默认local，不执行供应商或下载网络请求。管理员显式配置provider并重启后，新正式提交可自动上传、生成、查询和下载。发行入口及实际Host已有相应验收证据；完整产物集合仍待核实。Job生命周期调查已关闭，但启动器终止可能连带结束后端的兼容性限制未修复，不重开排查。合成适配器只在开发测试目录内，不随发行包提供，也没有用户环境变量后门。请勿用“任务 accepted”判断已向供应商提交。

## 2. 项目初始化与固定版本安装

建议使用 Git 固定发布标签；目标目录必须不存在，已有目录按升级步骤处理。

```powershell
$ErrorActionPreference = 'Stop'
$ProjectDir = 'D:\MCP\zhenzhen-seedancevideo-mcp'
$ExpectedCommit = Read-Host '输入 v0.1.0.dev1 Release 记录的完整提交 SHA'
if ($ExpectedCommit -notmatch '^[0-9a-fA-F]{40}$') { throw '需要完整的 40 位提交 SHA。' }
if (Test-Path -LiteralPath $ProjectDir) { throw '目标已存在，请按升级步骤处理。' }
New-Item -ItemType Directory -Path 'D:\MCP' -Force | Out-Null
git clone --branch v0.1.0.dev1 --single-branch https://github.com/tsyecommercialdesigner-cloud/zhenzhen-seedancevideo-mcp.git $ProjectDir
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

版本预期输出 `0.1.0.dev1`；标签 checkout 为 detached HEAD 是正常的。安装后用本地编辑器填写安装目录 `.env`。文件是明文，应限制 NTFS ACL，仅授权实际运行账户和必要管理账户读取。以下源码包安装是替代方式。

### 使用 Release 源码包

发布后从仓库 Release `v0.1.0.dev1` 下载 `zhenzhen_seedancevideo_mcp-0.1.0.dev1.tar.gz` 和 `SHA256SUMS.txt`。也可使用来源可信且另附 SHA-256 的本地构建包；即使版本号相同，本地构建的内容也可能不同，不应视为已发布资产。

在 PowerShell 执行。输入本机实际源码包路径；目标目录必须不存在，不覆盖已有安装。

```powershell
$ErrorActionPreference = 'Stop'
$Archive = (Resolve-Path -LiteralPath (Read-Host '输入已核对 SHA-256 的源码包绝对路径')).Path
$ExpectedSHA256 = Read-Host '输入可信 SHA256SUMS.txt 中该源码包的 SHA-256'
if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $ExpectedSHA256) { throw '源码包 SHA-256 不匹配。' }
$ProjectDir = 'D:\MCP\zhenzhen-seedancevideo-mcp'
if (Test-Path -LiteralPath $ProjectDir) { throw '目标已存在，请按升级流程处理。' }
New-Item -ItemType Directory -Path $ProjectDir | Out-Null
tar -xf $Archive -C $ProjectDir --strip-components 1
if ($LASTEXITCODE -ne 0) { throw '解包失败，停止安装。' }
uv --directory $ProjectDir sync --frozen --no-dev
if ($LASTEXITCODE -ne 0) { throw '冻结安装失败，停止接入。' }
uv --directory $ProjectDir run --no-sync zhenzhen-seedance-video --version
if ($LASTEXITCODE -ne 0) { throw '入口检查失败。' }
if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir '.env'))) {
    [IO.File]::Copy((Join-Path $ProjectDir '.env.example'), (Join-Path $ProjectDir '.env'), $false)
}
```

预期版本 0.1.0.dev1。源码包包含 uv.lock、源码和文档；wheel 可安装，但单独 wheel 不携带完整 uv 项目，成员默认使用上述源码包。安装不依赖维护者 `.venv`、测试文件或用户 HOME 中的 `.env`。

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

任务库与默认输出位于 `%LOCALAPPDATA%\ZhenzhenSeedanceVideo`，独立于安装目录；显式输出目录按任务接收时固定。删除／切换安装目录不会自动删除状态或产物。若自行把输出指定到安装目录内，则不享有此物理分离保证，删除前必须另行保存。

### 日常启动

日常启动复用已安装环境，不同步依赖：

```powershell
uv --directory 'D:\MCP\zhenzhen-seedancevideo-mcp' run --no-sync zhenzhen-seedance-video stdio
```

等待协议输入时无普通输出是正常行为，不要向 stdout 写日志。仅版本命令成功不代表业务闭环。客户端先发现 Tools，然后调用 get_service_status 和 get_capabilities；execution_mode=local／generation_execution=not_implemented表示当前未启用；provider模式下为adapter_installed。provider=unverified表示没有通过启动健康探测验证上游。Resources、Prompts 当前为空。

## 3. 本地可用性检查

目标版本包含模块 `zhenzhen_seedance_video.protocol_probe`；**已发布的 v0.1.0.dev0 不包含该模块**。发布 v0.1.0.dev1 后，先将实际安装目录 `.env` 的 `ZHENZHEN_SEEDANCE_EXECUTION_MODE` 设为 `local` 并填写密钥，运行：

当前未发布源码包及 wheel 均已在隔离 Windows 环境安装并运行该检查；wheel 验证通过锁文件冻结同步准备依赖，再卸载源码安装并安装 wheel。结果不代表已发布版本包含该脚本，也不代表空缓存离线安装已验证。

```powershell
uv --directory 'D:\MCP\zhenzhen-seedancevideo-mcp' run --no-sync python -m zhenzhen_seedance_video.protocol_probe
if ($LASTEXITCODE -ne 0) { throw '本地协议检查失败，请查看脱敏错误。' }
```

预期退出码 0，输出协商协议版本、工具数、`resources=0 templates=0 prompts=0 local=ok`；检查使用独立临时状态目录、120 秒异步超时和只读能力及状态查询，不提交任务、不调用供应商。超时后的进程收尾可能额外耗时。provider 模式被拒绝；失败时返回非零退出码，仅报告错误类别和隔离目录路径，不输出子进程原始诊断；隔离目录可能保留以供人工核对，不删除用户状态。成功信息仅在隔离目录清理成功后输出。此脚本仅覆盖 SDK stdio，不代表实际 Host 或供应商验收。当前 v0.1.0.dev0 用户继续通过 Host 调用以下只读工具：

1. 发现 `get_service_status` 与 `get_capabilities`；缺失即连接或发现失败。
2. 调用 `get_service_status({})`，确认 `execution_mode=local`、`dispatch_allowed=false`，并检查 `storage_fault`。`provider=unverified` 不表示上游已验证。
3. 调用 `get_capabilities({})`，预期列出 `seedance-video` 26 个模型与独立 `zhenzhen-upscaler`；返回错误或超时均不视为通过。

Host 检查不提交生成任务、不调用供应商，但连接会启动或接入本地后端并访问同用户状态库；如不希望接入现有任务库，请先在专用隔离 Windows 用户或环境中检查。Host 的调用超时和错误按实际客户端显示，不把版本命令当作协议验证。Sandbox 的 SDK stdio 验证及实际 Host 验证范围见[验收记录](docs/verification-add-local-video-generation-service.md)。

## 4. 本地客户端配置

编辑前私有备份，合并目标服务项，保留其他服务和认证；保存、启用并按 Host 要求重启，再执行上面的检查。当前证据覆盖 Codex Desktop、Claude Desktop 和 DSH Desktop 的工具发现／共享查询；Codex 与 DSH 有跨 Host 主视频交付证据，但不代表所有版本或所有 Host 已验证。Host 配置无需包含 API Key。

Codex Desktop 的 TOML 服务表：

```toml
[mcp_servers.zhenzhen-seedance-video]
command = "uv"
args = ["--directory", "D:\\MCP\\zhenzhen-seedancevideo-mcp", "run", "--no-sync", "zhenzhen-seedance-video", "stdio"]
```

Claude Desktop（Claude-3p）的 JSON 服务项；仅合并 `mcpServers` 下的目标项：

```json
{
  "mcpServers": {
    "zhenzhen-seedance-video": {
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

DeepSeek Harness 的 `cordis.patch.yml` 中合并以下独立 `insert`，先检查现有条目，避免相同 serverName 重复。DSH 中 `seedance-video` 是本服务的短别名，与上面的 `zhenzhen-seedance-video` 一一对应；请先确认该别名未被其他服务占用。根据本机 DSH 官方文档镜像（dsh-plugin-guide 0.3.39）核对字段，实际 Desktop 曾以隔离安装完成工具发现；下面 `uv` 命令组合仅为配置示例，须在目标 Host 验证。

```yaml
- insert:
    - id: seedance-video
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: seedance-video
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

1. 记录当前包版本、包 SHA-256 和可用的发布 SHA。正常退出全部 Host，确认旧后端结束；不能确认时停止维护。
2. 保留私有 `.env` 原文件、权限及旧安装，不用解包覆盖它。下载目标版本 v0.1.0.dev1 的源码包并核对 SHA-256，按上面的首次安装步骤将其安装到独立候选目录；不要启动或填写新密钥探测供应商。
3. 首次安装步骤会在候选目录创建空密钥 `.env` 模板。确认该候选文件确为本次新建的空模板后，在停机窗口由用户安全替换为原 `.env` 的私有副本；如果候选已含任何用户配置，停止并手工合并，不能覆盖。核对内容摘要和 NTFS 权限，记录原／新 Host 路径。状态与输出不迁移，备份按 [离线维护](docs/storage-recovery.md) 完成。
4. 新包冻结安装和版本检查通过后，将 Host 的 `--directory` 指向候选目录，重启并执行第 3 节的工具发现与本地状态检查；检查失败时停止并按第 5 步评估回滚。工作区有源码改动或未跟踪冲突时先停止，不强制覆盖。
5. 回滚程序仅当旧程序支持现有 schema 时进行：退出所有 Host，恢复原 Host 路径及旧安装，保留当前任务库。过新 schema 明确拒绝，不能降级或重建空库。首期没有自动升级／回滚命令。

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

- 为什么安装后不能生成？默认EXECUTION_MODE=local。只有显式provider并重启后新接收任务才授权执行，旧/local任务不会自动获得授权。
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

启用与旧任务保护的详细步骤见[执行保护](docs/configuration.md#发行入口执行保护)。实际Host零调用验收必须保持local，不要为检查工具发现切到provider。
