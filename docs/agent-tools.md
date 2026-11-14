# Agent 工具使用手册

适用版本：0.1.0.dev0，MCP SDK 2.3.0，Windows。
当前发行入口已接通供应商适配器，默认 execution_mode=local 不执行供应商请求，显式配置 provider 并重启才启用。实际 Host 工具发现及 Codex／DSH 跨 Host 主视频交付已有分范围证据，详见[验证记录](verification-add-local-video-generation-service.md)；不能把这些证据推广为全部模型、Host 或完整产物集合均已验收。

## 启动与配置

在 MCP 实际安装目录配置 `.env`，使用 `ZHENZHEN_SEEDANCE_API_KEY`；文件字段优先，缺失才回退到进程／用户环境变量。不要将密钥写入 Host 命令参数。

常见 Host 的 stdio 配置结构如下；实际 Host 配置入口另需按其版本核对：

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

## 调用顺序

每个调用均返回 JSON 对象。业务拒绝用 `ok=false`、`error` 和脱敏 `diagnostic` 表达；检查业务字段，不能只检查 MCP 传输成功。

1. `get_service_status({})` 区分本地状态、额度、存储故障和供应商状态。`generation_execution=not_implemented` 表示当前未启用供应商执行；检查execution_mode，provider模式下为adapter_installed。上游未知不妨碍本地查询和已有产物复制。
2. `get_capabilities({"api_id":"seedance-video","model_id":"seedance-2.0-mini-t2v"})` 读取参数限制与待核实能力。
3. 可选 `preflight_video_task({"request":{"model":"seedance-2.0-mini-t2v","prompt":"一只狐狸在雪地奔跑"}})`。预检不上传、不创建任务，不保证稍后接收；本地素材只检查参数形状，不冒充已经读取验证。
4. 提示词优化授权发生在正式提交前。单次允许：提交 `allow_once=true`；总是允许：先读取 `get_prompt_optimization_policy`，再调用 `set_prompt_optimization_policy({"enabled":true,"expected_version":0,"confirmed":true})`（版本使用实际查询值）。撤销用 enabled=false。单次 request.enhance_prompt=false 优先。成片、超分不适用。已入队任务不会再弹确认。
5. `submit_video({"request_key":"my-stable-request-001","request":{"model":"seedance-2.0-mini-t2v","prompt":"一只狐狸在雪地奔跑"}})`。保留返回的 task_id/version。响应丢失用 `find_task_by_request_key({"request_key":"my-stable-request-001"})`，不要换 key 盲目重提。receiving 不等于 accepted。
6. `get_task({"task_id":"实际任务 ID"})` 查询本地快照。`wait_task({"task_id":"实际任务 ID","after_version":1,"timeout_seconds":20})` 等待业务版本变化；默认 20 秒，默认配置上限 30 秒。wait_timed_out=true 只表示等待结束。取消等待不取消生成。
7. `list_tasks({"needs_attention":true,"limit":20})` 是共享非消费异常名单。可叠加 remote_state 或 attention_reason。next_cursor 必须携带相同筛选；不承诺跨页快照，重启后游标失效，从首页重读。生成未知和下载、清理错误分别反映。
8. 单次查询：`refresh_task({"task_id":"实际任务 ID"})` 有远端及保存副作用。恢复持续跟踪：`resume_task_tracking({"task_id":"实际任务 ID","expected_version":实际版本})`。重复恢复不叠加预算，VERSION_CONFLICT 返回最新任务。生产适配器未接入时返回 CAPABILITY_UNVERIFIED。
9. `list_artifacts({"task_id":"实际任务 ID","limit":20})` 返回 artifact_id 与绝对路径。此调用检查存在性并可能更新外部删改状态，因此不是只读标注。`verify_artifact({"artifact_id":"实际产物 ID"})` 进一步检查摘要。
10. `copy_artifact({"artifact_id":"实际产物 ID","target_path":"videos/result.mp4","workspace_root":"E:\\my-agent-workspace"})`。相对目标限制在工作区内，外部目标需显式绝对路径；默认不覆盖，overwrite=true 才允许覆盖。原产物保留，响应没有视频字节、Base64 或签名 URL。

## 管理工具

- `cancel_task(task_id, expected_version)`：仅提交前本地取消；上游取消待核实。
- `abandon_task(task_id, expected_version, reason, acknowledge_remote_may_continue=true)`：释放本地占位并触发托管输入清理，远端可能继续并计费，不冒充失败或取消。
- `retry_unsubmitted_task(task_id, expected_version)`：仅适配器取得可靠未创建证据后允许；不接受调用方提供“已核实”标志或任意 task_id 绑定。
- `repair_task_materials(task_id, material_id, source, expected_version)`：补回相同内容；source 为本地绝对路径。
- `retry_material_cleanup(task_id, expected_version)`：只重试已登记清理待办，不允许任意路径删除。
- `retry_task_download(task_id, expected_version, overwrite=false)`：恢复下载，异常目标显式覆盖；不重新生成。
- `get_diagnostic(diagnostic_id)`：有界脱敏诊断，不输出原始日志。费用尚未返回是 null，不是 0；SUCCESS 与实际费用响应已有局部真实样例，不能推广到所有模型。
- `upscale_video(request_key, request)`：独立入口固定 zhenzhen-upscaler，metadata.content 中恰好一个 video_url，目标分辨率默认 1080p；不接受生成提示词优化。不自动由生成任务触发收费超分。

## 可执行隔离演练

```powershell
uv run --frozen pytest tests/test_tools.py -q
```

该演练启动真实 stdio 前端与两个协议客户端，使用合成适配器、隔离任务库和本地假下载服务完成能力、预检、优化授权、提交／找回、等待、恢复和复制；不会调用真实供应商。取消与多调用竞争亦在该文件覆盖。通用 Host JSON 只作接入示例；实际 Host 证据及其限制见验证记录。


## 2026-11-13 主视频引用与部分交付

以下为该时点的历史记录；SUCCESS／费用及实际 Host 的后续证据见最新验证记录，完整产物集合仍待核实。

已确认的 metadata.url 可通过内部 CompatibilityAdapter（注入任务库）接通主视频下载、持久化与复制。任务查询新增 artifact_set_status；完整集合未知时为 unverified，已就绪主视频可单独交付，任务保持 partial，保留 ARTIFACT_SET_UNVERIFIED 和输入托管副本。显式放弃仍按既有规则清理素材。测试 tests/test_main_video_delivery.py 使用合成传输覆盖下载、复制、403恢复、数据库重开、重复查询、格式和引用关联以及清理协调。四份样例仍是契约来源；尾帧／完整集合、SUCCESS、费用完整响应待核实，无真实调用证据。


主视频协议复验：独立stdio客户端的提交、等待、主视频下载／复制，以及最后客户端退出、发布前后崩溃和下载待处理恢复，见[端到端验证说明](main-video-protocol-validation.md)。此为合成供应商、多进程协议证据；实际Host和供应商仍未验收。
