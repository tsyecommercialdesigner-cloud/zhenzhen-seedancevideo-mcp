> 2026-11-14更新：当前67/69；实际Host local部分已有证据，干净Windows和实际Host业务交付仍未完成。逐项见下表及[交接记录](host-local-review.md)。

# Windows安装与实际Host验收记录（待执行）

对应13.1／13.3。本页记录已完成的部分验证和未完成步骤；不以部分结果替代整项验收。已核实适配器有专用启动器真实闭环证据；默认发行入口现已接线，但默认local阻断网络，显式provider才启用新任务执行。当前准备阶段不允许供应商调用或修改日常任务库。现有本机隔离安装和stdio测试不能填入“干净OS／实际Host通过”。

本机只读盘点、最小阶段方案及所需授权见[本轮准备](windows-host-preparation.md)。环境可用性与实际验收尚未确认。

## 环境记录

| 字段 | 待填值 |
| --- | --- |
| 执行时间／执行人 | 未执行 |
| Windows版本／构建／架构；新OS或VM依据 | 未记录 |
| uv版本；Python实际版本（须3.12.14） | 未记录 |
| 安装包名称／SHA-256；源码版本及未提交变更 | 未记录 |
| 原安装／候选安装绝对路径 | 未记录 |
| 同一Windows用户标识（脱敏） | 未记录 |
| Host A名称／版本／启动方式 | 未记录 |
| Host B名称／版本／启动方式 | 未记录 |
| Host配置所在位置、合并项、恢复办法 | 未记录；勿包含API Key或RPC令牌 |

## 13.1 干净环境步骤

按[成员手册](../MANUAL.md)执行，不用开发机器现有.venv替代新安装。

1. 核对包摘要，解包到不存在的目录；执行`uv --directory <安装目录> sync --frozen --no-dev`。记录退出码和依赖取得方式；离线缓存不足就是未完成，不能忽略失败。
2. 使用安装目录.env，检查版本入口；记录实际导入路径来自安装目录。不要把.env内容或密钥上传到验收记录。
3. 用明确记录版本的Host启动stdio，发现Tools并调用get_service_status、get_capabilities。记录provider未核实等真实状态；accepted不代表已生成。
4. 在专用验收环境中退出全部Host，确认后端退出；按手册切换安装目录，再回切原目录。保留.env摘要、任务ID与外部产物摘要作为前后比较依据。跨版本仅在schema兼容已核实后执行。
5. 状态／输出保持在安装目录之外。只删除专用测试安装副本，记录外部数据仍在；不可直接删除日常使用的安装或状态目录。
6. 备份窗口屏障和过新schema拒绝应在离线副本／隔离环境演练，参见[状态维护](storage-recovery.md)，不得为测试修改真实库schema。

## 13.3 实际Host逐步判定

| 步骤 | 完成判断／证据 | 当前结论 |
| --- | --- | --- |
| A/B接入 | 两个实际Host均发现工具；健康显示共享后端PID与两个租约，记录名称／版本 | 通过 local 部分：Codex、Claude、DSH 均查得 PID 19900；详细证据见交接记录 |
| 配置冲突 | 专用测试配置冲突仅拒绝新Host，不影响已接入Host；保存错误码 | 未执行 |
| Job Object | 记录Host的实际启动、退出与后端行为；不能仅凭控制台启动推定支持 | 未执行 |
| A退出、B继续 | B只读查询仍可用；后端身份保持；无无意的新后端 | local 部分通过：DSH退出后租约5→4，Codex查询原任务，后端身份不变 |
| 最后Host退出 | 宽限与有限收尾后进程退出；记录配置时间和观察时间，不强杀 | 部分通过：观察到旧PID 19900退出；尚不证明所有Job强制退出行为 |
| 重启接续 | 原任务标识／已确认远端ID／预算不重置；原输出目录固定 | local部分通过：Codex重启查询相同任务版本1及未提交状态；无远端ID或下载预算可验证 |
| A提交、B找回及交付 | 需生产适配、契约及真实调用授权；保留视频摘要和复制结果 | 阻塞：当前不允许真实调用 |

前六步能独立准备或部分验收，不能据此关闭要求业务交付的整个13.3。合成适配器只在开发测试中，不进入发行包；不要为实际Host验收新增环境变量后门。

## 结论与脱敏

逐步填写通过／失败／未执行、命令或工具名、退出码、关键输出及证据位置。健康／任务响应仅保留必要标识和状态；隐藏API密钥、RPC令牌、签名URL查询串及用户私有输入。使用路径／包摘要和版本关联证据，不能只写“正常”。业务视频播放结果单列人工结论。只有原任务完成判断全部满足后才勾选对应tasks。

