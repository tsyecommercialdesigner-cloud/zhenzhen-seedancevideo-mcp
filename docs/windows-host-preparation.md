> 2026-11-14更新：实际 Host 改为 Codex Desktop、Claude Desktop、DeepSeek Harness Desktop；Cursor 排除且已恢复配置。已授权合并测试配置，等待用户手动重启后验收。当前66/68；历史准备记录不作为通过证据。见 [交接记录](host-local-review.md)。

# 13.1／13.3 最小验收准备（2026-11-14）

本轮仅只读环境盘点、包与隔离测试准备；未启动VM或Sandbox，未安装Host、修改Host配置、重启日常Host或调用供应商。65/67保持不变，两项仍待验收。原始完成判断不缩减。

## 本机已观察事实

| 对象 | 只读结果 | 能证明什么／不能证明什么 |
| --- | --- | --- |
| Windows | Windows 11专业工作站版，10.0.26300，Build 26300；JGINYUE/B760M GAMING；HypervisorPresent=true | 当前开发机，不是干净OS |
| Hyper-V | Get-VM命令存在；vmms、vmcompute运行，存在vmwp进程 | Get-VM权限拒绝，不能列出或认定某个来宾可用；CIM只返回宿主项，不据此断言无VM |
| Sandbox | C:\Windows\system32\WindowsSandbox.exe存在 | Get-WindowsOptionalFeature -Online要求提升；未启动，启用状态及可启动性未证实 |
| Codex Desktop | Appx 26.1111.2228.0；相关进程运行 | 可作为候选Host；未接入本服务、未验证Job Object |
| Claude Desktop | Appx 5.11492.5.0；进程运行 | 常用Roaming/Claude/claude_desktop_config.json不存在；不等于不支持MCP，实际配置位置未核实 |
| DeepSeek Harness | 卸载注册表0.2.1-rc.5；进程运行 | 候选Host；未读取凭据，未核实当前profile与配置合并方法 |
| Cursor | 注册表3.22.12；cursor.cmd存在 | .cursor/mcp.json可解析，当前无名称含seedance的服务项；未验证实际MCP调用 |
| VS Code | 注册表1.146.0；code.cmd存在 | User/mcp.json可解析、无名称含seedance的条目；扩展/Agent能力未核实 |
| 本地工具 | uv 0.12.9；Codex/Claude CLI存在 | CLI存在不代表桌面Host验收，未启动Agent会话 |

Codex的用户config.toml可解析、含9个MCP条目，没有名称含seedance的条目；Cursor及VS Code各2个。本次只输出计数与匹配布尔值，不输出服务凭据、命令参数或完整配置。不存在名称匹配不排除服务使用其他名称，后续合并前还要核对目标command。未扫描整个磁盘找VM镜像，未探测远端Windows。

## 最小环境选择与授权

首选一台可回滚的干净Windows VM，创建专用测试用户；在该用户下安装两个实际Host，既能避免日常任务库和DPAPI绑定混用，也能复用同一环境完成两项验收。现有开发机的新解包目录只能补充证据，不能替代干净OS。Sandbox可用于短期安装验证，但需先证实可启动、保存外部证据并允许所需安装；若Host登录或持久重启不便，不用它勉强替代VM。

用户最少需要指定：

1. **环境**：一台干净Windows VM/独立测试机的可访问方式、Windows版本和干净快照依据；或允许在本机检查/使用指定Hyper-V来宾或Sandbox。若需新建VM，还需镜像来源、许可、磁盘/内存额度和安装权限。当前权限拒绝来自Windows，不是工具自动审批拒绝；可由管理员提供只读Get-VM和可选功能结果，不必提供管理员密码。
2. **Host组合与操作窗口**：指定两个Host及允许使用的测试profile。优先复用熟悉的Codex+Cursor；选择Claude/DSH也可，但应先核实具体版本配置位置。允许在测试用户中安装/启动、合并一个服务项、备份配置、正常退出与重启，并在结束后移除本轮服务项。日常Codex正承载本次会话，未经指定不要退出它。Host自身模型账号由用户登录，若需模型调用，费用权限与供应商视频额度分开确认。
3. **网络与数据**：允许uv取得锁定依赖及Python 3.12.14（或提供完整离线依赖）；本轮供应商访问保持禁止。阶段一用非真实验收占位凭据，不携带现有.env、签名URL或私有任务库进入VM。不需要用户补交已有供应商响应。

