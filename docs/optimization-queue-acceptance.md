# 单次提示词优化统一队列真实验收

2026-11-14，用户明确单次允许开启优化，不修改“总是允许”。本轮使用seedance-2.0-mini-t2v，复用此前提示词`A small red wooden cube slowly rotates on a plain white table. Static camera.`，4秒、480p、1:1、generate_audio=false；enhance_prompt=true，MCP submit_video传allow_once=true。

## 真实闭环与授权隔离

通过真实MCP SDK stdio客户端与生产共享后端、CompatibilityAdapter、NetworkPolicy、接收/调度/下载/复制服务完成，不直接调用HTTP绕过队列。后端使用独立验收LOCALAPPDATA和配置目录，沿用已有凭据与网络策略，没有打开或修改用户现有Host任务库。

提交前调用get_prompt_optimization_policy与无生成副作用preflight_video_task，正式提交的授权来源为single_allow、enabled=true。同key重复submit_video返回同一任务。实际发送payload和数据库effective_parameters的enhance_prompt均为true；授权事实不被一次重放改成持久允许。

完成后只读查询偏好，前后均enabled=false、version=0，preferences表无写入行。未调用set_prompt_optimization_policy。随后用相同文案、但省略enhance_prompt与allow_once的预检，得到enabled=false、source=default_false，没有为后续任务提交生成。这同时验证单次允许不外溢，用户原“总是允许”偏好未被访问或修改。

本轮仅1次收费POST、9次同任务查询、0次上传；1份主视频下载并经copy_artifact复制到显式工作区的optimized-delivered.mp4，默认不覆盖，原产物与副本SHA-256相同。实际视频h264、640×640、4.041667秒、734552字节。后端正常退出0；1个任务、1次submit attempt，生产源码摘要未变。

实扣0.8028 / ¥；历史累计47.020240 / ¥。当前授权窗口累计5/10、剩余5；历史共13次/终身授权18次。本轮提交前记录独占intent并扣次数，未重提或另开对照任务。

## 证据边界

本次证明已授权true被正确发送并被供应商接受，完成生成与交付；不证明优化算法内部做了何种改写、不宣称视觉质量提升。未做额外付费false对照或人工画面质量验收，也不推广为26模型均实际测试。完整产物集合仍unverified，任务partial，不冒充完整集合交付。

原始响应、工具结果、数据库、媒体在Git忽略且ACL保护的.cache/optimization-queue-20261114，生产入口默认派发和实际Host配置未改变。公开脱敏响应位于tests/fixtures/provider/optimization-queue-observed；[机器证据](optimization-queue-acceptance.json)记录授权快照、前后偏好、后续预检、摘要、次数和费用，不公开ID/签名URL/密钥。

13.4最小矩阵现在已有两个api_id、Mini/Fast/Standard代表差异、两区域样片/成片、独立超分、上传、单次优化与实扣的证据，并逐项标明26模型中8个局部真实、18个仅契约/隔离。按任务原完成判断关闭13.4，不要求全部26模型收费实测；未测音频/其他模式/边界仍逐项保留，不删除或降低其能力约束。实际Host、干净Windows及1.2/1.5/1.6规则性调查仍未完成。没有Git提交推送、业务主规范同步或归档。
