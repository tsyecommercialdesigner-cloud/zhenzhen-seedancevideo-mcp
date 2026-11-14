# 网络策略与内部适配器

本轮实现 NetworkPolicy、错误分类和能力门控，未启用真实供应商适配器。SUCCESS 与费用完整响应、上传响应及取消／核对／刷新凭据等仍依契约台账待核实。没有因为本地测试通过而宣称供应商支持。

## 网络配置

沿用 `ZHENZHEN_SEEDANCE_PROXY_URL`、`ZHENZHEN_SEEDANCE_PROXY_BYPASS`、`ZHENZHEN_SEEDANCE_CA_FILE`，后端启动时固定。HTTP_PROXY、HTTPS_PROXY、NO_PROXY 和 PAC 不会隐式生效。

- HTTP／HTTPS 显式代理；绕过支持精确域名、以点开头的域后缀、字面 IP／CIDR。每跳重新匹配原目标 hostname，不使用前一跳的代理决定。
- 使用系统可信根，可附加 PEM CA；HTTPS 目标和 HTTPS 代理均使用该信任配置，证书校验不可关闭。坏 CA 初始化拒绝；代理不可达不切换直连。
- 连接、读写空闲与连接池等待有界；连接使用 CONNECT_TIMEOUT_SECONDS，其余使用 REQUEST_TIMEOUT_SECONDS。整个请求／完整流读取再受 REQUEST_TIMEOUT_SECONDS、UPLOAD_TIMEOUT_SECONDS 或 DOWNLOAD_TIMEOUT_SECONDS 的阶段总期限约束。
- 客户端按代理、鉴权用途及原 origin 隔离，避免共享 IP 上不同 TLS 域名复用错误会话；最多 64 个客户端池，超限明确拒绝。单池连接数由已配置的四类并发上限之和界定，阶段并发由调度／下载模块控制。

## 目标与重定向

生产目标仅 HTTPS。DNS 全部返回地址必须为公网，随后固定经过校验的 IP 建连，同时保留原 Host 和 TLS SNI／证书名称，避免校验与连接之间重新解析到私网。代理也连接固定的目标 IP。回环、链路本地、私网和混合公网／私网解析均拒绝。测试可通过内部构造注入指定回环 origin；没有环境变量或 MCP 参数可以启用此例外。

只对 GET 逐跳处理重定向，最多六次请求，循环和 HTTPS 降级拒绝。生成／上传 POST 遇到重定向明确停止，不重发请求体。API Bearer 仅初始受信 origin 可用；跨 origin 后永久移除，不在后续跳回时重新附加。不使用响应 Cookie 携带 API 会话。产物下载默认无 API 凭据，403 不触发带密钥重试。

NetworkPolicy.request 对小响应执行字节上限；大产物通过 stream 接口流式消费，后续下载器负责文件上限与发布。网络错误只返回静态代码，不含签名 URL、代理密码或原始异常文本。

## 错误与能力门控

`classify_http` 只给出保守重试／保护建议。401/403 保护两个 API；查询暂时故障可消耗预算；提交任何 HTTP 错误均不能单凭状态推导“未接单”。可靠未创建证明是内部适配器的 NotCreatedEvidence，须同时启用已核实核对能力；MCP 调用方不能提交 verified=true 或任意 task_id 绕过。

取消、提交历史核对、产物 URL 刷新及账号识别默认 CAPABILITY_UNVERIFIED。相同连接绑定可接续；新凭据／端点不能盲接旧任务。既有 CredentialBindings 的核验门控继续生效。

测试证据：tests/test_network.py 使用真实本地 HTTP、HTTP 代理、HTTPS 代理、自签名 TLS、合成传输错误；tests/test_scheduler.py 的 HTTPFixtureAdapter 仅访问本地假服务。tests/fixtures/network 的证书与私钥为合成测试材料，不写入系统证书库、不用于生产。