这些是后续环境操作的范围选择；当前只读盘点及本仓库准备已执行，不等待许可。

## 阶段一：零供应商调用的安装与Host行为

交付输入：当前开发源码包、其SHA-256、uv.lock、MANUAL.md以及本页和windows-host-acceptance.md。无正式Release/CI声明；源码有未提交修改，包摘要才是本次安装身份。不要复制开发机.venv。

1. 保存干净快照/系统构建号；在测试用户下将源码包解到全新绝对目录，按MANUAL执行uv sync --frozen --no-dev。记录uv/Python/包版本与导入路径。
2. 实际安装目录.env使用专用非真实占位API_KEY，设置外部OUTPUT_DIR，优化不授权；不要继承日常密钥或改变Windows用户环境。当前CLI在EXECUTION_MODE=local时不安装适配器，验收.env须显式保持local，检查健康应如实显示生成不可执行；阶段一只用本地操作。可在专用VM禁用供应商外网访问，但依赖安装须先完成。
3. 两个Host指向同一安装。使用已安装venv的python.exe及`-m zhenzhen_seedance_video stdio`，不在工具启动时同步依赖。记录Host实际读取的配置位置、格式和版本；按其格式合并，不整文件覆盖。
4. A/B均发现工具，调用get_service_status/get_capabilities；保存同一后端PID、创建时间/实例标识和两个租约。A用唯一request_key接收一个4秒480p、enhance_prompt=false的本地任务；确认无供应商adapter且没有提交attempt，再由B按request_key找回。accepted只能记本地接收，不记生成成功。
5. A正常退出，B继续查询且后端身份保持。关闭最后Host，记录最后连接离开、宽限及有限收尾期限、进程退出时间。强制结束Host测试须在专用profile且无其他工作时另行确认，不能强杀共享后端。由B重新接入，核对原任务标识、参数和预算；提交前取消该测试任务，不启用自动生成。
6. 配置冲突用第二个同版本安装目录的.env暂时设置不同OUTPUT_DIR；原Host仍在线时新接入必须明确拒绝，原服务不受影响。不要用低优先级Host环境覆盖安装.env来制造冲突。
7. 全部退出后按MANUAL切换同版本安装再回切，比较.env摘要、任务标识、外部产物/保留标记摘要；仅在离线副本演练备份窗口屏障及过新schema拒绝。恢复配置并核对专用进程均退出。该演练不声称跨版本迁移支持。

每一步记录工具名、必要输入、脱敏结果、时间与结论。Job Object记录实际Host父子进程和退出表现；仅观察正常退出不能宣称所有强制结束策略兼容。健康数据不能独立证明Job限制。

## 阶段二：13.3业务交付仍存在的门槛

本轮后续实施已接通默认发行构造：EXECUTION_MODE默认local，显式provider才安装ProductionAdapter、ProductionUploads及Scheduler；local阻断网络，provider接收事务固定授权，旧/local任务不会自动获权。入口接线通过隔离验证，实际Host和新入口真实闭环仍未验证。此前专用启动器真实证据单独保留。

本次准备及后续零调用Host验收必须使用local，不切provider，不带入日常任务库；不会新增环境变量合成适配器后门。

13.3原判断包含A提交、B找回及复制交付。可以零收费地补验已有本地产物在实际Host中的查询/复制，但不能将其改称A新提交到B交付的完整流程；已有私有库也不跨Windows用户复制（DPAPI绑定）。完整流程需后续明确允许的供应商操作及生产接线。当前暂停新增收费，历史余5次不在本轮使用。阶段一成功只完成13.3部分证据，两个任务均须按原判断核对再关闭。

## 本轮验证与待填结果

环境命令只读执行；Get-WindowsOptionalFeature提升拒绝、Get-VM权限拒绝均如实记为未核实。未运行VM/Sandbox或任何实际Host工具调用。安装/多客户端隔离复验结果见implementation-progress.md，不能填作干净OS或品牌Host通过。主规范业务同步与归档均未执行，无Git提交推送。
