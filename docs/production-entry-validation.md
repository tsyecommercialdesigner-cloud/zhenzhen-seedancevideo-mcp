# 默认发行入口与执行保护

2026-11-14；对应14.1，为13.3准备。本轮无真实供应商请求、收费、Host配置修改或Git提交推送。

## 配置与行为

- `ZHENZHEN_SEEDANCE_EXECUTION_MODE=local`为默认；严格只接受local/provider。安装目录.env优先，缺失字段才回退，重启生效。显式模式冲突只拒绝新Host。
- local保留原本地接收、查询、清理和复制；无供应商调度，网络request/stream被LocalNetwork阻断。健康包含execution_mode，adapter_installed不是上游可用性探测结果。
- provider由runtime默认构造ProductionAdapter、ProductionUploads与Scheduler，三者共用后端NetworkPolicy和数据库；不是用户指定模块路径，也不是环境变量合成后门。
- accepted事件与任务同事务保存provider_execution_authorized。provider新正式提交获得执行授权，提示词优化仍独立控制；local和旧记录没有授权，重复request_key不会改变授权。
- provider启动在RPC公布前将未授权active任务转待处理，保留远端ID、占位、预算和素材；每次上传准备与适配器prepare/submit/query/artifacts再次核对。旧任务不自动迁移授权；不得靠更换key重新发出未知结果任务。
- provider已授权任务继续使用原租约、存储故障、重试和恢复规则。没有Host不派发；最后Host离开有限收尾。关闭provider不删除任务或产物。

## 隔离证据

`tests/test_production_entry.py`不注入adapter_factory/upload_factory，直接调用默认run_backend，只替换网络为httpx2.MockTransport，并由现有socket护栏禁止外网。覆盖：

1. 真实生产组合接收本地MP4、持久上传、一次生成提交；关闭后重新打开数据库，按同request_key重放、查询、下载、复制，字节相同。完整集合未知仍partial。无Host时上传和提交计数均为零。
2. local request/stream均拒绝；local任务和删除授权字段模拟的旧任务，连续两次重开、重放仍拒绝上传/提交/查询/引用提取，网络调用计数为零。
3. 安装.env优先、模式冲突拒绝、非法值拒绝。
4. SQLite触发器注入授权隔离事务失败，事务回滚且没有网络操作。生产调用位于RPC start之前，失败传播使后端安全退出。

这里的后端重开在同一pytest进程完成：关闭所有权后删除专用测试发现记录，以免存活的pytest PID触发OLD_PROCESS_STILL_ALIVE。该夹具不是跨进程重启证据；既有独立进程/租约测试另行保留，实际品牌Host仍待验收。

初次测试夹具遗漏object/model导致SUBMISSION_UNKNOWN，正好验证严格响应身份检查；补齐合成响应后成功。另有同PID发现记录问题及初始Ruff格式问题，均修正，未修改生产所有权检查或放宽解析。详细最终检查结果见implementation-progress.md。

## 验收限制

未在本轮把安装.env切换为provider，也未接触日常状态库。旧专用真实验收库没有新授权标记，不能直接拿来启用自动执行。13.3下一步先按windows-host-preparation.md在专用环境使用local做零调用Host接入；完整新入口真实闭环需后续明确授权。13.1干净Windows及13.3实际Host任务仍未完成，业务主规范未同步、change未归档。
