# 用户提供的契约样例

`submit-queued.json`：2026-11-13，用户回复本会话关于 `/v1/video/generations` 完整响应的核实请求时提供。作为提交后 queued 响应样例登记；仅去除 Markdown 围栏并调整缩进，字段和值保持原样。

这是用户提供的脱敏契约样例，不是本项目真实调用抓包，也不是合成假服务响应。HTTP 状态码和响应头未提供。样例说明顶层 id、object、model、status、progress、created_at 的形状，不证明字段必填性、progress 的整体范围、created_at 的单位，或其他模型和查询状态的完整响应结构。

用户随后于同日提供三份查询响应：`query-in-progress.json`、`query-completed.json`、`query-failed.json`。仅调整缩进，保留原字段与占位值；对应 GET /v1/video/generations/{id} 的处理中、成功和失败。

成功响应通过 metadata.url 提供主视频引用；处理中 URL 可为空，失败样例没有 metadata、created_at。失败 progress 也为 100，不能据进度数值推断成功。三份样例没有 usage，也没有 SUCCESS 状态，不据此发明其完整封装。失败任务 JSON 不等于 HTTP 请求错误响应。

样例中的占位 ID 和 URL 不得用于真实请求；这些查询样例来自用户，不是由提交样例推导的合成数据。
