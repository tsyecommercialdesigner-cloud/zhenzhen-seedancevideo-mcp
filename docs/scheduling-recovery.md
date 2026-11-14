# 调度与恢复（内部服务阶段）

Scheduler 已可用注入适配器自动运行排队、提交和查询，并持久化状态；生产后端尚未绑定真实适配器，MCP 管理工具已接线，未核实上游操作保持能力门控。下列是内部服务接口及隔离测试示例，不是已经可调用的全部 MCP 工具。生成成功只进入 downloading/pending，真正文件下载／发布、终态素材清理及跨阶段恢复依赖第 10–11 组。

## 执行与额度

`await engine.run(stop_event)` 先恢复可靠状态，再并行推进派发与轮询。可派发 FIFO 保留 sequence；API／模型保护、身份不兼容及素材非 ready 被跳过。准备受 UPLOAD_CONCURRENCY 限制，且不超过当前可用生成位；准备结束仍按原可派发顺序提交。生成、成片、独立超分共用 GENERATION_CONCURRENCY。没有可用额度就不做新的准备。

API 保护持久化到 preferences 中独立的 dispatch 命名空间。队列任务保留顺序，新请求明确拒绝；旧 request_key 找回可用。只有配置已修复重启或已核实无付费检查才可调用内部 clear_protection，不靠反复付费请求试探。准备期 API 保护不把排队任务假报生成失败。

生成请求前，SQLite 同事务保存占位、提交 intent、epoch 和跟踪起点。发出前／后中断，或收到 ID 尚未落账，均保留未知和占位；不自动重复 POST。`retry_not_created` 需要内部核对能力和可靠证明，并由显式动作授权新尝试。证明与原尝试历史保留。本地 request_key 去重不承诺上游 exactly-once。

## 三类超时与查询预算

- 请求超时约束一次 HTTP／适配器操作，不能据超时判断生成失败或未创建。
- 工具等待结束只影响调用者等待，不取消已授权后台工作。
- 跟踪从开始提交计时，排队不计、停机计；关闭跟踪期限不关闭查询错误预算。到期停止新查询，在途查询按请求期限有限收尾，若成功则保存成功，否则标记 TRACKING_TIMEOUT 并保留占位。

query_budget 尝试行按 tracking_round 保存剩余错误预算与 next_attempt_at；普通 queued/in_progress 不消耗预算，成功查询结束连续失败段。暂时失败有限指数退避并加抖动，等待不占网络并发。配置或无效响应直接待处理，不重复浪费预算。query_failed/query_succeeded 事件保留历史。耗尽、身份不兼容和已放弃状态不因重启或网络恢复自动复活。

进程内 UTC 与单调时钟结合，回拨不延长期限；恢复时发现时间早于跟踪／观察记录，转 CLOCK_ROLLBACK_REQUIRES_REVIEW，不悄悄获得新预算。旧任务输出目录不随新配置迁移；降低额度保留已有占位，消化后再派发。

## 查询、刷新、恢复

```python
snapshot = await engine.state.get(task_id)  # 本地读取，不访问网络
snapshot = await engine.refresh(task_id)  # 单次查询；并发调用合并
snapshot = await engine.resume(task_id, expected_version=snapshot["version"])
```

刷新仍运行不会开启自动轮询。可靠成功／失败更新远端事实并消退相应查询异常；成功授权下载 pending，不伪称 ready。已放弃任务也可显式刷新找回；旧 epoch 的迟到结果只保存事实，不能自行恢复执行。

resume 创建新轮次和预算，保留历史；重复恢复不会再次重置。已放弃且仍生成需重新取得额度，无额度明确拒绝；原来持有额度的任务不重复占位。原连接配置恢复后仍需显式恢复。

## 取消与放弃

```python
await engine.state.cancel_unsubmitted(task_id, expected_version=version, now=utc_timestamp)
await engine.state.abandon(
    task_id, expected_version=version, reason="用户明确停止跟踪", confirmed=True, now=utc_timestamp
)
```

取消先于提交 intent 生效时不 POST；提交先行后不能报告本地取消成功。远端取消仍待核实，不支持的路径明确返回 REMOTE_CANCEL_CAPABILITY_UNVERIFIED；合成取消待确认状态取得成功仍按成功进入下载。

放弃须确认远端可能继续运行、计费；释放本地额度并标记输入清理待办，不冒充失败或取消。实际远端并行数可能超过本地额度。放弃成功但未下载完的任务保留生成成功和已有产物。管理操作校验 version，旧 epoch 不恢复调度。

## 停机与未完成项

关闭停止新工作，在 SHUTDOWN_DRAIN_SECONDS 内等待在途查询／提交，随后取消 I/O；未知提交下次仍不重提。查询预算与退避保留，文件恢复不得由调度器猜测完成。当前已验证提交／跟踪恢复、身份门控和额度重建；下载临时文件／发布核对与清理恢复模块已分别实现，但跨全部阶段的统一启动／停机协调验收尚未汇总，任务 9.6 保持未勾选。

隔离验证命令：`uv run --frozen pytest tests/test_scheduler.py tests/test_network.py -q`。测试使用合成适配器、本地 HTTP 假服务及 SQLite；未验证真实供应商、真实 Agent Host 或完整视频落盘交付。


## 统一启动恢复与有限停机（9.6）

生产后端在发布 discovery 之前依次完成接收残留处理、占位／阶段事务核对、产物发布恢复和清理待办扫描；注入适配器时同时核对查询预算与期限。恢复失败不发布服务，也不开始派发。没有生产适配器时，本地恢复与查询可用，生成仍不执行。恢复耗时不消耗首个 Host 的连接宽限期。

占位按未结束且未放弃的远端事实重建，不受新并发上限截断。原输出目录保持不变，查询退避与预算保留；停机消耗跟踪期限。已保存远端 ID 的正常提交恢复为跟踪；无 ID 的提交保留未知、占位和素材。needs_attention／abandoned 不自动复活，连接身份不兼容转待处理并保留占位。准备中但未提交的任务恢复排队且 sequence 不变。

Lifecycle 统一跟踪派发、轮询、下载和清理。最后 Host 退出先关派发门，宽限期可继续已有任务查询／下载；进入 draining 后不再启动后台新操作。RPC 与后台工作均纳入退出判断，共用剩余收尾期限，期满取消 I/O 并等待文件句柄、短事务收尾。未完成 intent 保留供下次恢复，不承诺远端请求被取消。没有按每个服务额外重置一轮 drain 时间。

验证入口：`uv run --frozen pytest tests/test_lifecycle.py -q`。使用合成适配器和真实数据库重开，覆盖队列／准备、提交未知／已知 ID、跟踪、下载发布前后、清理、身份切换、降额度、旧输出目录、预算保留、跟踪过期及统一收尾；不替代真实 Host／供应商验收。真实上传的接口与预算仍属于 8.3。
