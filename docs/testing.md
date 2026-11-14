# 隔离测试

运行 `uv run --frozen pytest`。测试使用临时 LOCALAPPDATA 与工作目录，移除服务凭据和代理环境变量；网络默认拒绝，只允许测试注册的回环假服务端口。不要给测试提供真实 API Key。

临时目录默认位于 `.cache/test-runs/<随机标识>`，每次使用新路径，不使用机器上既有 pytest 临时目录。Windows asyncio 的标准库 socketpair 内部唤醒连接被单独允许，不开放任意回环地址。测试目录保留供失败诊断，按项目清理规则处理。

`fake_http` 提供本地 HTTP 字节级交互并在测试结束关闭监听及工作线程；其中响应都是合成数据，不是供应商协议证据。`clock` 用于可控时间，`faults` 提供一次性命名故障注入。后续生产组件通过显式依赖注入使用这些设施，不增加生产配置绕过网络策略。

子进程测试须显式传入已清理环境和临时状态位置；进程内 socket monkeypatch 不会自动保护外部进程。当前子进程测试包含版本入口、隔离 Windows 后端和 SDK stdio 客户端；测试通过临时安装根、临时 LOCALAPPDATA 和子进程 sitecustomize 隔离真实 .env 与用户环境，未注入真实供应商适配器。后续供应商或 Host 验收须单独授权和记录，不混入默认 pytest。

代码检查：`uv run --frozen ruff check .` 与 `uv run --frozen ruff format --check .`。构建：`uv build`。CLI 已支持 stdio 前端与隐藏共享后端；生产供应商适配仍未完成。


## 安装与独立进程集成

- `uv run --frozen pytest tests/test_installation.py -q`：构建并检查源码包／wheel 白名单；全新目录解包、独立 .venv、uv --frozen --no-dev --offline 安装，通过该安装实际入口发现 Tools／空 Resources／Prompts。注册表配置由测试 bootstrap 隔离，但不替换安装目录解析；验证目录内 .env 优先。正常等待后端退出后移除本轮安装副本，检查外部状态和产物保留。当前 Windows 的干净 Python 环境不等同全新 OS/VM。
- `uv run --frozen pytest tests/test_windows_integration.py -q`：真实独立后端与多个 stdio 前端进程，合成 submit/query 和本地 HTTP 产物。控制文件、崩溃脚本只存在于 tests／本轮隔离目录，发行包不携带。强制退出通过 Popen 保留的 Windows 进程句柄，仅针对测试创建的独立前端（后端事先单独启动），不依赖 WMI/taskkill 枚举；后端分阶段 os._exit 用于崩溃恢复验证，不作用于实际服务。
- 验证并发 request_key 仅一次生成、任务 ID 与文件 SHA-256、冲突拒绝不影响现有客户端、宽限重连、准备／提交后／ID 落账后／产物发布前后崩溃、存储故障门及核对恢复。子进程均等待结束并关闭日志，真实用户配置、任务库与供应商不参与。

## 真实验收的离线准备

[供应商候选验收矩阵](provider-acceptance-matrix.md)列出 26 模型的契约／候选实测范围、独立超分、素材与费用授权待填项及逐例证据格式。[交付证据汇总](delivery-evidence.md)按八项业务能力映射实现、测试和剩余限制。矩阵不是自动执行脚本，默认 pytest 不运行真实案例；当前真实调用授权为 0，SUCCESS 和费用完整响应仍待核实。


## 上传单次组件

`uv run --frozen pytest tests/test_uploads.py -q` 验证历史文档 fixture 的结构、合成 URL、未知期限、大小／类型与摘要拒绝、multipart 字节、Bearer 作用域，以及上传失败／重定向不重试。MockTransport 只收发本地合成请求，不证明上游接受。生产调用方的持久化重试、素材租约与调度接线尚未完成，不运行真实上传。

上传持久化续记：`uv run --frozen pytest tests/test_upload_service.py tests/test_uploads.py -q` 覆盖上传准备、SQLite 重开、有限重试、临时引用截止、调度门与清理协调。见 [上传准备](upload-preparation.md)，不执行真实请求。

兼容端点接线：`uv run --frozen pytest tests/test_compatibility_adapter.py tests/test_provider_response.py tests/test_network.py -q` 使用合成传输运行实际请求／响应适配和调度持久化；不发送供应商请求，HTTP200只是测试设定，详见 [适配器范围](compatibility-adapter.md)。


安装切换补充：test_installation.py现在还将同一源码包分别安装到两个独立目录，候选与原安装先后启动，核对各自导入路径、同一任务／版本、无新增attempt、.env字节及外部产物不变，然后仅删除测试安装副本。此为同版本切换／回切，不代表跨版本升级、schema迁移或干净OS验收。剩余门槛见[剩余任务清单](remaining-work.md)。
