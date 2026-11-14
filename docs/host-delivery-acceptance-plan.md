# 13.3 实际 Host 跨 Host 业务交付：验收准备

2026-11-14；当前 change 68/69，13.3未完成。本页是待执行方案，不是供应商调用授权或通过证据。此前用户指定 Codex Desktop、Claude Desktop、DeepSeek Harness Desktop；选择其中 A、B 两个，均使用同一 Windows 用户与隔离后端。记录实际 Host 名称/版本、构建和测试包 SHA256。

## 已有证据与缺口

| 原完成条件 | 现有证据 | 缺口 |
| --- | --- | --- |
| Host/Job Object | 三款Host local工具发现；DSH具体Job句柄成员关系、正常与强制退出分别有记录 | 不排除未枚举共同外层Job；不把不同实验拼成一次强制关闭Job句柄的证明 |
| A提交、B找回 | local模式实际Host接收并跨Host查同一任务 | 实际Host正式provider提交及远端结果尚未验证 |
| B交付 | MCP SDK真实生成、下载、复制已有证据 | 同一实际Host任务由另一实际Host读取产物并复制尚未验证 |
| 最后Host退出及重启接续 | 实际Host local旧后端退出、原未提交任务重启找回 | 若本轮覆盖已知远端ID及预算，须记录实际状态，不把未提交任务当成远端恢复 |

## 可执行最小方案（正式执行前须有当前收费调用授权）

1. 测试前查资源清单和未决旧进程；用新建专用安装及独立LOCALAPPDATA、输出和交付目录。固定安装包与源码/依赖摘要，不复制其他用户的私有数据库。备份并逐字段合并两个Host的测试服务项；明确现场进程与退出窗口。Codex需要重启时由用户手动操作。
2. 通过受保护的安装目录 `.env` 注入 `ZHENZHEN_SEEDANCE_API_KEY`，不在命令、Host配置、日志或证据中写密钥。显式设置 `ZHENZHEN_SEEDANCE_EXECUTION_MODE=provider` 和专用 `ZHENZHEN_SEEDANCE_OUTPUT_DIR`；核对配置优先级和运行时provider模式，禁止复用local接收任务作为已授权provider任务。
3. A/B分别在实际Host中调用 `get_service_status` / `get_capabilities`，记录一致后端PID、实例和连接状态。仅在确认当前预算及用户明确允许收费后，由A对 `seedance-2.0-mini-t2v` 发起一次独立请求：4秒、480p、`enhance_prompt=false`、音频false，复用已用提示词，提供唯一request_key。4秒枚举的临时声明及供应商变化仍以实际验证/预检为准；预检无生成副作用，不保证接收或费用。
4. A提交一次并记录本地task_id、版本及远端task_id；响应丢失以原request_key只读找回，提交结果不明不重发。B用 `find_task_by_request_key` / `get_task` 读取同一任务，核对本地/远端ID及状态。观察后台自动轮询与下载，不通过反复重新提交制造进度；如失败、超时或未知，按实际状态保留证据，不把它记为通过。
5. 生成成功和主视频ready分开记录。B调用 `list_artifacts`，再调用 `copy_artifact` 到显式工作区相对路径或专用绝对路径，默认不覆盖；核对原件与副本的SHA256、字节数，确认原件仍在。完整产物集合若仍未核实，按partial报告，主视频复制成功不冒充全部产物就绪。
6. 记录实际usage金额/币种，缺失记未返回，不推算价格。将每个收费POST意图（包括结果未知）记入账本；绝不自动重试或换键重提。当前账本历史13次、本窗口5/10、剩余5次是静态记录；正式执行前重新核对，不能仅凭剩余额度推断本次授权。
7. 记录两Host的配置版本、Job检查范围及实际状态；必要时先由A正常退出，B继续查询并复制。最后Host退出后核对旧后端身份与有限退出；重启时保留任务ID、已知远端ID、预算历史和固定输出目录。不要强杀存活后端或隐式迁移库。每项分别记录通过/失败/未执行；确认Job句柄关闭或共同外层Job需要独立证据，不能因正常退出而推断。
8. 归档脱敏最小证据（参数摘要、各Host工具名、状态、实例/版本、费用、原件/副本摘要、异常与限制），不得保存密钥、签名URL和原始日志。验收结束/失败/中断均撤销测试配置项并保留并发变动；确认Host、后端退出并核验链接/重解析点后清理专用安装、依赖、状态和临时副本；必要真实产物按用户确认保留，不清理任何原始输入。资源清单记录所有路径及释放条件并复扫。

## 当前执行状态

未建立新测试安装或修改Host配置；未调用供应商、上传、生成、下载、提交或推送Git。13.3仍未完成；业务主规范未同步、change未归档。当前额度、可用凭据与具体Host重启安排在正式执行前核实。

