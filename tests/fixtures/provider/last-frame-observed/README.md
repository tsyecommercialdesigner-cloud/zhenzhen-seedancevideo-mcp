# 尾帧真实取证（2026-11-14）

用户授权最多10次最短时长最低分辨率测试，本轮仅1次POST seedance-2.0-mini-t2v：4秒480p、1:1、return_last_frame=true、enhance_prompt=false、generate_audio=false。3次GET，第3次SUCCESS，实扣0.8028、币种¥。两次无Bearer产物GET成功。原始记录及视频/图片保存在受ACL保护且Git忽略的.cache/artifact-probe-20261114。

脱敏保留完整键、层级及叶类型，任务ID统一task_last_frame_probe_01；URL替换example.invalid；私有字符串替换[REDACTED]，私有数值替换同类型0。0不是账单值。SHA-256关联原始记录；未保存Authorization头。

尾帧路径data.data.content.last_frame_url；上游results的outputType及URL后缀均为png，但实际Content-Type=image/jpeg，ffprobe为mjpeg，640×640。视频为H264 MP4，640×640，4.041667秒；请求480p不等于实际高480像素。下载响应的Accept-Ranges=bytes只是声明，未进行Range续传验证。网络层使用DNS固定目标，不能从内部response.url变化推断发生重定向；具体重定向链仍待核实。

仅证明此次Mini任务返回两项可下载产物，不能证明所有模型、尾帧必需性、集合穷尽、链接期限、刷新或长期恢复。实际媒体未纳入版本控制；fixtures用于隔离回放，不再访问供应商。