## 2026-11-14 Windows Sandbox 干净安装（用户回传）

用户提供刚启动且未操作的Sandbox；Get-ComputerInfo返回Windows 10 Enterprise、WindowsVersion 2009、OsBuildNumber 26100（版本名称按命令原样记录）。uv 0.12.9从宿主复制；sdist SHA256 f9ec4432775f152d65055ebc8b969143953ae5d4243ba19c3e2ac5dfb27e3c7d 与缓存zip SHA256 e47d590fc0714fc70d99eb39b76d82ca8174f682d55ea2ab5d238879df213ad1 在Sandbox核对一致。首次在线sync下载PyPI超时；使用筛选缓存及绝对缓存路径执行uv sync --frozen --no-dev --offline，用户输出Installed 31 packages。Python 3.12.14，模块导入位置为Sandbox独立安装src，版本入口0.1.0.dev0。

安装目录.env设local及占位密钥；Sandbox用户运行只读MCP SDK stdio探针，发现23工具、required_tools_present=True，健康PID5260、host_count1、execution_mode=local、dispatch_allowed=false，能力26+1。该验证是干净环境stdio客户端证据，不是实际Agent Host证据，也不覆盖跨版本升级回滚或跨Host产物交付；13.1完成判断见后续记录，13.3仍未完成。

Sandbox探针退出后，用户执行 Get-Process -Id 5260 -ErrorAction SilentlyContinue，无输出；仅证明该PID当前不存在，未单独核对创建时间。

Sandbox外部存储保留：用户确认测试安装路径本身及内部无重解析点后删除，Test-Path=False；删除前后输出标记SHA256 3402a1781f98076c2195a28a91df1ff8dc813282dd467a801155169d0d2eca37、SQLite主文件SHA256 0ab48b25cba617ed3a4acca0161813b314c095ef63544bb4af60769eb1012977一致。由独立uv Python 3.12.14只读打开（含SQLite WAL语义），integrity_check=ok、tasks=0，与删除前一致。该输出为标记文件，非视频内容；本项不宣称业务产物或跨版本回滚通过。
宿主隔离验证：test_future_schema_rejected_without_migration、test_offline_consistent_backup_preserves_unknown_task、test_backup_window_is_quarantined_before_any_restore_dispatch，3 passed in 1.12s。结合本次干净Sandbox安装及stdio工具发现满足13.1文字完成判断；13.3实际Host业务交付和Job Object仍未完成。

Sandbox清理：用户确认关闭；宿主复扫未发现WindowsSandboxServer、WindowsSandboxRemoteSession或vmmemWindowsSandbox，专用宿主准备目录不存在。CodexSandboxService是另一个正在使用的系统服务，不属本次清理对象。微软文档说明关闭Sandbox丢弃来宾文件和状态；具体磁盘回收字节数本次未测量。

13.3待办核对：① 实际Host所在Job Object的具体归属及Host退出时后端行为，不能用普通进程观察替代；② A正式提交、B找回并完成产物复制交付的实际Host端到端证据，需真实生成授权或经批准的可验证等效方案；③ 若需覆盖已知远端ID/预算的停机恢复，须有对应实际Host任务证据。现有local三Host共享查询、正常退出及DSH故障重连分别已记录；当前禁止供应商请求，业务闭环不可冒充完成。配置冲突实际Host测试为待补充观察，非将隔离测试等同实测。

Job Object只读准备：当前Codex Desktop 26.1111.2228.0主进程43728及codex进程29740、6060通过IsProcessInJob(handle,None)均返回True；只能说明各自至少属于某Job，不能认定同一Job。新DSH local专用安装SHA256 d658c6817676cf10cf9e7c838f60cf2063cf9d553de6a20ae88d17a16952467e，离线uv冻结安装成功，临时配置已备份合并；等待DSH接入及Host/前端/后端关联核验。

## 2026-11-14 实际DSH Job Object部分观察

使用DSH Desktop 0.2.1-rc.5及独立冻结源码包SHA256 d658c6817676cf10cf9e7c838f60cf2063cf9d553de6a20ae88d17a16952467e；Python3.12.14、local隔离状态。IsProcessInJob(handle,None)对DSH主进程36780及前端实际解释器12888返回True，对后端10116也返回True；该API仅表示属于至少一个Job，不能识别是否同一Job或其关闭策略。

