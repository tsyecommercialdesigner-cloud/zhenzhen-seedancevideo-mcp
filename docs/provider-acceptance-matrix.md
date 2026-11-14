# 供应商最小验收矩阵（当前证据）

2026-11-14本轮契约复核完成：按原完成判断交付1.2错误/证据映射与未知回退、1.5逐模型26行差异和来源台账、1.6已知不符拒绝/未知提示规则；修复实际MCP预检、接收事务与派发前未接入本地样片事实的问题，重新关闭6.3。全量546项隔离测试通过，当前65/67，剩余13.1干净Windows与13.3实际Agent Host验收。调查完成不等于供应商未知规则获证；详见docs/contract-review-closure.md及docs/model-contract-audit.json。本轮0次供应商请求、0次收费；历史13次，当前窗口5/10、余5，实扣47.020240/¥未变。未提交或推送Git，业务主规范未同步、change未归档。

以下续记保留各阶段状态；当前状态以上述复核为准。

2026-11-14复核：62/67，剩余5项。13.4按原完成判断完成：两个api_id、常规代表差异、两区域样片/成片、独立超分、上传、优化单次授权和实扣已有证据；26模型逐项列出实际与契约覆盖。不宣称所有参数、26模型、实际Host或完整产物集合全部验收。历史候选表由以下当前证据取代。


## 授权、素材与费用

- 历史已用8次后，用户新增8次，与旧余量2次合并为新授权窗口10次；当前窗口累计用5/10、余5，终身账本已用13/18。历史记录不清零。结果不明的POST意图也占次数，不能自动重提。
- Fast/Standard之后本轮单次优化再新增1次收费提交。已观察实扣合计47.020240，币种原值`¥`；详见[逐笔账本](paid-test-ledger.json)。未约定金额硬上限，既有实扣不是下次报价；不推导成片费用公式。
- 后续如有必要，仅复用既有素材、最低允许参数。普通/样片4秒480p；成片仅native1080p；独立超分最低720p。新窗口与历史累计分开记录，未知提交也占预算。
- 已用视频：此前Mini生成的MP4，4.041667秒、823227字节；既有图片：其JPEG尾帧，112496字节。输入摘要与交付证据见下列专项记录；无用户新素材、外部音频或跨账号素材授权。
- 此前普通请求优化与音频关闭；本轮Mini t2v经用户单次明确许可优化true，音频仍false。成片/超分不发送优化字段。没有修改持久偏好，未把通用收费授权当作优化授权。

## 26个Seedance模型逐项覆盖

