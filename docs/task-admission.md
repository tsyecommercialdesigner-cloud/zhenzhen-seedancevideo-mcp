# 本地任务接收与素材恢复

当前提供本地接收、去重和授权工具；自动上传／生成／轮询／下载尚未接入。accepted 只表示副本和任务已持久化，不表示已提交供应商。所有示例均适用于隔离测试，不是付费接口验收。

## 提交与找回

调用 `submit_video`：

```json
{"request_key":"example-video-1","request":{"model":"seedance-2.0-mini-i2v","prompt":"camera slowly dollies in","images":[{"local_path":"E:\\media\\first.png"}],"seconds":"5","enhance_prompt":false}}
```

外部素材把 local_path 对象换成 HTTPS URL 字符串；multi 和超分使用 metadata.content 对应的嵌套 url。`upscale_video` 是独立工具，request.model 为 zhenzhen-upscaler，不接受提示词优化。托管副本是独立文件，后续超分不会消费或删除原视频。外部 URL 不下载缓存，时效和可恢复性不作保证。

响应包含 accepted、task_id、request_key、version、stage、remote_state、output_dir、authorization、materials 和 unverified。materials 提供 material_id、SHA-256 和字节数，不包含视频内容。正常初始状态为 queued / not_submitted。内部 material_id 引用不是供应商 URL。

等待超时、响应丢失或 Host 退出后调用：

```json
{"request_key":"example-video-1"}
```

工具为 `find_task_by_request_key`。receiving / accepted / not_found 明确区分；receiving 不保证最终成功。满队列或原件已删仍可只读找回已接收任务。重复提交同 key 会对素材内容重新核对；同路径换内容返回 REQUEST_KEY_CONFLICT。不同 key 创建独立任务。接收失败释放预留，存储故障时暂留副本和预留供核对，不能擅自清空任务库。

## 提示词优化授权

默认关闭。单次用户同意可在 submit_video 顶层传 `allow_once: true`，此声明只属于该 request_key。request.enhance_prompt=false 始终优先。request.enhance_prompt=true 缺少单次或总是允许授权时返回 PROMPT_AUTHORIZATION_REQUIRED。

先 `get_prompt_optimization_policy` 取得 version，再调用 `set_prompt_optimization_policy`：

```json
{"enabled":true,"expected_version":0,"confirmed":true}
```

confirmed 表示 Agent 已取得用户明确授权，不是服务器自行证明用户意愿。该偏好同 Windows 用户所有 Host 共享并跨重启保存。撤销将 enabled 改为 false、expected_version 改为最新值；已接收任务的授权快照不改变，新任务按新偏好决定。写入失败不确认授权。成片和独立超分不应用此偏好，也不发送 enhance_prompt。

## 同内容修复

对尚未提交的任务，使用返回的 task_id、materials[].material_id 和最新 version 调用 `repair_task_materials`：

```json
{"task_id":"<task_id>","material_id":"<material_id>","source":"E:\\media\\restored.png","expected_version":1}
```

必须与原托管素材的 SHA-256 和大小完全相同；修改内容需新建任务。已开始提交则拒绝。修复阶段阻止派发；成功返回更新后的任务 version，不改变排队顺序。修复失败／重启中断需显式重试，不能当作已恢复自动执行。用户原件不会被删除。

验证对应 tests/test_admission.py 和 tests/test_runtime.py：实际 SQLite／Windows 文件句柄、共享后端 RPC 和 SDK v2 stdio 协议；并非真实供应商或实际 Agent Host 验收。SUCCESS 与费用完整响应仍待核实。
