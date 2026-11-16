## ADDED Requirements

### Requirement: 已发现产物就绪且集合未知的展示

系统 SHALL 对已确认远端成功、至少一个产物已登记且所有已登记产物均为 ready、但完整集合未核实的任务提供独立展示状态，明确不再等待当前已发现产物下载；旧 stage、delivery 和完整性语义保持兼容。

#### Scenario: 已下载但集合未知
- **WHEN** 主视频及其他已登记产物均已 ready，且集合仍为 unverified
- **THEN** 返回 `display_stage=downloaded_unverified`，保留 stage、delivery=partial、集合未核实说明；允许查询、核验及复制已就绪产物，不声称所有必需产物完整。

#### Scenario: 存在下载或产物异常
- **WHEN** 任一已登记产物尚未就绪、缺失、变更或下载失败
- **THEN** 不显示 downloaded_unverified，分别反映当前未就绪或异常状态并保留恢复动作；不因为一个产物 ready 掩盖另一个未就绪产物。

#### Scenario: 输入素材保留
- **WHEN** 显示 downloaded_unverified
- **THEN** 不据此标记集合 complete、不触发完整交付清理、不改变远端状态或已存在的放弃语义；托管素材继续按现有规则保留。

#### Scenario: 已有任务与跨 Host 查询
- **WHEN** 符合条件的历史任务在升级或后端重启后由不同 Host 查询或等待
- **THEN** 一致展示上述状态和原持久事实，不发起上游查询、下载、重新生成或清理；没有登记产物或缺少可靠事实时不得猜测就绪。
