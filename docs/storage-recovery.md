# 状态数据与离线维护

数据库位于固定用户根的 `state/tasks.sqlite3`。schema_version 使用 SQLite user_version，当前初始版本为 1。单独数据库线程串行执行短事务，WAL、synchronous=FULL、外键与有界 busy timeout 保证本地事务边界；网络、文件复制和删除不得在数据库事务函数内执行。

| 表 | 持久化职责 |
| --- | --- |
| tasks | 唯一 task_id/request_key、不可变入队序号、api/model/kind、规则版本、意图摘要、有效参数、输出目录、连接绑定与正交状态 |
| admissions | 接收操作标识、容量预留、登记临时素材；不表示 accepted |
| attempts | 阶段、轮次、epoch、intent/finished/reconciled、预算及退避；effect_started 防止重复执行同一尝试 |
| remote_observations | 原始状态枚举、关联 ID、时间、出处、有界结构化事实及终态冲突；不是原始响应日志 |
| material_copies / uploads | 托管归属、摘要、大小、顺序；上传临时 URL、过期、绑定和预算独立记录 |
| artifacts | 必需性、固定目标、临时路径、摘要及发布状态 |
| cleanup_jobs | 只能引用登记素材；原因、预算、执行与结果 |
| preferences | 授权值、版本、来源及撤销时间 |
| task_events / diagnostics | 业务版本事件、诊断索引；不保存 API 密钥 |
| charge_observations | 实扣原状态、十进制文本、币种、证据摘要；不保存预扣或上游成本 |

stage 表示 queued/preparing/submitting/tracking/downloading/settled；remote_state 独立表示 not_submitted/unknown/queued/running/succeeded/failed/cancelled。auto_mode 表示 active/needs_attention/abandoned；delivery 表示 none/pending/partial/ready/missing/changed。本地取消使用 locally_cancelled，不能冒充远端 cancelled；清理状态独立，不改变生成事实。

version 仅在业务变化时增加；重复相同动作或观察不新增副作用或预算。epoch 隔离旧操作，放弃后迟到事实可保存，但不能恢复下载或占位。生成占位以持久化 generation_slot_held 为准，未知仍占位；终态或显式放弃才释放。下调额度不能取消已有占位。

提交 intent、占位及跟踪开始在同一事务落账；run_effect 在副作用前持久化 effect_started，一条尝试只能开始一次。调用方取消等待不会撤销已接收事务。任何存储故障保留最近可靠状态并阻止新增副作用，未决 intent 核对完成后才解除门控。统一恢复协调已接入，合成独立后端有进程崩溃恢复测试；这不替代真实供应商或实际 Host 验收。

数据库事务不包含供应商请求或文件发布：intent 后、请求后、文件重命名后都存在崩溃窗口。恢复必须按记录核对，不能把未知提交重新 POST，也不能将磁盘上同名文件无条件视为本服务产物。费用缺失不阻止产物，Decimal 持久化能力不表示 SUCCESS／费用完整响应已核实。

普通启动拒绝过新／未知 schema、损坏库、空白既有库；不会降级、修复、删除或自动迁移。`database.initialized` 在首次初始化之前可靠写入；存在此标记或 WAL/SHM 而主库缺失时明确失败，不重建空库。不要通过删除标记绕过故障。

离线备份步骤：

1. 正常退出全部 Host，确认后端已结束并释放所有权锁；无法确认时停止维护，不强杀。不在后端运行时复制单独的 tasks.sqlite3。
2. 在全新备份目录保存用户根的 state、runtime 凭据绑定及 materials，另按任务登记保存外部输出目录的产物。不同位置须在同一停止窗口完成；不要只备份数据库而忽略素材、产物和 DPAPI 绑定文件。
3. 对数据库使用 SQLite backup API 得到一致快照，再运行 integrity_check。下面命令要求先填写已停止的源路径及不存在的备份文件；只复制本地数据，不执行生成或自动恢复。
4. 记录备份时间、schema 版本及备份期间保持停机的事实；在新的隔离目录核验 request_key、未知占位、产物登记和文件摘要。备份包含签名 URL 和用户内容，按私有数据保管。

```powershell
$sourceDb = 'C:\Users\Administrator\AppData\Local\ZhenzhenSeedanceVideo\state\tasks.sqlite3'
$backupDb = 'D:\Backups\Seedance\snapshot\tasks.sqlite3'
uv run --frozen python -c 'import pathlib,sqlite3,sys; s=pathlib.Path(sys.argv[1]); d=pathlib.Path(sys.argv[2]); f=d.open("xb"); f.close(); src=sqlite3.connect(s.as_uri()+"?mode=ro",uri=True); dst=sqlite3.connect(d); src.backup(dst); assert dst.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; dst.close(); src.close()' $sourceDb $backupDb
```

父目录需事先创建，目标存在时拒绝覆盖；命令失败则将该快照标为未验证，不覆盖源库。复制 WAL/SHM 文件不能替代一致备份。DPAPI 绑定依赖原 Windows 用户环境，不承诺移到另一机器或用户后仍可解密。

恢复不是回滚远端任务。恢复旧备份会丢失备份后已发生的本地记录，但远端可能已经接单并计费；恢复前必须识别该时间窗口并核对，不能把备份中的 queued 任务直接批量重派。首期没有自动恢复备份工具。数据格式不兼容时应使用匹配程序和独立迁移流程，保留原始副本，不以重建空库继续服务。

验证：`uv run --frozen pytest tests/test_storage.py tests/test_storage_fault.py tests/test_task_state.py tests/test_charges.py`。隔离备份测试在关闭数据库后运行相同 SQLite backup/integrity_check，恢复后未知状态和占位保留；未执行生产备份或真实远端恢复。


### 旧备份的离线核对门

备份后的远端提交不会因恢复旧库而撤销。以下 SQL 仅由维护者在**未启用、已留存原始副本的离线备份数据库**内执行；不是对正在运行的生产库执行，也不代表核实完成。它阻止未结束任务被恢复调度器盲目派发，保留 task_id、remote_id、原远端状态与已有占位。备份中没有的任务还需结合原库及可靠上游证据核对，不能依靠此 SQL 找回。

```sql
BEGIN IMMEDIATE;
UPDATE tasks
SET auto_mode = 'needs_attention',
    attention = json_insert(attention, '$[#]', 'BACKUP_RESTORE_REVIEW_REQUIRED'),
    version = version + 1
WHERE remote_state NOT IN ('succeeded','failed','cancelled')
  AND locally_cancelled = 0 AND auto_mode != 'abandoned';
COMMIT;
PRAGMA integrity_check;
```

这是维护演练使用的保守屏障；原始备份必须保留以核对既有异常历史；此屏障追加原因并提升版本，不清除原异常。没有工具可以用一句“已核实”消除该门。不要通过 resume_task_tracking 绕过；需要逐项形成恢复方案后在独立维护变更中处理，当前未交付自动数据恢复工具。`tests/test_installation.py` 验证先备份 queued、随后原库已提交、再打开带屏障副本时不会第二次提交；另有未知占位一致备份、schema=999 拒绝测试。
