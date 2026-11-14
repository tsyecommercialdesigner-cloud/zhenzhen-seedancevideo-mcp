# 13.3 local 实际 Host 验收交接

2026-11-14，0.1.0.dev0，当前66/68。用户已授权配置备份和合并，随后指定 Codex Desktop、Claude Desktop、DeepSeek Harness Desktop；Cursor 不参与。

## 已应用配置

三者均新增 seedance-local-acceptance，命令为本任务独立安装的 .venv/Scripts/python.exe，参数 -m zhenzhen_seedance_video stdio。子进程 LOCALAPPDATA 共用专用 local-app-data，不改日常任务库。安装目录 .env 强制 local、占位密钥，禁止供应商调用；心跳1秒、租约5秒、宽限3秒、收尾2秒。

- Codex：用户 .codex/config.toml 的 mcp_servers 表。
- Claude：实际使用 C:/Users/Administrator/AppData/Local/Claude-3p/claude_desktop_config.json 的 mcpServers 表。
- DSH：用户 .dsh/profiles/desktop/cordis.patch.yml 新增独立 insert，插件 @deepseek-ai/dsh-mcp-client，transport=stdio。
- Cursor：此前临时新增项已撤销，配置逐字节恢复原文件；没有启动 Cursor。

受保护原件、准确绝对路径及摘要位于 .cache/host-local-acceptance-20261114/manifest.json 和 config-backups；备份不提交，不能直接整文件覆盖并发修改。冻结包 SHA256：7c26dd46853dfb4ea8acbcba96ee942311bcfb315942e3774e1f823418a28631。已复用既有安装，没有另建安装或环境。

## 当前证据与限制

配置合并不等于 Host 验收。当前 Codex 工具集中未发现 seedance 服务；DSH UI 自动化截图与可访问文字不一致，已停止点击，不记工具发现通过。发现目录中的 PID/实例文件只作为启动痕迹，未证明三个实际 Host 成功连接或共享租约。只读生命周期观察器尚未启动。

用户需保存工作并手动完整退出、重新打开三款 Host，回到本聊天继续；Agent 不关闭承载当前会话的 Codex。重启后先确认每款 Host 的工具发现及 get_service_status/get_capabilities，再比较后端实例与租约；随后验证单个 Host 退出不影响其他 Host、最后一个 Host 退出后后端有限停止、重启接续。全程 local，无供应商调用；本阶段不替代实际业务交付或干净 OS 验收。

## 清理交接

资源清单见 test-resource-register.json。当前独立安装、依赖环境、配置备份、local 状态和输出目录保留至 Host 验收结束，使用者为用户及接手 Agent。结束或中断时先归档最小脱敏结论，逐字段撤销三款 Host 的测试配置（保留并发修改），断开测试连接，再核对路径和链接后清理安装、运行时/依赖、下载包及本任务缓存，复扫登记。其他历史缓存仅已盘点、尚未逐项判定归属与付费原件，不能宣称全部清理。

13.1/13.3仍未完成。无供应商调用、无 Git 提交或推送。工程主规范已修订；业务主规范未同步，change未归档。

## 重启后第一轮实测

2026-11-14 13:24（Asia/Shanghai）：Codex实际发现23个工具；get_service_status返回PID19900、3个租约、local、dispatch_allowed=false、存储正常。get_capabilities空参数返回26个Seedance模型及1个超分；首次仅传model_id得到API_ID_REQUIRED，随后按无参能力入口成功，不隐去首次参数错误。

Codex接收唯一request_key=host-local-acceptance-20261114，task_id=ddf1295ce6ed4b1fa053683b7801641a，version=1、queued/not_submitted、remote_id=null，优化single_explicit_false。随后按请求标识找回一致。数据库只读计数见host-local-codex-evidence.json，供应商提交/上传/远端观察均为零。

3个租约不等于三款Host都已验收：进程盘点观察到多个Codex接入及DSH接入，仍需Claude/DSH分别返回实际工具结果。DSH输入自动化未可靠取得编辑焦点，未发送验收请求；用户已收到可复制的三项只读请求。独立无租约观察器已隐藏启动，最长15分钟，到期自行结束；本轮尚未完成全部Host退出及接续，因此暂不撤销仍在使用的配置或删除安装。验收结果待用户回传后继续。

## DSH 与 Claude 用户回传

用户回传 DSH 的三项实际工具响应：PID 19900、local、3 租约；能力 26+1；按请求标识找回 Codex 的同一 task_id、版本 1、queued/not_submitted、优化关闭。因此 Codex 与 DSH 的共享后端及跨 Host 本地查询通过；未验证退出恢复。local 下 generation_execution=not_implemented 是本轮防派发模式的状态，不否定已有 provider 模式真实闭环证据。

Claude 用户回传当前会话未挂载该工具。只读核对打包应用配置文件中存在 seedance-local-acceptance，Claude 进程运行；该应用日志中未发现服务名称。配置存在不证明会话加载，具体生效配置、会话模式或加载失败原因尚未确认，不能认定通过。未修改其他配置或调用供应商；保留隔离安装及配置用于继续排查。

2026-11-14：用户指出 Claude 实际使用 Claude-3p 配置。该文件原有五个服务，已备份并合并 local 验收条目；先前误修改的打包应用配置已逐字节恢复。需要重启 Claude 并重新验证工具；此前 Claude 失败保留为历史证据。

Claude-3p 重启后观察：Codex 健康工具返回同一后端 PID 19900、local、4 租约；进程树出现 Claude 启动的验收前端。此为连接迹象，不能替代 Claude 会话实际工具调用；等待用户返回查询及正常退出 DSH 后验证其余连接。