实际DSH和独立SDK客户端同时连接时，后端PID10116、实例d7aa7965-de4a-4a75-8de6-408cd436c824、host_count=2。用户正常退出DSH后，SDK客户端连续查询相同PID、running、local，host_count=1；SDK断开后通过PID及创建时间确认后端退出。此结果证明本次正常退出未中断另一个客户端，但SDK不是第二个实际Host、正常退出不证明强制结束或Job句柄关闭行为，也不证明后端不属于DSH的Job。无供应商调用。DSH临时配置按条目撤销，保留其他配置。

强制退出Job验证准备：此前专用目录复扫无残留，DSH未运行；建立独立local安装，Python3.12.14、离线冻结安装成功，包SHA256 04c0bf49df77d4452f94b4ce07642df0766cb804995059723efe46f295341195；DSH新增seedance-job-force项并在受保护目录备份。等待用户启动专用Host并核验进程身份。尚未强制退出或证明同Job。

## 2026-11-14 实际DSH强制退出部分验收

冻结sdist SHA256 04c0bf49df77d4452f94b4ce07642df0766cb804995059723efe46f295341195；Python3.12.14、local及独立状态。实际DSH主进程40760、其stdio启动器5592及后端42208，IsProcessInJob(handle,None)均返回True；发现文件实例e57a6f00-970c-4f5c-a1c7-440c43f5c233。该接口只说明各进程处于某Job，未确定为同一对象。尝试枚举Job句柄的探针因创建无名Job时pywin32参数TypeError失败，未取得同一Job证据，不算通过。

隔离SDK客户端与DSH共同接入后，状态PID42208、host_count2。用户确认无其他工作后在任务管理器强制结束DSH；之后DSH/前端进程不可见，SDK以2秒间隔连续查询同一PID42208、running、local、host_count1。SDK正常断开后以PID和创建时间确认后端退出。结果证明该次强制结束回收连接且未中断另一个客户端；未证明实际Host的Job句柄关闭或后端与该Job的成员关系，也未使用第二个实际Host。未调用供应商。

Job归属续验准备：修复前次无名Job创建参数，探针以已知命名Job验证成员真、无关进程假并成功获得Job句柄类型；隔离local安装冻结包SHA256 0d3d75ea15c4c0c0cc04745c575b6f504e523b31013fae7e3ea1ebc0bc314707，DSH配置已合并并备份，等待实际Host接入。

## 2026-11-14 实际DSH具体Job句柄归属

冻结sdist SHA256 0d3d75ea15c4c0c0cc04745c575b6f504e523b31013fae7e3ea1ebc0bc314707；离线安装Python3.12.14，local隔离。探针以命名Job及专用子进程自测：已知成员返回True、无关进程返回False；从Windows扩展句柄表识别Job类型，限本次相关PID复制可访问的Job句柄并调用IsProcessInJob，未保存内核地址或其他进程内容。

实际DSH主进程24416，DSH子进程40416，stdio启动器9348，实际前端解释器34456，后端6608、实例002d360a-6d4b-45b8-b18d-f021c35158ac。对主进程持有、主进程自身为成员的一个具体Job：主进程/DSH子进程/stdio启动器为True，前端解释器/后端均为False，重复检查一致。DSH子进程持有另一个可访问Job句柄，成员向量为False/True/True/False/False（按上述五个PID顺序）；stdio启动器持有的一个Job句柄向量为False/False/False/True/False。这些是实际具体Job成员关系，不能排除不可访问或未枚举的共同外层Job，也不证明所有Job的关闭策略。

用户正常退出DSH，后端6608按PID及创建时间确认退出；相关进程不再发现，临时DSH配置仅测试项已撤销。本次无供应商调用；此前强制退出与本次句柄检查是分别进行的实验，不宣称同一次句柄关闭因果。13.3实际Host跨Host业务交付仍未完成。

13.3 实际Host跨Host交付的待执行步骤、证据及收费前提见 [最小验收方案](host-delivery-acceptance-plan.md)；该方案尚未执行，不能据此勾选13.3。

13.3业务交付完成证据：Codex提交一次4秒480p、优化关闭；DSH找回同一任务、列出并复制ready主视频，原副本摘要一致。实扣0.8028¥。DSH退出Codex继续查询；最后Host退出旧后端确认停止，Codex重启后找回同一远端ID、版本、费用和partial状态，记录多个新实例变化待排查。详见host-delivery-acceptance-plan.md及Job实验；完整产物集合unverified，不宣称完整集合或所有Job句柄已验证。