## 2026-11-14 用户授权执行

用户授权本轮一次最低参数收费测试，Codex提交、DSH找回并复制，优化false。此前账本13次、本窗口5/10、余5；本次独立预留1次，尚未发送提交。隔离provider安装包SHA256 145e9a77b4dc76b0f6c2fc7df1c4a1c554f4460ab78dd54e221131979222fecd，Python3.12.14、离线冻结安装通过；专用受保护安装.env与隔离状态，Codex/DSH各合并测试入口，均未写入密钥。等待手动重启Codex并启动DSH；调用前需核对同一后端、provider模式、模型预检及请求唯一性。

DSH用户回传：实际健康PID23904、provider、host_count1、额度0占用、存储正常、上游未探测；能力26+1。专用发现文件实例已关联，尚未提交，等待Codex重启后核对相同后端。

Codex实际Host提交一次：本地task_id 012efe97d75d429594f88cf41646d9d6，远端ID已持久化，预检4秒480p、优化false；随后状态running、进度50、费用未返回。账本记录第14次收费提交，本窗口6/10、剩余4，本轮授权1/1已使用；不重提。DSH找回及复制待验。

实际结果进展：DSH按请求标识找回Codex任务及同一远端ID；生成完成，主视频artifact_id 7239096f29aa44a78aad1458a987d340，1641276字节，SHA256 28ca7bc7bb0c5f25eb011836280d2600f506bf14716c7d4df13c50134abb64c1，费用0.8028 ¥；artifact_set_status=unverified、delivery=partial。已请求DSH复制至仓库deliveries/host-acceptance-20261114.mp4，结果待回传。原件位于隔离输出目录，默认保留，不能随临时安装一并删除。

13.3实际Host业务结果：Codex/Desktop提交task 012efe97d75d429594f88cf41646d9d6；DSH实际find_task_by_request_key找回相同本地及远端ID，调用list_artifacts及copy_artifact成功，overwrite=false。宿主独立核验原件与副本均1641276字节、SHA256 28ca7bc7bb0c5f25eb011836280d2600f506bf14716c7d4df13c50134abb64c1；原件保留。SQLite按阶段仅1次submit、1个任务、0上传、1个artifact；data.usage实际0.8028 ¥。产物集合unverified、delivery partial，不将主视频复制冒充完整集合。最终Host退出和清理待完成。

DSH正常退出后，Codex仍读到后端PID23904、host_count2、同一任务远端succeeded、实际费用0.8028¥、主视频ready及集合unverified。已启动无租约只读观察器（最长1小时），等待用户退出最后Codex并重启，以验证本任务远端ID和状态接续；暂不撤销连接所需配置。

重启接续：观察器记录原PID23904于06:37:51 UTC确认退出，重启后依次观察PID13936、40144、31928，前两次实例变化原因未确定；Codex连接PID31928后按request_key找回同一任务、远端ID、version9、succeeded、费用0.8028¥及partial状态。重启后SQLite仍只有一次submit及一个任务，原件与DSH副本各1641276字节/SHA256 28ca7bc7bb0c5f25eb011836280d2600f506bf14716c7d4df13c50134abb64c1。观察器不占租约。13.3记录实际Host/Job范围及业务闭环，完整产物集合仍unverified，实例变化仍需排查；不声称所有Job或产物均已验证。

清理进展：Codex与DSH测试服务项已按结构移除，保留其余配置；观察器已发停止信号。当前Codex仍持有测试安装，需用户再次手动重启后确认后端退出再清除安装、私有配置备份及观察器。 paid原视频、交付副本及任务状态继续保留，不与临时安装一并删除。

最终收尾核验：用户再重启Codex后，测试后端PID31928按PID及创建时间确认退出，测试进程/观察器均已停止，Codex/DSH测试配置不存在；任务库SQLite integrity_check=ok、唯一任务succeeded/version9、submit intent 1。原件与副本均1641276字节、SHA256 28ca7bc7bb0c5f25eb011836280d2600f506bf14716c7d4df13c50134abb64c1。保留原视频、复制交付和整个local-app-data任务状态；仅清理安装、源码包、带凭据的配置及Host配置备份/观察器。

最终清理完成：经用户再次重启，后端31928按PID及创建时间确认退出；观察器及测试进程不存活，Codex/DSH测试服务不存在。核验专用安装内无重解析点后移除安装（含私有.env）、源码包、Host配置备份/片段及观察器；仅保留专用根内outputs、local-app-data及.gitignore，另保留deliveries副本。原件/副本摘要及SQLite状态在清理前复核一致，状态和视频默认不清理。