Claude 用户回传实际三项查询成功：PID 19900、local、5租约、26+1能力、同一任务 ddf1295ce6ed4b1fa053683b7801641a 版本1且未提交。三款Host的工具发现及跨Host查询通过；租约数不等于Host数。Claude此前未发现的说法经其更正。local任务没有provider执行授权，不据此承诺重试可派发。DSH进程仍运行，退出恢复尚未验收。

DSH 正常退出后实测：未发现 DeepSeek Harness.exe 进程；Codex get_service_status 返回 host_count=4（退出前5）、phase=running、PID 19900，discovery instance_id 仍为 3e0d55e6-aa61-468b-b0ea-f98dc378ea5b；按原 request_key 查询同一任务 ddf1295ce6ed4b1fa053683b7801641a，version 1、queued/not_submitted、remote_id=null。单 Host 退出后共享后端与本地查询继续可用；最后 Host 退出与重启恢复尚未验证。

最后Host退出验证已准备只读观察器：以PID 19900及创建时间核验旧进程，另记录发现文件中新实例；不连接RPC、不占租约，最长一小时。等待用户先退出Claude、再退出Codex，等待至少30秒后重启Codex并回到本会话；结果及清理待接续。

最终退出实验：观察器确认旧 PID 19900 于 13:32:42 退出；13:33:21 记录新 PID 14860，13:33:30 又记录 PID 23432。重启后 Codex get_service_status 和 find_task_by_request_key 均返回工具执行错误，任务恢复未通过；两次新实例的原因待排查。只读任务库仍有原任务，attempts/uploads/remote_observations 均为零；不能将库内存在当作 Host 恢复通过。观察器及隔离状态暂留以便诊断，最多运行至自身截止。

后续排查：重启后 Codex get_service_status 再次返回 Error executing tool；独立 MCP SDK stdio 客户端使用同一冻结安装与状态根，初始化成功，PID 32020、local，并找到原任务版本1/not_submitted。该测试证明新前端可恢复，不能证明 Codex Host 恢复，也不能判定实例变化根因。首次探针因解释器路径拼写错误未启动，第二次因 SDK timeout 类型错误初始化失败；修正为数值秒后退出0。未调用供应商。

后续隔离探针：SDK stdio 客户端以相同 local 安装与状态根连接，间隔15秒两次健康查询均成功且 PID 5388 不变，进程退出码0。此结果不证明 Codex Host 连接已修复；原始 Codex 工具错误仍缺少可归因诊断。检查前端实现可见连接在 lifespan 建立、丢失后无重连，但尚未证明这是本次根因，未擅自更改行为。

追加排查：Codex 启动的两个 stdio 启动器及其 Python 子进程仍存活；检查 Codex 本地日志数据库未找到 BACKEND_CONNECTION_LOST、mcp error 或 Broken pipe 记录。观察器记录的 PID 32020 与 5388 分别对应随后独立探针建立的实例，不能归咎于 Codex；14860 与23432 的退出原因仍未知。未定位根因、未修改实现。

2026-11-14：针对已知前端断连缺口增加下一调用前互斥重新接入，发送后失败不自动重放；原因是否为Codex本次错误仍待实际验证。两项定向测试和6项runtime测试通过。专用安装中仅替换frontend.py，原件已备份、摘要在manifest；现存Codex进程仍使用旧代码，须手动重启加载。

修复版实际Host重启验证：Codex get_service_status 返回 PID 13580、local、2租约，find_task_by_request_key 找回原ID、version1、queued/not_submitted；随后显式取消本地测试任务，version2、远端未提交。此证明重启后接续，本次调用没有人为触发已建立连接再次断开，因此不证明重连分支在实际Host执行，也不能归因原故障。三Host测试配置已按条目移除，保留其他配置；Codex测试进程仍存活，须用户完整重启后清理安装。

最终清理前核验：Codex重启后测试后端PID 13580按PID及创建时间确认退出；三Host测试配置均已移除，任务测试进程和观察器无存活，专用目录递归扫描无重解析点。旧后端19900于13:32:42退出；重启查询PID13580找回原任务后已取消。专用状态仅用于local验收，无供应商请求。

清理复扫：本轮专用 host-local-acceptance-20261114 目录（含独立安装、依赖、状态、观察器及配置备份）已移除，路径不存在；三Host测试配置不存在。其他历史缓存仍按资源清单待分类，不在本次清理范围。

实际Host断连重接新一轮：复扫并复用本机离线uv缓存，创建独立 local 安装，sdist SHA256 1c46ab59db71194478669c604542a4b373db04f54794a455f275d5babd3a11af；uv sync --frozen --no-dev --offline退出0，Python 3.12.14。DSH配置增加seedance-reconnect临时服务，其余项语义不变，备份位于ACL保护测试目录。等待DSH实际接入；尚未进行断连验证。

14.2 实际DSH断连接续：用户在同一会话实际查询local PID 20476；在核对测试目录discovery实例及PID创建时间后，对该专用测试后端注入终止并等待进程退出；用户未重启DSH，后续首次状态查询成功返回local PID 39572，host_count=1、dispatch_allowed=false。新discovery实例9a06f388-6deb-4744-97cd-f4b1dcf19ef4，旧PID不存活。故障注入仅用于隔离验收，不改变正常接管不强杀规则。此轮没有测试提交任务，也不证明此前Codex错误根因。DSH配置测试项已撤销，等待进程退出后清理。

用户正常退出DSH后，按进程ID及创建时间确认测试后端39572退出，DSH测试配置不存在；专用目录扫描无重解析点，准备清理。

清理完成：DSH测试配置项已移除、后端退出；专用host-reconnect-20261114安装、运行时、状态、下载包及配置备份已删除，复扫路径及测试进程不存在。其他历史缓存仍按清单待分类。
