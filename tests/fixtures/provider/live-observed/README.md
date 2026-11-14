# 经授权的真实接口证据

2026-11-13用户授权：为第1项SUCCESS／费用完整响应最多进行10次收费测试，限最短时长、最低分辨率。本轮仅提交1次seedance-2.0-mini-t2v，4秒480p，关闭优化和音频；无素材上传、产物下载或其他模型提交。查询4次，第4次返回SUCCESS与实际usage。

文件为完整JSON键与层级的脱敏副本；provenance.json记录端点、HTTP状态、时间和私有原始记录摘要。任务标识统一替换为task_live_probe_01；账号、渠道、计费内部值、上游ID、请求回显等字符串替换为[REDACTED]，敏感数值替换为同类型0。这些0是脱敏占位，不是实际零费用。URL替换为不可用的example.invalid地址。时间、枚举、模型和外层data.usage实际费用保留。未解析请求回显字符串内部内容，不伪造其字段。

原始响应保存在受当前用户及SYSTEM ACL保护且被Git忽略的.cache/paid-contract-probe，未保存请求Authorization头。只对data.usage.amount=0.8028、currency="¥"记录实扣；不将quota、price_estimate、data.data.usage或上游token字段作为金额。货币符号按返回原值保留，未擅自转换为ISO币种。

真实GET响应为code/message/data封装，data.task_id匹配POST顶层id；data.id为另一个数值字段，不能作为远端任务ID。处理中为data.status=IN_PROGRESS；成功为SUCCESS，主视频位于data.result_url，且此次与data.data.content.video_url一致。无顶层metadata.url。现有四份用户样例仍保留，不能用本次响应覆盖其契约来源。

此证据仅覆盖一个Mini模型、一个账号、一个成功任务；不能证明draft-to-video、其他模型、退款、延迟结算及未来终态稳定性。8.4已于2026-11-13通过隔离回放完成该封装解析；取证脚本仍不等同完整MCP或真实Host验收。