所有模型均有已提供契约与本地注册/参数隔离覆盖；“仅契约”表示未做真实供应商提交，不表示全部接口细节均已核实。模型族未知项见[契约台账](provider-contract-evidence.md#当前剩余契约证据映射2026-11-14)。

| 模型 | 当前真实证据/限制 |
| --- | --- |
| `seedance-2.0-standard-t2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-standard-i2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-standard-multi` | 统一队列/MCP闭环，账本12；既有JPEG+MP4、4秒480p/1:1，优化false |
| `seedance-2.0-fast-t2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-fast-i2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-fast-multi` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-mini-t2v` | 直接取证1、2及单次优化队列闭环13；4秒480p；尾帧与优化分别有局部证据 |
| `seedance-2.0-mini-i2v` | 统一队列/MCP闭环；账本6；4秒480p，既有单张JPEG，adaptive |
| `seedance-2.0-mini-multi` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-global-standard-t2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-global-standard-i2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-global-standard-multi` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-global-fast-t2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-global-fast-i2v` | 统一队列/MCP闭环，账本11；单张既有JPEG、4秒480p/adaptive，优化false |
| `seedance-2.0-global-fast-multi` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-global-mini-t2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-global-mini-i2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.0-global-mini-multi` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.5-standard-t2v` | 仅draft=true：直接取证4、队列闭环7；4秒480p；普通模式未实测 |
| `seedance-2.5-standard-i2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.5-standard-multi` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.5-standard-draft-to-video` | 统一队列/MCP闭环；账本8；同账号国内新样片，native1080p，显式mp4 |
| `seedance-2.5-global-standard-t2v` | 统一队列/MCP样片闭环，账本9；4秒480p draft=true，优化false；普通模式未实测 |
| `seedance-2.5-global-standard-i2v` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.5-global-standard-multi` | 仅契约及隔离覆盖；真实未执行 |
| `seedance-2.5-global-standard-draft-to-video` | 统一队列/MCP闭环，账本10；同区域新样片、native1080p/显式mp4 |

共26个：8个有局部真实证据、18个仅契约/隔离覆盖。任何一个成功样例都不证明该模型全参数范围。

## 两个api_id与完整流程

| 能力 | 已完成证据 | 未覆盖 |
| --- | --- | --- |
| `seedance-video` 常规 | Mini i2v经MCP提交、托管JPEG上传、查询、主视频下载、复制、请求去重；直接Mini t2v取证；global Fast i2v、国内Standard multi已完成上传/生成/下载/复制 | 其他模型/模式、音频输入 |
| 国内样片→成片 | 新样片及其成片分别显式入统一队列；下载复制摘要一致；原样片保留 | 七天边界、外部样片身份核验、默认格式、mov；不自动串联 |
| global样片→成片 | 账本9、10，分别显式提交、下载复制摘要一致；见国际专项记录 | 七天边界、外部身份核验、默认格式、mov未验证 |
| `zhenzhen-upscaler` 独立tool | 账本3直接取证、5统一队列：既有MP4上传、720p、查询、下载复制、输入保留 | 更高档位、精确大小/时长边界；不计入26模型 |
| 上传 | 既有MP4及JPEG成功；有限重试/过期/混合素材/清理为合成隔离证据 | 真实音频、URL期限边界及全部模型素材限制 |
| 优化授权 | 账本13：Mini t2v true/single_allow真实队列闭环；前后持久偏好相同、下一次预检默认false；持久允许/撤销另有隔离测试 | 不证明内部改写或质量提升；其他模型开启优化未实测 |
| 实际费用 | 十三笔外层data.usage，原金额与币种持久化 | 退款0、延迟结算和终态长期稳定性 |

证据：[单次优化](optimization-queue-acceptance.md)、[Fast图生/Standard多模态](fast-multi-queue-acceptance.md)、[国际版样片/成片](global-queue-acceptance.md)、[生成/样片/成片队列](generation-queue-acceptance.md)、[独立超分队列](upscaler-queue-acceptance.md)、`tests/fixtures/provider/{live-observed,last-frame-observed,contracts-observed,generation-queue-observed}`。这些为SDK stdio/MCP协议验收，不能代替13.3实际品牌Host；没有人工画面质量验收。完整产物集合未知，已知视频可就绪但整体仍为partial。

## 后续最小候选与停止条件

| 候选 | 最低输入/参数 | 新收费提交 | 门槛/能证明什么 |
| --- | --- | --- | --- |
| global 2.5 t2v样片→global成片 | 复用既有方块提示词，4秒480p draft；成功后显式成片native1080p/mp4 | 已执行2 | 真实闭环通过；不证明7天起算/跨账号核验，不重复执行 |
| Fast i2v常规差异 | 复用既有JPEG，4秒480p，关闭音频/优化 | 已执行1 | global Fast i2v真实闭环通过，仅证明该配置 |
| Standard multi参考 | 复用既有JPEG+MP4，4秒480p，关闭音频/优化；2.0不传2.5专用reference参数 | 已执行1 | 国内2.0 Standard multi真实闭环通过；不证明2.5 edit/extend或音频边界 |
| 优化开启 | Mini t2v复用文案、4秒480p；用户单次许可，allow_once=true | 已执行1 | true真实闭环通过，不修改总是允许，不做额外付费对照 |

不为限流/鉴权/错误枚举故意创建收费任务，不为七天边界持续轮询。优先供应商既有完整响应、接口说明与只读证据；需要新增提交时先核对账本、输入摘要、同区域引用和最小参数。若提交结果不明，保留任务及意图，停止自动重提。当前最小代表矩阵完成，窗口保留5次余量，不为耗尽预算继续生成。未实测模型、音频和其他模式仍明确列为契约/隔离覆盖，不替代实际Host、干净OS或规则性核实。

## 13.4完成判断逐项索引

| 原完成判断 | 可核对证据 |
| --- | --- |
| 两个api_id与独立超分 | seedance-video多项队列记录；zhenzhen-upscaler的upscaler-queue-acceptance |
| 常规模型差异 | Mini i2v/优化t2v、global Fast i2v、国内Standard multi；未测模型在26行逐项标注 |
| 两区域样片/成片 | generation-queue-acceptance与global-queue-acceptance，均独立显式任务 |
| 上传/优化授权/实扣 | JPEG/MP4上传引用与托管摘要；optimization-queue-acceptance单次授权与不变偏好；13笔实际金额账本 |
| 授权素材/模型/次数/费用与核心契约门槛 | 各专项记录的已授权参数/来源、POST前intent、累计窗口和响应fixtures；不以未知成功/费用封装试派发 |

13.4关闭仅对应最小矩阵任务。1.2、1.5、1.6在后续独立契约复核中按各自完成判断关闭，供应商未知规则保留；13.1、13.3仍未完成，人工质量验收未执行。
