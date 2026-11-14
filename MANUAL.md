# 成员安装与维护手册

## 版本与适用范围

本版本为 **0.1.0.dev0**，标签 **v0.1.0.dev0**（开发预发行版）。包版本、锁文件及入口版本均为 0.1.0.dev0。已发布 [v0.1.0.dev0 预发行版](https://github.com/tsyecommercialdesigner-cloud/zhenzhen-seedancevideo-mcp/releases/tag/v0.1.0.dev0)，发布提交 SHA 为 `d0cbe6de5471d631016706438f1a6df0b08ef04c`。Windows 发布候选全量隔离测试及构建通过；源码包 SHA-256 为 `9c572bc82f94c5045bd928db5a5a820cb667ad67c8aba9a7e385769bbfa41ddd`。完整产物集合和部分模型仍待核实，Job 生命周期限制未修复。

仅 Windows；要求 PowerShell、uv 和可获得的 Python 3.12.14。uv 安装时按锁文件取得依赖；代理／包源问题应在安装阶段处理。MCP 的网络代理配置不会自动配置 uv。Codex Desktop、Claude Desktop和DeepSeek Harness Desktop已有工具发现/共享查询证据，Codex与DSH已有跨Host主视频交付证据；具体范围见[验证记录](docs/verification-add-local-video-generation-service.md)，不代表任意Host兼容保证。

默认发行入口已接通已核实供应商适配器，但EXECUTION_MODE默认local，不执行供应商或下载网络请求。管理员显式配置provider并重启后，新正式提交可自动上传、生成、查询和下载。发行入口及实际Host已有相应验收证据；完整产物集合仍待核实。Job生命周期调查已关闭，但启动器终止可能连带结束后端的兼容性限制未修复，不重开排查。合成适配器只在开发测试目录内，不随发行包提供，也没有用户环境变量后门。请勿用“任务 accepted”判断已向供应商提交。

## 首次安装（版本化源码包）

从仓库 Release `v0.1.0.dev0` 下载 `zhenzhen_seedancevideo_mcp-0.1.0.dev0.tar.gz` 和 `SHA256SUMS.txt`。也可使用来源可信且另附 SHA-256 的同版本本地构建包。

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
Copy-Item -LiteralPath (Join-Path $ProjectDir '.env.example') -Destination (Join-Path $ProjectDir '.env')
```

预期版本 0.1.0.dev0。源码包包含 uv.lock、源码和文档；wheel 可安装，但单独 wheel 不携带完整 uv 项目，成员默认使用上述源码包。安装不依赖维护者 `.venv`、测试文件或用户 HOME 中的 `.env`。

## 配置与初始化

用编辑器填写实际安装目录 `.env` 的 `ZHENZHEN_SEEDANCE_API_KEY`，不填通用 API_KEY。示例密钥为空，未填写会明确失败；如要使用环境变量，删除该字段再配置进程／Windows 当前用户环境变量。文件优先，仅缺失字段回退；空、重复或非法值不回退。不要把密钥写进 Host JSON、命令行、截图或版本库。代理、CA、输出目录等见 [配置说明](docs/configuration.md)。

任务库与默认输出位于 `%LOCALAPPDATA%\ZhenzhenSeedanceVideo`，独立于安装目录；显式输出目录按任务接收时固定。删除／切换安装目录不会自动删除状态或产物。若自行把输出指定到安装目录内，则不享有此物理分离保证，删除前必须另行保存。

## 日常启动与可用性检查

日常启动复用已安装环境，不同步依赖：

```powershell
uv --directory 'D:\MCP\zhenzhen-seedancevideo-mcp' run --no-sync zhenzhen-seedance-video stdio
```

等待协议输入时无普通输出是正常行为，不要向 stdout 写日志。仅版本命令成功不代表业务闭环。客户端先发现 Tools，然后调用 get_service_status 和 get_capabilities；execution_mode=local／generation_execution=not_implemented表示当前未启用；provider模式下为adapter_installed。provider=unverified表示没有通过启动健康探测验证上游。Resources、Prompts 当前为空。

## 本地客户端配置

将下列服务项合并到支持 mcpServers 结构的 Host 配置中，保留所有既有服务，避免重复同名条目；不覆盖整个文件。不提供尚未核验版本的 DSH、Codex 或其他专用格式，实际 Host 接入属于待验收项 13.3。

```json
{
  "mcpServers": {
    "zhenzhen-seedance-video": {
      "command": "uv",
      "args": ["--directory", "D:\\MCP\\zhenzhen-seedancevideo-mcp", "run", "--no-sync", "zhenzhen-seedance-video", "stdio"]
    }
  }
}
```

API Key 用于供应商；本地前后端 RPC 使用受当前用户目录权限保护的随机令牌，两者不同。不要手动复制令牌或编辑发现文件。同用户所有 Host 共享任务，不做项目权限隔离。

## 功能、文件和异常处理

按 [工具手册](docs/agent-tools.md) 查询能力、可选预检、优化授权、提交／找回、等待、恢复与复制。授权询问在提交前；正式提交即授权自动执行。request_key 防止本地重复接收，不代表上游幂等。提交结果不明不能换 key 自动重提。取消工具等待不撤销已接受任务；放弃跟踪可能仍计费且会清理托管输入。

视频以绝对路径和摘要交付，不通过 MCP 返回二进制。相对复制目标须提供 workspace_root，越出工作区需显式绝对路径。默认不覆盖，默认长期保留视频；素材仅清理登记副本。查询与下载预算独立，费用未返回是未知，不是免费。SUCCESS及实扣完整响应已有脱敏证据；其他未明规则见供应商契约台账。

启动报配置冲突时，仅新 Host 被拒绝；统一配置并退出所有 Host 后重启。无法确认旧后端退出、schema 过新或库损坏时停止操作，不强杀生产后端，不删库或标记文件。排障见 [本地运行](docs/local-rpc.md) 和 [状态维护](docs/storage-recovery.md)。

## 升级与回滚

1. 记录当前包版本、包 SHA-256 和可用的发布 SHA。正常退出全部 Host，确认旧后端结束；不能确认时停止维护。
2. 保留私有 `.env` 原文件、权限及旧安装，不用解包覆盖它。下载目标版本 v0.1.0.dev0 的源码包并核对 SHA-256，按上面的首次安装步骤将其安装到独立候选目录；不要启动或填写新密钥探测供应商。
3. 在停机窗口将原 `.env` 安全复制到候选实际安装目录，核对文件摘要和权限；记录原／新 Host 路径。状态与输出不迁移，备份按 [离线维护](docs/storage-recovery.md) 完成。
4. 新包冻结安装、版本与工具发现通过后，修改 Host 的 `--directory` 指向候选目录并验证本地状态。发布前先保持开发验收范围。
5. 回滚程序仅当旧程序支持现有 schema 时进行：退出所有 Host，恢复原 Host 路径及旧安装，保留当前任务库。过新 schema 明确拒绝，不能降级或重建空库。首期没有自动升级／回滚命令。

数据备份不能当作程序回滚。旧备份会遗漏备份后发生的远端请求；禁止恢复 queued 快照后直接启动派发。必须先在离线副本中将所有未结束任务置为需要核对、保留未知占位，结合原库和远端可靠证据处理窗口。未核实上游反查时保持待处理，不自动重派。详见状态维护说明；首期无自动恢复备份工具。

## FAQ 与验证范围

- 为什么安装后不能生成？默认EXECUTION_MODE=local。只有显式provider并重启后新接收任务才授权执行，旧/local任务不会自动获得授权。
- 多个 Host 是否会多开生成额度？同一 Windows 用户共享后端与总额度；实际 Host 行为仍需单独验证。
- 更新 `.env` 是否立即生效？后端统一配置，重启生效；提示词优化授权是可即时修改的独立业务偏好。
- 能否删除任务库修复？不能。未知付费任务仍可能运行，应保留记录并核对。
- 是否经过干净 Windows 验收？验证记录区分当前 Windows 全新解包目录／虚拟环境与全新 OS/VM；没有 OS/VM 证据就不宣称通过。

实际命令与结果见 [实施记录](docs/implementation-progress.md)。不会由成员启动命令自动安装依赖、修改 Host 或发起收费测试。


## 验收记录

干净Windows安装和实际Agent Host接入请使用[验收记录模板](docs/windows-host-acceptance.md)，逐项填写环境版本、安装包摘要、执行结果和未验证项。目前的同版本安装切换隔离演练不代表正式跨版本升级或真实生成验收。

启用与旧任务保护的详细步骤见[执行保护](docs/configuration.md#发行入口执行保护)。实际Host零调用验收必须保持local，不要为检查工具发现切到provider。
