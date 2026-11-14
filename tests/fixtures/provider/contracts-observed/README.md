# 样片、独立超分及只读错误证据

2026-11-14累计10次以内授权，本轮2次收费提交，此前2次，累计4次。样片seedance-2.5-standard-t2v：4秒、480p、draft=true、音频/优化false。超分zhenzhen-upscaler：使用此前生成的4.041667秒MP4，先上传一次，resolution=720p，无prompt/seconds，不调用price-preview。各查询3次成功，各下载一次，无Bearer；另2次只读错误查询（未鉴权与不存在任务）。

实扣仅外层data.usage：超分0.875/¥，样片2.688892/¥。超分960×960、样片640×640，均4.041667秒；不把分辨率标签当像素。样片data.data.content.draft=true及draft_task_id匹配原task_id；无7天起算、身份/有效期核验或成片默认格式证明。超分本次无需客户端额外price-preview操作；精确媒体上限仍未知。

JSON保留原键/层级/类型，任务ID统一化；私有字符串[REDACTED]、私有数值同类型0，URL变成example.invalid。0不是实扣值。原始响应及媒体在受ACL保护、Git忽略的.cache/contracts-round-20261114。此为直接接口取证，不等于生产队列、MCP或实际Host验收。
