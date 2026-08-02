# 更新规则规范

- 按“输入开始，到结果生效或回滚结束”的顺序组织全文；

## 1. 适用范围

本规范适用于以下三类更新：

- `raw_source`
- `external_source`
- `manual_override`

适用于以下几类产物：

- 输入数据
- 参考表
- 过程文件
- 正式输出
- 当前生效版本
- 历史快照
- 历史日志
- 回滚审计

## 2. 核心原则

所有更新都必须遵循以下原则：

- 不直接覆盖 `current`
- 每次正式更新前先对 `current` 做快照
- 过程文件和正式输出必须分层保存
- 所有运行都必须生成独立 `release_id`
- 所有更新都必须支持追溯、审计和回滚
- 大文件和运行数据不进入 Git 仓库
- 仓库只保留代码、文档、测试、说明和旧脚本
- 所有原始数据、参考表、结果表、快照和运行产物统一放在 `.external_data/`

总流程：

1. 新数据进入 `incoming`
2. 分配新的 `release_id`
3. 先备份 `current` 到 `history/snapshots/<release_id>-before`
4. 执行更新
5. 结果写入 `releases/<release_id>/`
6. 审核结果
7. 审核通过后再切换 `current`
8. 审计和变化日志写入 `history`

## 3. 术语定义

### 3.1 `source-type`

`source-type` 表示本次输入数据的身份，而不是文件格式。

允许值只有：

- `raw_source`
- `external_source`
- `manual_override`

### 3.2 `batch_id`

`batch_id` 表示一次上传批次目录名。

建议格式：

- `YYYYMMDD_ext_batch_001`
- `YYYYMMDD_raw_batch_001`
- `YYYYMMDD_manual_batch_001`

### 3.3 `release_id`

`release_id` 表示一次正式运行的版本号。

建议格式：

- `YYYYMMDD-rawNNN`
- `YYYYMMDD-extNNN`
- `YYYYMMDD-manualNNN`
- `YYYYMMDD-rollbackNNN`

例如：

- `20260724-raw001`
- `20260724-ext001`
- `20260724-manual001`
- `20260726-rollback001`

### 3.4 `current`

`current` 表示当前正式生效的一整套结果。

### 3.5 `snapshot`

`snapshot` 表示一次更新前保存的旧版本快照。

### 3.6 `release`

`release` 表示一次运行产生的完整版本档案，包含输入说明、日志、审计、过程文件和正式输出。

### 3.7 `business_key`

`business_key` 表示“同一条目”的标准业务分组键。

固定字段为：

- `uniprot`
- `enzyme_type`
- `mutation`
- `sequence`
- `substrate`
- `smiles`

规则：

- `business_key` 是“条目分组键”，不是“单行唯一键”
- `business_key` 用于：
  - 判断是否属于同一条目
  - 正式业务去重前的条目分组
  - 人工审计和对账
  - 次级匹配
- 同一结果层内允许存在多条记录具有相同 `business_key`
- `manual_override` 使用 `business_key` 匹配时，必须额外检查是否唯一命中；若命中多条，不得视为精准命中
- 对 `external_source` 而言，若一条记录不满足以下任一组门槛：
  - `uniprot` / `sequence` 至少 1 个非空
  - `substrate` / `smiles` 至少 1 个非空
- 则该记录：
  - 不允许自动并入正式结果
  - 不进入正式业务去重
  - 必须写入 `rejected_rows.csv`
  - `reject_reason` 记录具体缺项原因

### 3.8 `record_key`

`record_key` 表示当前一次运行内部生成或继承的临时记录定位标识。

规则：

- 仅用于当前 release 内定位
- 仅用于工作区、中间过程文件和本次运行内部审计
- 不作为长期稳定主键
- 不参与正式 `business_dedup`
- 不作为长期 `manual_override` 的首选匹配键
- 不允许作为 `current` 正式结果层长期 patch 的唯一定位依据


### 3.9 `record_id`

`record_id` 表示正式结果层最终保留下来的单行稳定记录 ID。

它用于标识最终 `merged` / `conditions` 里的那一条正式记录，不能与 `record_key` 混用。

用途：

- 正式结果层单行精准定位
- `manual_override` 的首选精准匹配键
- 历史变化追踪
- 单行级回滚辅助定位
- 结果层变更审计

规则：

- 正式输出中继续使用物理列名 `record_id`
- `record_id` 格式固定为：
  - `frid_<20位hex>`
- `record_id` 必须在正式 `merged` / `conditions` 结果层单行唯一
- `record_id` 在去重、冲突拦截和防泄漏完成后生成
- `record_id` 是最终单行身份键，不是来源键，也不是条目键
- `record_id` 必须直接继承到 `conditions` 导出结果
- `conditions` 不允许再为同一正式记录重新生成另一套记录键
- 仅当正式单行身份发生变化时，才允许重算 `record_id`

### 3.10 `measurement_uid`

`measurement_uid` 表示“同一条目下是否属于同一实验候选”的 measurement 级键。

用途：

- 在同一 `business_key` 下判断是否属于同一实验候选
- 支撑正式业务去重
- 支撑实验级历史追踪与审计

规则：

- `measurement_uid` 格式固定为：
  - `muid_<20位hex>`
- `measurement_uid` 的 canonical identity 固定为：
  - `uniprot|enzyme_type|mutation|sequence|substrate|smiles|parameter_name|value_normalized|ph|temperature`
- 同一 `business_key` 分组下可以存在多条不同 `measurement_uid`
- 若两条记录 `business_key` 相同但 `measurement_uid` 不同，则允许同时进入正式结果层
- 若两条记录 `measurement_uid` 相同，但 `organism` 或 `ions` 不同，则不得自动合并，必须进入审计
- `measurement_uid` 只回答“是不是同一实验候选”，不是最终正式单行 ID

### 3.11 `update_mode`

`update_mode` 表示本次运行的更新策略。

允许值：

- `full_rebuildfull`  #整条旧黑盒全量重跑
- `incremental_append`  #在当前正式结果基础上追加、去重、导出。
- `override_only`  #按 patch 改现有正式结果，然后重建正式输出。


## 4. 输入规则

### 4.1 身份层

每次运行都必须指定 `source-type`，表示本次输入数据的身份。

- `raw_source`
  - 官方更新源数据
- `external_source`
  - 普通外部补充
  - 只能追加、补充、参与候选比较
- `manual_override`
  - 人工裁定后的精准修改指令
  - 用于明确修订哪些字段、哪些记录

### 4.2 模板层（模板示例见附录B）

系统规定模板，输入者必须尽量对齐模板。

（1）`raw_source` 原始模板：

- 只接受官方原始格式

（2）`external_source` 标准补充模板字段规则如下：

 基础必填规则：

  - parameter_name 非空
  - value 非空
  - uniprot / sequence 至少 1 个非空
  - substrate / smiles 至少 1 个非空
  - 只是想改现有记录，那不该走 external_source，应该走 manual_override
  

  可补充的条件与测量字段：

  - `enzyme_type`
  - `mutation`
  - `unit`
  - `ph`
  - `temperature`
  - `value_normalized`
  - `unit_normalized`
  - `enzyme_type`、`mutation` 不是门槛字段，但如果提供，就参与 business_key

  - 若未单独提供 `ph` 或 `temperature`，且该行 `parameter_name` 就是 `ph` 或 `temperature`，则允许由 `value` 回填到对应条件字段
  - 若未提供 `value_normalized`，允许先回填自 `value`
  - 若未提供 `unit_normalized`，允许先回填自 `unit`

  可补充的来源追踪字段：

  - `source_record_id`
  - `source_db`
  - `source_release`
  - 缺失时由系统自动补齐，不要求输入者手动提供
  - `source_record_id` 缺失时，按 `<source_file_stem>:<row_number>` 生成
  - `source_db` 缺失时，默认写入本次来源类型
  - `source_release` 缺失时，默认写入本次 `release_id`

  可补充的附加保留字段：

  - `ec_number`
  - `organism`
  - `commentary`
  - `ions`
  - `sequence_source`
  - `parse_status`
  - 这些字段允许提供，但不作为 `external_source` 正式去重主键


  `manual_override` patch 指令模板字段：

  `manual_override` 只接受 patch 指令模板，不接受普通补充记录表。

  固定列分为三类：

  1. 基础必填列：

  - `operation_id`：patch 指令唯一编号。
  - `target_table`：目标表名，通常是 `master`、`merged` 或 `conditions`。
  - `target_scope`：作用范围，表示改动落在当前工作区、正式结果或历史修复中的哪一层。
  - `match_key_type`：定位目标记录所用的键类型，例如 `record_id`、`business_key`、`record_key`。
  - `field_name`：要修改的字段名。
  - `action`：执行动作，例如 `replace`、`fill_if_blank`、`clear`、`drop_row`。
  - `reason`：本次 patch 的业务原因或修正理由。
  - `approved_by`：审批人或提交人。
  - `approved_at`：审批时间。

  2. 匹配定位列：

  - `record_id`：正式单行 ID，优先用于精确命中。
  - `record_key`：工作区临时定位键，主要用于当前 release 内的 patch。
  - `uniprot`：蛋白条目标识字段。
  - `enzyme_type`：酶类型字段，区分 wildtype、mutant 等语义。
  - `mutation`：突变信息字段。
  - `sequence`：蛋白序列字段。
  - `substrate`：底物名称字段。
  - `smiles`：底物或分子结构的 SMILES 字段。

  3. 取值相关列：

  - `old_value_expected`：期望旧值，只有目标字段当前值匹配时才允许修改。
  - `new_value`：要写入的新值；`clear` 时应为空，`drop_row` 时固定写 `drop_row`。

  允许的可选辅助列：

  - `target_release_id`
    - 说明这条 patch 预期作用于哪个版本结果
  - `priority`
    - 多条 patch 冲突时的执行顺序
  - `review_comment`
    - 人工备注
  - `evidence_source`
    - 这次修正依据来自哪里
  - `expected_context`
    - 用来写目标记录的辅助上下文说明

  `match_key_type` 只允许以下三种取值：

  - `record_id`  
    - 可能由用户提供，但只能“引用已有正式结果里的值”，不能自己发明。典型场景是manual_override：想精确改一条正式结果记录，就可以在 patch 里写现成的 record_id。
  - `business_key`
  - `record_key`



### 4.3 入口层

三类输入必须进入各自入口目录，不允许混放：

- `.external_data/incoming/<batch_id>/raw/`
- `.external_data/incoming/<batch_id>/external/`
- `.external_data/incoming/<batch_id>/manual_override/`

### 4.4 别名映射

系统允许有限别名映射，但不应长期依赖别名识别作为主要输入方式。

当前建议映射：

- `enzyme_id -> uniprot`
- `species -> organism`
- `wildtype_mutant -> enzyme_type`
- `raw_value -> value`
- `raw_unit -> unit`

### 4.5 输入总原则

- `raw_source` 不允许用户自行改列名后再当原始源输入
- `external_source` 输入者必须按统一模板整理
- `manual_override` 只接受 patch 指令模板
- 不允许把普通补充表放进 `manual_override/`
- 不允许把 `manual_override` 放进 `external/`

## 5. 三类更新模式规则

### 5.1 `raw_source`

定位：

- 官方原始更新源数据

典型输入：

- 新的 BRENDA 原始文件
- 新的 SABIO 原始文件

运行方式：

- 走全量重建链路
- 调用旧的 14 步流程脚本

### 5.2 `external_source`

定位：

- 普通外部补充数据

典型输入：

- 整理后的 Excel
- CSV
- JSON
- TSV

运行方式：

- 走增量标准化、去重、条件表导出、结果更新链路

### 5.3 `manual_override`

定位：

- 人工审批后的精准修正指令
- 不是普通补充记录表，而是 patch 指令表

运行方式：

- 走独立的 override patch 链路

## 6. CLI 与运行入口规则

当前命令行入口支持三个命令：

- `plan`
- `validate`
- `run`

### 6.1 `plan`

作用：

- 预演本次运行计划
- 让操作者知道本次会读什么、写什么、走哪条链路

特点：

- 不写正式输出
- 不切换 `current`

### 6.2 `validate`

作用：

- 检查输入格式、模板字段、关键列、空值、数据类型、主键字段是否可识别

特点：

- 不写正式输出
- 不切换 `current`

### 6.3 `run`

作用：

- 正式执行更新流程

强规则：

- `run` 内部默认必须先自动执行基础 `plan` 和基础 `validate`
- 如果 `validate` 失败，则本次 `run` 必须终止

### 6.4 使用方式

简单场景：

- 可直接 `run`

保险场景：

- 先 `validate` 再 `run`

排查场景：

- `plan -> validate -> run`

## 7. 数据与目录结构规则

### 7.1 总体结构

所有运行数据统一放在：

- `.external_data/`

  .external_data/                                      # 仓库外的大数据工作区根目录
  |- incoming/                                         # 每次新上传数据的入口区
  |  `- <batch_id>/                                    # 一次上传批次目录，例如20260726_ext_batch_001
  |     |- raw/                                        # 官方原始更新输入，只放 raw_source 输入文件
  |     |- external/                                   # 普通外部补充输入，只放 external_source 输入文件
  |     `- manual_override/                            # 人工修正规则输入，只放 manual_override patch 指令文件
  |
  |- database/                                         # 系统长期使用的数据库资产区
  |  |- original/                                      # 长期保留的原始官方数据和初始基线原始文件
  |  |  |- brenda/                                     # BRENDA 原始文件
  |  |  |- sabio/                                      # SABIO 原始文件
  |  |  |- skid/                                       # SKiD 原始文件
  |  |  |- intenzy/                                    # IntEnzy 原始文件
  |  |  `- catapro_reference/                          # 初始版 CataPro 原始参考包或基线原始资料
  |  |
  |  |- reference/                                     # 流程运行依赖的稳定参考表，不是最终输出
  |  |  |- catapro/                                    # CataPro 参考表
  |  |  |- dlkcat/                                     # DLKcat 参考表
  |  |  |- intenzy/                                    # IntEnzy 参考表
  |  |  |- ligands/                                    # 底物/配体参考表
  |  |  |- skid/                                       # SKiD 参考表
  |  |  `- uniprot/                                    # UniProt 序列/映射参考表
  |  |
  |  |- current/                                       # 当前正式生效的一整套结果
  |  |  |- master/                                     # 当前有效 master 表
  |  |  |- merged/                                     # 当前有效 merged 表
  |  |  |- summary/                                    # 当前有效 summary 结果
  |  |  `- conditions/                                 # 当前有效条件表，如 ph / temperature
  |  |
  |  `- history/                                       # 历史区，只放历史资产
  |     |- snapshots/                                  # 每次更新前或回滚前的整套快照
  |     |  `- <release_id>-before/                     # 某次 release 开始前保存的旧版本快照
  |     |     |- master/                               # 更新前的 master 快照
  |     |     |- merged/                               # 更新前的 merged 快照
  |     |     |- summary/                              # 更新前的 summary 快照
  |     |     `- conditions/                           # 更新前的条件表快照
  |     |
  |     |- history_logs/                               # 逐条变化日志，不是整表快照
  |     |  |- conditions/                              # ph / temperature 等条件表的追加、修改、删除日志
  |     |  |- master/                                  # master 表逐条变化日志
  |     |  `- merged/                                  # merged 表逐条变化日志
  |     |
  |     `- audits/                                     # 历史审计区
  |        |- current_switch_audit.csv                 # current 切换记录
  |        |- rollback_actions.csv                     # 回滚动作记录
  |        |- conflict_audit.csv                       # 冲突处理审计
  |        |- rejected_rows_audit.csv                  # 被拒收/逻辑删除记录审计
  |        `- diff_summary_audit.csv                   # 版本差异摘要审计
  |
  `- releases/                                         # 每次运行的完整版本档案区
     `- <release_id>/                                  # 一次正式运行对应一个 release
        |- manifest/                                   # 本次运行的说明清单
        |  |- release_manifest.json                    # release 总说明：版本号、类型、状态、操作者等
        |  |- input_manifest.json                      # 输入清单：本次读取了哪些输入和参考表
        |  |- output_manifest.json                     # 输出清单：本次生成了哪些正式结果
        |  |- file_inventory.csv                       # 本次 release 下关键文件总目录
        |  |- plan_preview.json                        # plan 结果：会怎么跑
        |  |- plan_preview.txt                         # plan 摘要
        |  |- validate_report.json                     # validate 检查结果
        |  |- validate_report.txt                      # validate 检查结果
        |  |- run_summary.txt                          # run 后的总结
        |  |- dedup_batch_manifest.json                # artifact manifest。只在 external_source 跑去重时生成,记录这次 dedup 批次处理了多少行、重复多少、冲突多少、leakage 去掉多少
        │  |- ph_long_table_manifest.json              # artifact manifest。只要这次 run 触发了正式 conditions 导出，就会生成,记录 ph_long_table.csv 的输入、输出、行数、列数
        │  `─ temperature_long_table_manifest.json     # 同上
        |
        |- logs/                                       # 运行日志
        |  `- raw_source/                              # raw_source 黑盒逐脚本日志目录，当前实现写入 01_*.log ~ 23_*.log
        |
        |- audits/                                     # 本次 release 内部审计文件
        |  |- import_duplicate_rows.csv                # 导入级完全重复行审计
        |  |- business_duplicate_rows.csv              # 业务级去重审计
        |  |- test_leakage_removed.csv                 # test 泄漏过滤移除记录
        |  |- rejected_rows.csv                        # 本次拒收记录
        |  |- conflicts.csv                            # 本次冲突记录
        |  |- validation_issues.csv                    # 校验问题明细
        |  |- override_applied.csv                     # manual_override 成功应用记录
        |  |- override_skipped.csv                     # manual_override 跳过记录
        |  |- override_conflicts.csv                   # manual_override 冲突记录

        |- outputs/                                    # 本次正式输出结果
        |  |- master/                                  # 本次输出的 master 表
        |  |- merged/                                  # 本次输出的 merged 表
        |  |- summary/                                 # 本次输出的 summary 表
        │  │  |─ summary_v6.txt
        │  │  |─ summary_v6_counts.csv
        │  │  |─ mutation/
        │  │  |─ ph_tem_empty/
        │  │  `─ unit/
        |  `- conditions/                              # 本次输出的条件表，如 ph_long_table.csv 、temperature_long_table.csv
        `- workspace/                                  # 本次运行过程文件工作区
           |- raw_source/                              # raw_source 全量链路过程文件
           |  `- database_update_pipeline/             # 黑盒工作区副本根目录
           |     |- 01_new_raw/                        # 第 1 步原始数据整理过程文件
           |     |  |- input/                          # 第 1 步输入文件
           |     |  |- output/                         # 第 1 步输出文件
           |     |- 02_enrich+mutation/                # 第 2 步 enrich / mutation 过程文件
           |     |- 03_subres/                         # 第 3 步 substrate / residue 处理过程文件
           |     |- 04_QC/                             # 第 4 步质量控制过程文件
           |     |- 05_qc_standardize/                 # 第 5 步标准化过程文件
           |     |- 06_backfill_seq/                   # 第 6 步序列回填过程文件
           |     |- 07_cata_updata/                    # 第 7 步 Cata 更新过程文件
           |     |- 08_cata_master/                    # 第 8 步 master 生成过程文件
           |     |- 09_external_master/                # 第 9 步 external master 合并过程文件
           |     |- 10_mut_status_repair/              # 第 10 步突变状态修复过程文件
           |     |- 11_merged_canonical_pool/          # 第 11 步 merged canonical pool 过程文件
           |     |- 12_status_fix/                     # 第 12 步状态修复过程文件
           |     |- 13_final_data/                     # 第 13 步最终数据过程文件
           |     `- 14_final_docs/                     # 第 14 步文档/汇总/审计过程文件
           |
           |- external_source/                         # external_source 增量链路过程文件
           |  |- standardized_inputs/                  # 标准化后的输入中间表
           |  |- dedup/                                # 去重过程文件
           |  |- conditions/                           # ph / temperature 条件表构建过程文件
           |  |- reports/                              # 中间检查报告、对账报告
           `- manual_override/                         # manual_override 独立 patch 链路过程文件
             |- standardized_instructions/            # 标准化后的 patch 指令表
             |- matched_targets/                      # 目标记录匹配结果，包含命中、未命中、歧义匹配
             |- applied_changes/                      # patch 应用后的中间结果和逻辑移除结果
             `- reports/                              # patch 执行摘要、冲突说明、人工复核报告

### 7.2 顶层目录职责

- `incoming/`
  - 用户本次上传的新数据入口区
- `database/original/`
  - 长期保留官方原始源文件和原始基线文件
- `database/reference/`
  - 流程运行依赖的参考表
- `database/current/`
  - 当前正式生效的一整套结果
- `database/history/`
  - 历史快照、逐条变化日志、冲突和切换审计
- `releases/`
  - 每次运行的完整版本档案

### 7.3 `database/reference/` 规则

`database/reference/` 放的是流程反复读取的依赖文件。

规则：

- 不是最终结果表
- 不是本次新上传数据
- 不是官方原始更新快照
- 是流程每次运行都可能依赖的稳定参考文件

当前已确认参考文件包括：

- `kcat-data_0.4simi-10fold.csv`
- `Km-data_0.4simi-10fold.csv`
- `kcat-over-Km-data_0.4simi-10fold.csv`
- `Kcat_combination_0918_wildtype_mutant.json`
- `Ligands_all_final_v1.csv`
- `db_matched_pairs_pH.csv`
- `kcat_all_data_logscale_final_v1.csv`
- `Km_all_data_logscale_final_v1.csv`
- `uniprot_sequence_cache_v1.csv`

### 7.4 `database/current/` 规则

结构：

```text
database/current/
|- master/
|- merged/
|- summary/
`- conditions/
```

含义：

- `master/`
  - 当前正式生效的 master 表
- `merged/`
  - 当前正式生效的 merged 表
- `summary/`
  - 当前正式生效的汇总结果
- `conditions/`
  - 当前正式生效的条件表，例如 `ph.csv`、`temperature.csv`

### 7.5 `database/history/` 规则

结构：

```text
database/history/
|- snapshots/
|- history_logs/
|  |- conditions/
|  |- master/
|  `- merged/
`- audits/
```

- `snapshots`
  - 版本级历史
  - 回答“更新前整套旧版本长什么样”
- `history_logs`
  - 记录级历史
  - 回答“某条记录是怎么一路变化到今天的”
- `audits`
  - 审计说明
  - 回答“为什么切换、拒收、冲突、回滚”

### 7.6 `releases/<release_id>/` 规则

每次运行都必须在：

- `releases/<release_id>/`

下生成完整档案。

固定结构：

```text
releases/<release_id>/
|- manifest/
|- logs/
|- audits/
|- outputs/
|  |- master/
|  |- merged/
|  |- summary/
|  `- conditions/
`- workspace/
   |- raw_source/
   |- external_source/
   `- manual_override/
```

s

## 8. 运行前规则

### 8.1 支持格式

当前支持：

- Excel
- CSV
- JSON
- TSV

按 `source-type` 的校验入口约束如下：

- `raw_source`
  - 文件输入只接受官方原始格式
  - 当前固定为：
    - BRENDA `json`
    - SABIO `tsv`
  - 目录输入也允许，但目录内文件仍必须满足上述规则
- `external_source`
  - 接受：
    - `xlsx`
    - `xls`
    - `csv`
    - `json`
    - `tsv`
- `manual_override`
  - 接受：
    - `csv`
    - `json`
    - `xlsx`

补充规则：

- `validate` 不根据文件内容自动推断 `source-type`
- `source-type` 必须由操作者显式声明
- 系统只在已声明的 `source-type` 下执行对应校验和链路分派

### 8.2 `validate` 检查内容

`validate` 是正式阻断步骤。每次 `run` 前都必须执行同一套硬规则。

固定检查项如下：

1. 文件级检查
   - 输入文件数量必须 `>= 1`
   - 所有输入文件必须可读取
   - 所有输入文件扩展名必须在本规范允许集合内
2. 模板级检查
   - 当前 `source-type` 对应的必备列必须 `100%` 存在
   - 同一输入表内不允许多个列映射到同一标准字段
   - `manual_override` 不允许混入普通补充记录模板
3. 标准化级检查
   - `external_source` 标准化成功率必须 `>= 90%`
   - `external_source` 若标准化成功率 `>= 90%` 且 `< 95%`，判定为 `pass_with_warning`
   - `external_source` 若标准化成功率 `< 90%`，判定为 `fail`
   - `manual_override` 指令有效率必须 `100%`
4. 业务键级检查
   - `external_source` 的每一条记录都必须满足以下行级规则：
     - `parameter_name` 非空
     - `value` 非空
     - `uniprot` / `sequence` 至少 1 个非空
     - `substrate` / `smiles` 至少 1 个非空
   - 任意一条记录不满足上述规则，均判定为 `fail`
5. 条件字段检查
   - 若输入中声明了 `ph` / `temperature` / `value` / `unit` 等条件相关列，则必须可解析为统一字段
   - 条件列存在但整列完全不可解析时，判定为 `fail`
6. 空列检查
   - 任一必备列若整列为空，判定为 `fail`
   - 任一非必备列若整列为空，判定为 `pass_with_warning`
7. 类型与内容检查
   - `manual_override.approved_at` 必须能解析为时间
   - `manual_override.action` 必须在允许枚举中
   - `manual_override.match_key_type` 必须在允许枚举中
   - `record_id` 若提供，则必须匹配 `^frid_[0-9a-f]{20}$`
   - `measurement_uid` 若提供，则必须匹配 `^muid_[0-9a-f]{20}$`

### 8.3 `validate` 状态

只允许三种状态：

- `pass`
- `pass_with_warning`
- `fail`

含义：

- `pass`
  - 可以直接运行
- `pass_with_warning`
  - 可以运行，但必须提示风险
- `fail`
  - 不允许继续正式运行

### 8.4 阻断错误与警告

以下情况必须判定为 `fail`：

- 文件数量为 `0`
- 任一输入文件无法读取
- 文件格式与 `source-type` 入口不匹配
- 必备字段缺失
- 同一输入表多个列映射到同一标准字段且无法唯一裁定
- 关键业务键字段无法识别
- `external_source` 标准化成功率 `< 90%`
- `external_source` 任一记录 `parameter_name` 为空
- `external_source` 任一记录 `value` 为空
- `external_source` 任一记录同时缺少 `uniprot` 和 `sequence`
- `external_source` 任一记录同时缺少 `substrate` 和 `smiles`
- `manual_override` 任一指令缺少目标匹配信息
- `manual_override` 任一指令缺少 `action`
- `manual_override` 任一指令 `approved_by` 或 `approved_at` 缺失
- `manual_override` 任一 `match_key_type == record_id` ，但指令缺少 `record_id`
- `manual_override` 任一 `match_key_type == record_id` ，但指令的 `record_id` 格式不合法
- `manual_override` 任一 `match_key_type == record_key` ，但指令的 `target_scope != workspace`   #record_key 是工作区临时键，只允许在本次 release 的 workspace 里定位，不允许拿它去打正式 current 结果层。
- `manual_override` 任一 `match_key_type == record_id` 或 `business_key` 的指令命中目标记录 `> 1` 且仍声明为精准单记录 patch
- 所有记录均无法标准化

以下情况必须判定为 `pass_with_warning`：

- 存在未使用的非关键列
- 可选字段缺失
- `external_source` 标准化成功率 `>= 90%` 且 `< 95%`
- 某些记录字段值异常但不影响整体读取
- 非必备列整列为空

### 8.5 运行前快照规则

每次正式更新必须先执行：

1. 生成新的 `release_id`
2. 将当前 `database/current/` 复制到 `database/history/snapshots/<release_id>-before/`
3. 然后再开始本次更新

快照命名规则：

- `database/history/snapshots/<release_id>-before/`

例如：

- `20260730-ext001-before`

含义：

- 为 `20260730-ext001` 这次更新保存的更新前旧版本快照

### 8.6 运行前产物规则

`plan` 和 `validate` 的正式产物属于 `manifest/` 一部分。

每次 `run` 必须固定生成：

- `plan_preview.json`
- `plan_preview.txt`
- `validate_report.json`
- `validate_report.txt`

四个文件的详细示例见附录 A。

## 9. 三类运行链路规则

每次运行都必须指定 `source-type`，表示本次输入数据的身份。

### 9.1 `raw_source` 链路

#### 9.1 1. `raw_source` 输入和运行规则

输入位置：

- `.external_data/incoming/<batch_id>/raw/...`

典型输入：

- 新的 BRENDA 原始文件
- 新的 SABIO 原始文件

运行方式：

- 走全量 14 步重建链路
- 调用 14 步黑盒流程脚本

结果写入规则：

- 过程文件放：
  - `releases/<release_id>/workspace/raw_source/database_update_pipeline/`
- 正式结果放：
  - `releases/<release_id>/outputs/`
- 审计文件放：
  - `releases/<release_id>/audits/`
- 日志放：
  - `releases/<release_id>/logs/`
- 说明文件放：
  - `releases/<release_id>/manifest/`

过程目录：

- `01_new_raw/`
- `02_enrich+mutation/`
- `03_subres/`
- `04_QC/`
- `05_qc_standardize/`
- `06_backfill_seq/`
- `07_cata_updata/`
- `08_cata_master/`
- `09_external_master/`
- `10_mut_status_repair/`
- `11_merged_canonical_pool/`
- `12_status_fix/`
- `13_final_data/`
- `14_final_docs/`


#### 9.1.2 黑盒 14 步阶段契约

`raw_source` 的正式全量重建以 14 步链路为准。

固定阶段如下：

1. `01_new_raw`
   - 重建 BRENDA / SABIO 原始整理表
2. `02_enrich+mutation`
   - 补全本地序列、SMILES，并重建突变体相关字段
3. `03_subres`
   - 处理 SABIO 底物组成与残基拆分
4. `04_QC`
   - 执行原始层 QC 过滤
5. `05_qc_standardize`
   - 对 QC 保留记录做正式标准化
6. `06_backfill_seq`
   - 使用本地与 UniProt 参考补全序列
7. `07_cata_updata`
   - 导出 CataPro 更新表
8. `08_cata_master`
   - 生成 CataPro master 表
9. `09_external_master`
   - 将 DLKcat、SKiD、IntEnzy 统一到共享 master schema
10. `10_mut_status_repair`
    - 修复 mutation status 字段
11. `11_merged_canonical_pool`
    - 合并候选训练池、去重并去除 test 泄漏
12. `12_status_fix`
    - 修复最终状态字段
13. `13_final_data`
    - 导出最终 enriched 数据和条件数据
14. `14_final_docs`
   - 导出 `conditions`、`summary`、`drop`


补充规则：

- 新软件对 `raw_source` 来源数据的职责是编排、版本化、归档和审计
- 旧链路内部脚本仍决定各阶段具体数据加工细节
- 进入 `releases/<release_id>/outputs/` 的正式结果必须与旧版正式结果口径一致
- catapro_delivery\database_update_pipeline被定义为`raw_source` 来源数据永久复用 14 步黑盒
- 新软件不得重写、替换或重新解释黑盒内部数据处理逻辑
- 新软件允许做的事情只有：
  - 组织输入目录
  - 调用黑盒流程脚本
  - 收集工作区产物
  - 校验正式输出
  - 生成版本、审计、回滚记录
- 若后续需要改变 `raw_source` 内部处理逻辑，必须视为“旧链路版本升级”，先修订本规范，再升级旧脚本；不能在新软件层静默改写

##### 9.1.2.1 Step 05 `05_qc_standardize` 保留规则

该步是旧链路中正式标准化的固定节点，必须保留以下语义：

- 输入为 QC 通过后的 BRENDA / SABIO 表
- 输出为标准化后的原始层表
- 负责产出进入后续共享 schema 所需的标准化字段
- 后续正式结果层 `record_id` 必须以显式字段重算结果为准
- 负责标准化：
  - `parameter_name`
  - `value`
  - `unit`
  - `uniprot`
  - `smiles`
  - 序列相关字段
- 负责准备：
  - `sequence_final`
  - `sequence_final_source`
- 该步不新增额外 QC
- 该步不改变已保留行集合，只重组字段和取值表达

##### 9.1.2.2 Step 09 `09_external_master` 保留规则

该步是旧链路中外部来源统一进入共享 master schema 的固定节点，必须保留以下语义：

- `9A_ex_master`
  - 构建：
    - `DLKcat` master
    - `SKiD` master
    - `IntEnzy` master
  - 将 `IntEnzy` pair 数据 reshape 为 long-form master 表
- `9B_SKID_seqfill`
  - 仅针对 SKiD 做序列补全
  - 使用 UniProt cache 回填序列
  - 尝试构造 mutant sequence

硬规则：

- Step 09 产物必须进入共享 master schema
- `9B_SKID_seqfill` 的目标是提高 SKiD 序列完整度
- `9B_SKID_seqfill` 不应改变 SKiD 表行数
- Step 09 修复的是 SKiD 温度解析和序列完整性问题，不是随意补造条件值

##### 9.1.2.3 Step 11 `11_merged_canonical_pool` 保留规则

该步是旧链路中训练池合并和正式去重的固定节点，必须保留以下语义：

- `candidate_pool`
  - 合并：
    - `CataPro`
    - `DLKcat`
    - `SKiD`
- `dedup-split`
  - 去除重复训练键
  - 去除与 `IntEnzy` test 集重叠的记录
  - 保留 `IntEnzy` test 输出

硬规则：

- `IntEnzy` 在该步按外部 test 集处理，不作为训练数据
- `merge_kcat_final_*` 与 `merge_km_final_*` 必须完成训练侧去重
- 与 `IntEnzy` test 业务键重叠的训练记录必须移除并进入审计

##### 9.1.2.4 Step 14 `14_final_docs` 保留规则

Step 14 的三个子输出必须继续保留，但语义要按新规范归位：

- `14A conditions`
  - 只生成旧链路条件配对辅助视图
  - 输出路径为：
    - `releases/<release_id>/workspace/raw_source/database_update_pipeline/14_final_docs/conditions/output/conditions/`
  - 固定三类视图：
    - `grouped_outerjoin`
    - `collapsed_multivalue`
    - `cartesian`
  - 这些视图只用于分析、审计、比对和报告
  - 不能替代正式 `ph_long_table.csv` / `temperature_long_table.csv`
- `13_final_data`
  - 在生成最终 `merge_kcat_final_v6_enriched.csv` / `merge_km_final_v6_enriched.csv` 的同时
  - 对应脚本为 `13_final_data/script/export_masters_merges_enriched_v6.py`
  - 必须同步生成正式条件长表：
    - `13_final_data/output/conditions/ph_long_table.csv`
    - `13_final_data/output/conditions/temperature_long_table.csv`
  - 这两张表还会同步进入正式 `outputs/conditions/`
- `14B summary`
  - 负责导出：
    - 总体规模统计
  - `mutation/*`
  - `ph_tem_empty/*`
  - `unit/*`
  - `mutation/*`
    - 定义为 `mutation` 非空记录
  - `ph_tem_empty/*`
    - 定义为 `ph` 与 `temperature` 同时为空的记录
  - `unit/*`
    - 定义为：
      - `missing_unit`
      - 或单位非空但不在预期集合内
  - 预期单位固定为：
    - `kcat -> s^-1`
    - `km -> mM` 或 `M`
    - `kcat_km -> M^-1*s^-1`
  - BRENDA 单位空白允许作为来源性空白存在，但必须进入审计，不允许硬填伪值
- `14C drop`
  - 负责发布被移除记录清单
  - 包括：
    - `raw_qc` 移除
    - `final_dedup` 移除
  - 对应脚本为 `14_final_docs/drop/script/build_dropped_v6.py`
  - 该步只做文档化和审计化，不回写上游数据
- `14A conditions`
  - 对应脚本为 `14_final_docs/conditions/script/build_conditions_v6.py`
  - 只生成辅助配对视图，不替代正式条件长表


### 9.2 `external_source` 链路

#### 9.2.1 输入与运行规则

输入位置：

- `.external_data/incoming/<batch_id>/external/...`

典型输入：

- 整理后的 Excel
- CSV
- JSON
- TSV

运行方式：

- 走增量标准化
- 去重
- 条件表导出
- 更新结果集

结果写入规则：

- 过程文件放：
  - `releases/<release_id>/workspace/external_source/`
- 正式结果放：
  - `releases/<release_id>/outputs/`
- 审计文件放：
  - `releases/<release_id>/audits/`
- 日志放：
  - `releases/<release_id>/logs/`
- 说明文件放：
  - `releases/<release_id>/manifest/`

工作区：

- `standardized_inputs/`
  - 标准化后的输入中间表
- `dedup/`
  - 导入级去重、业务级去重、test 泄漏过滤过程文件
- `conditions/`
  - `ph`、`temperature` 条件表构建过程文件
- `reports/`
  - 中间检查报告、对账报告、规模变化报告

补充规则：

- `external_source` 不能直接写 `current`
- 必须先写到 `releases/<release_id>/outputs/`

#### 9.2.2 `external_source` 的正式输出完成判定规则

  `external_source` 可以有独立的中间处理流程，但不能停留在中间结果层。

  正式规则如下：

  1. `external_source` 的中间过程允许生成：
     - `workspace/external_source/standardized_inputs/`
     - `workspace/external_source/dedup/`
     - `workspace/external_source/conditions/`
     - `workspace/external_source/reports/`

  2. 但一次 `external_source` 正式运行只有在以下正式结果全部生成后，才可视
  为“正式完成”：
     - `outputs/master/`
     - `outputs/merged/`
     - `outputs/summary/`
     - `outputs/conditions/`

  3. 上述四类正式输出必须满足：
     - 字段结构与旧版正式结果一致
     - 字段顺序与旧版正式结果一致
     - 字段语义与旧版正式结果一致
     - 不允许把中间过程字段直接混入正式输出

  4. `external_source` 的标准化、去重、条件导出只是前置处理，不等于正式完
  成。

  5. 如果本次运行只生成了中间结果，而未生成完整正式输出，则本次状态只能记
  为：
     - `intermediate_only_completed`
     - 或 `partially_completed`

  6. 在未生成完整正式输出前：
     - 不允许切换 `current`
     - 不允许把中间结果当作正式结果对外使用

  7. `run_summary` 和 `output_manifest` 必须明确写明：
     - 是否完成正式输出
     - 缺失了哪一类正式结果
     - 当前是否允许进入 `current` 切换

### 9.3 `manual_override` 链路

#### 9.3.1 输入与运行规则

输入位置：

- `.external_data/incoming/<batch_id>/manual_override/...`

典型输入：

- 按照模板整理的CSV 或 Excel
- 一行代表一次修改指令的 patch 指令表

运行方式：

- 走独立的 override patch 链路

过程文件放：

- `releases/<release_id>/workspace/manual_override/`

建议工作区：

- `standardized_instructions/`
  - 标准化后的 patch 指令表
- `matched_targets/`
  - 目标记录匹配结果，包括命中、未命中、歧义匹配
- `applied_changes/`
  - patch 应用后的中间结果和逻辑移除结果
- `reports/`
  - patch 执行摘要、冲突说明、人工复核报告

正式结果放：

- `releases/<release_id>/outputs/`

执行原则：

- 每条指令必须指向明确目标记录
- 每条指令必须指向明确字段
- 每条指令必须说明原因
- 每条指令必须留下审计记录
- 不允许无目标、无理由的大范围覆盖

匹配优先级：

1. 优先使用 `record_id`
2. 其次使用 `business_key`
3. 最后使用 `record_key`

#### 9.3.2 `manual_override` 的正式输出完成判定规则

  `manual_override` 可以有独立的中间处理流程，但不能停留在中间结果层。

  正式规则如下：

  1. `manual_override` 的中间过程允许生成：
     - `workspace/manual_override/standardized_instructions/`

  匹配规则如下：

  1. 如果 `match_key_type == record_id`
     - `record_id` 必填
     - 必须唯一命中 1 条正式结果层记录
     - 命中 `0` 条：记入 `override_skipped.csv`
     - 命中 `>1` 条：记入 `override_conflicts.csv`
     - 只有唯一命中时才允许应用 patch

  2. 如果 `match_key_type == business_key`
     - 以下 6 个字段必须存在并按正式数据一致的规则先完成标准化：
       - `uniprot`
       - `enzyme_type`
       - `mutation`
       - `sequence`
       - `substrate`
       - `smiles`
     - `uniprot`、`sequence`、`substrate`、`smiles` 四个字段不得同时为空
     - 匹配时不得直接信任输入表或结果表中已有缓存键列
     - patch 侧一定会重算 canonical business_key
     - 目标侧如果已有 business_key 列，就直接用；没有才现算
     - 命中 `0` 条：记入 `override_skipped.csv`
     - 命中 `1` 条：允许应用 patch
     - 命中 `>1` 条：记入 `override_conflicts.csv`
     - `business_key` 匹配是次级匹配，不等于天然精准单行匹配
     - `record_key` 可空

  3. 如果 `match_key_type == record_key`
     - `record_key` 必填
     - 只允许用于当前 release 内部工作区或中间结果定位
     - 不允许用于 `current` 正式结果层
     - 不允许用于历史 release 正式结果层
     - 不允许作为长期修正规则的唯一稳定匹配方式
     - 若 `target_scope != workspace` 且 `match_key_type == record_key`，`validate` 必须判定为 `fail`

  `action` 只允许以下四种取值：

  - `replace`
  - `fill_if_blank`
  - `clear`
  - `drop_row`

  各 `action` 的字段约束如下：

  1. `replace`
     - `field_name` 必填
     - `new_value` 必填
     - `old_value_expected` 可填可不填
     - 如果填写了 `old_value_expected`，则必须先与旧值匹配成功才允许修改

  2. `fill_if_blank`
     - `field_name` 必填
     - `new_value` 必填
     - 只有旧值为空时才允许写入
     - `old_value_expected` 应保持为空

  3. `clear`
     - `field_name` 必填
     - `new_value` 必须为空字符串
     - 必须提供 `reason`

  4. `drop_row`
     - `field_name` 固定写为 `record_status`
     - `new_value` 固定写为 `drop_row`
     - 不物理删除原始数据
     - 只在正式结果层将该记录逻辑移除
     - 必须写入审计和历史日志

  以下情况 `validate` 必须判定为 `fail`：

  - 缺少基础必填列
  - `match_key_type` 不合法
  - `action` 不合法
  - `business_key` 模式下 `uniprot`、`sequence`、`substrate`、`smiles` 同时为空
  - `record_id` 模式下 `record_id` 缺失
  - `record_key` 模式下 `record_key` 缺失
  - `clear` 动作下 `new_value` 非空
  - `drop_row` 动作下 `field_name` 或 `new_value` 不符合固定规则
  - `approved_by` 或 `approved_at` 缺失

  模板总原则：

  - `manual_override` 只用于精准修正
  - 不允许无目标、无字段、无理由的大范围覆盖
  - 不允许把普通外部补充表伪装成`manual_override`

边界规则：

- 命中目标记录后，其结果可以优先于 `external_source`
- 不允许直接改写 `database/original/`
- 不允许静默修改历史原始文件
- 默认作用于：
  - `current`
  - 或本次 `release_output`

输出规则：

- `override_applied.csv`
  - 放在 `releases/<release_id>/audits/`
- `override_skipped.csv`
  - 放在 `releases/<release_id>/audits/`
- `override_conflicts.csv`
  - 放在 `releases/<release_id>/audits/`
- `override_manifest.json`
  - 放在 `releases/<release_id>/manifest/`

 `manual_override` 不是只产出 patch 审计结果的链路。

  正式规则如下：

  1. `manual_override` 先执行：
     - patch 指令标准化
     - 目标记录匹配
     - patch 应用
     - 冲突记录生成
     - 跳过记录生成

  2. 但 patch 应用完成后，必须继续执行正式结果重建。

  3. 正式结果重建至少包括：
     - 更新后的 `outputs/master/`
     - 更新后的 `outputs/merged/`
     - 更新后的 `outputs/summary/`
     - 更新后的 `outputs/conditions/`

  4. 这四类正式结果必须与旧版正式结果保持一致：
     - 字段结构一致
     - 字段顺序一致
     - 字段语义一致

  5. `manual_override` 不允许只修改：
     - `current/conditions/`
     - 或单个正式表文件
     而不重建其余正式结果层。

  6. `manual_override` 的成功不等于“某条 patch 已命中”，而等于：
     - patch 已成功应用
     - 正式结果已完整重建
     - 审计文件已生成
     - 可以进入审核流程

  7. 如果 patch 已应用，但正式结果未完整重建，则本次状态只能记为：
     - `patch_applied_but_release_not_finalized`

  8. 在这种状态下：
     - 不允许切换 `current`
     - 不允许把 patch 后的局部结果视为正式发布结果


## 10. 数据处理规则

### 10.1 标准化规则

外部补充输入在进入去重前，必须先完成标准化。

标准化总目标：

- 统一字段名
- 统一字段语义
- 统一空值表示
- 统一单位字段承载方式
- 统一业务键字段格式

原则：

- 标准化语义应尽量与旧链路一致
- 不允许发明与旧链路不兼容的新核心 schema
- 原始源链路可以保留自身中间格式
- 但进入统一结果层时，必须映射到同一套结果语义

#### 10.1.1 `raw_source` 的标准化规则

- 在黑盒全量 14 步链路内部完成 QC、字段修复、标准化、合并
- 输入阶段允许保持官方原始格式
- 中间步骤允许存在旧链路特有字段和目录结构
- 但当记录进入以下层级时，必须完成统一结果层映射：
  - `releases/<release_id>/outputs/master/`
  - `releases/<release_id>/outputs/merged/`
  - `database/current/`
  - `database/history/`

raw_source 全量重跑黑盒旧链路，标准化形式不变，新增原始数据最终会进入和旧版一致的master/merge 口径。

补充硬规则：

- `raw_source` 永久复用旧 14 步黑盒，不在新软件中重写标准化细节
- 新软件只验证黑盒输出是否符合正式结果层合同
- 若旧黑盒输出与本规范的正式结果层合同冲突，以“修旧黑盒脚本并更新 baseline”为准，不允许在黑盒外再做一层静默补丁改写正式结果语义

#### 10.1.2 `external_source` 的标准化规则

`external_source` 标准化是去重前强制步骤，没有完成标准化的数据，不允许进入统一去重链路。

标准化至少包括：

- 将输入列名映射为统一字段名
- 将别名字段映射到标准字段
- 将 `parameter_name` 统一为受控名称
- 将空字符串、`NA`、`N/A`、`null`、`None` 等缺失表示统一
- 将 `value`、`unit`、条件字段整理到统一承载方式
- 将 `business_key` 相关字段整理为可比对格式
- 将条件相关字段整理为后续 `conditions` 导出可直接使用的格式

`external_source` 在标准化完成后，至少应得到：

- 统一字段名
- 统一 `parameter_name`
- 统一 `business_key` 字段
- 标准化后的条件字段
- 可用于去重的标准记录
- `business_key`
- `measurement_uid`
- 导入级整行去重所需的 canonical row

#### 10.1.3 `manual_override` 的标准化规则

`manual_override` 标准化的对象不是“事实记录表”，而是“patch 指令表”。

`manual_override` 至少要标准化以下内容：

- `record_id`
- `target_table`
- `target_scope`
- `match_key_type`
- `field_name`
- `action`
- `approved_at`

如果 `match_key_type == record_id`，则必须检查：

- `record_id` 是否存在
- 是否能唯一命中目标正式结果层记录

如果 `match_key_type == business_key`，则以下字段必须按与正式数据一致的业务键规则标准化：

- `uniprot`
- `enzyme_type`
- `mutation`
- `sequence`
- `substrate`
- `smiles`
- 且 `uniprot`、`sequence`、`substrate`、`smiles` 四个字段不得同时为空

如果 `match_key_type == record_key`，则必须明确：

- 仅允许用于当前 release 内部临时定位
- 仅允许用于工作区或当前 release 的中间结果
- 不允许用于 `current` 正式结果层
- 不允许作为长期修正规则的唯一依赖键

#### 10.1.4 字段层面的统一要求

无论来源如何，只要进入统一结果层，以下标准必须一致：

- `parameter_name`
  - 使用统一受控名称
  - `kcat` 和 `km` 分开去重
- `uniprot`
  - 使用统一大小写和空值规则
- `enzyme_type`
  - 对齐统一枚举语义
- `mutation`
  - 使用统一突变表示规则
- `sequence`
  - 去除换行和额外空白，统一序列表示方式
- `substrate`
  - 使用统一底物文本表示
- `smiles`
  - 使用统一字符串承载方式
- `value_normalized`
  - 用于实验级去重
- `ph`
  - 用于实验级去重和条件表导出
- `temperature`
  - 用于实验级去重和条件表导出

来源字段语义固定如下：

- `source_db`
  - 表示来源系统名
  - 仅作 provenance，不参与正式去重键
- `source_record_id`
  - 表示来源记录定位符
  - 仅作 provenance 和排查定位，不参与正式去重键
- `source_release`
  - 表示来源版本或快照标签
  - 仅作 provenance 补充，不参与正式去重键
- `source_file` / `source_row`
  - 仅作工作区与审计定位，不属于正式键

补充规则：

1. `ec_number` 必须保留为正式字段，但不参与正式去重键
2. `organism` 与 `ions` 必须保留为正式字段，但不参与 `business_key` 或 `measurement_uid` 的主判定
3. `organism` 与 `ions` 只用于冲突拦截和人工审计
4. 不允许为了适配新输入而改变旧版正式字段语义
5. 不允许在正式输出层静默新增未登记字段
6. `business_key`、`measurement_uid`、`record_id` 的计算必须基于标准化后的字段

### 10.2 键规则

#### 10.2.1 `record_id` 规则

`record_id` 是正式结果层最终单行身份的物理字段名。

规则：

- `record_id` 只表示最终正式结果中的单行身份
- `record_id` 必须在正式 `merged` 与正式 `conditions` 中单行唯一
- `record_id` 必须在以下步骤完成后生成：
  1. 标准化
  2. 完全相同行去重
  3. 正式业务去重
  4. `test_leakage_filter`
- `record_id` 的生成必须能够区分：
  - 不同 `measurement_uid`
  - 同一 `measurement_uid` 下因 `organism` 或 `ions` 冲突而并存保留的正式记录
- 若 patch 仅修改非身份性字段，例如 `commentary`、`reaction_raw`、`parse_status` 等，不得静默重算 `record_id`
- `conditions` 导出时必须直接继承正式 `merged` 中对应记录的同一个 `record_id`

#### 10.2.2 `business_key` 规则

`business_key` 是正式业务去重中的主键。

固定字段为：

- `uniprot`
- `enzyme_type`
- `mutation`
- `sequence`
- `substrate`
- `smiles`

规则：

- `business_key` 必须基于标准化后的字段重算
- `business_key` 不是正式单行 ID
- `uniprot`、`sequence`、`substrate`、`smiles` 四个字段不得同时为空
- `kcat` 和 `km` 不跨 `parameter_name` 互相去重


#### 10.2.3  `measurement_uid` 规则

`measurement_uid` 是正式业务去重中的实验候选键。

固定字段为：

- `uniprot`
- `enzyme_type`
- `mutation`
- `sequence`
- `substrate`
- `smiles`
- `parameter_name`
- `value_normalized`
- `ph`
- `temperature`

规则：

- `measurement_uid` 必须基于标准化后的字段重算
- `measurement_uid` 不是来源键
- `measurement_uid` 不是正式单行 ID
- 同一 `business_key`、同一 `parameter_name` 下：
  - `measurement_uid` 相同，表示同一实验候选
  - `measurement_uid` 不同，表示不同实验，必须同时保留
- `value_normalized`、`ph`、`temperature` 三者中任意一个不同，都必须生成不同 `measurement_uid`
- 若 `measurement_uid` 相同但 `organism` 或 `ions` 不同，则不得自动合并，必须进入审计。

### 10.3 去重规则

正式去重固定分五步：

1. 标准化
2. 完全相同行去重
3. 正式业务去重
4. `test_leakage_filter`
5. 生成正式 `record_id`

#### 10.3.1 导入级去重 `import_dedup`

目标：

- 去掉完全重复行

判定标准：

- 标准化后的整行字段完全一致

处理规则：

- 保留第一条
- 其余写入：
  - `audits/import_duplicate_rows.csv`

#### 10.3.2 正式业务去重 `business_dedup`

目标：

- 先按标准化后的 `business_key` 识别是否属于同一条目
- 再在同一条目、同一 `parameter_name` 下按 `measurement_uid` 识别是否属于同一实验候选

规则：

- `kcat` 和 `km` 不跨 `parameter_name` 互相去重
- 只有在同一 `business_key`、同一 `parameter_name` 下，才允许继续比较 `measurement_uid`
- `value_normalized`、`ph`、`temperature` 中任意一个不同，都必须保留为不同实验记录
- `record_key` 只允许用于工作区和审计定位，不得进入正式业务分组逻辑

自动匹配前提：

- 对 `external_source` 输入行，只有同时满足以下两组条件，才允许进入正式业务去重：
  - `uniprot` / `sequence` 至少 1 个非空
  - `substrate` / `smiles` 至少 1 个非空
- 若不满足：
  - 不进入正式业务去重
  - 不进入正式 survivor 候选集合
  - 必须写入 `rejected_rows.csv`
  - `reject_reason` 记录具体缺项原因

冲突拦截：

- 如果两条记录满足以下条件：
  - `business_key` 相同
  - `parameter_name` 相同
  - `measurement_uid` 相同
  - 但 `organism` 或 `ions` 不同
- 则：
  - 不自动合并
  - 继续保留
  - 必须写入 `conflicts.csv`
  - `conflict_type` 固定记为 `organism_or_ions_conflict`

正式 survivor 判定：

- 只有当两条记录同时满足以下条件时，才允许视为同一实验候选并继续 survivor 排序：
  - `business_key` 相同
  - `parameter_name` 相同
  - `measurement_uid` 相同
  - `organism` 相同
  - `ions` 相同

同候选集合内保留顺序：

1. `manual_override`
2. `raw_source`
3. `external_source`
  - 人工修正最优先，原始正式链路次之，普通外部补充最后。
4. 同优先级时按 release 版本排序
  - - release_id，新的 release 优先
5. 再按稳定记录顺序排序
6. 保留第一条
7. 其余写入 `audits/business_duplicate_rows.csv`

#### 10.3.3 `test_leakage_filter`

训练集根据验证集（目前验证集为IntEnzy）做防泄漏，必须在正式业务去重之后、`record_id` 正式落盘之前。

规则：

- 只对正式业务去重后的结果执行
- 当前正式结果层仍按 `kcat` / `km` 分表输出
- `kcat` 结果只与 `IntEnzy_kcat` test 集比较
- `km` 结果只与 `IntEnzy_km` test 集比较
- 每张表内部继续按 `business_key` 做泄漏阻断
- 命中 test 的正式记录必须从训练结果移出
- 不同实验条件但属于同一 `business_key` 的记录，仍视为泄漏并阻断
- 被阻断记录必须写入：
  - `audits/test_leakage_removed.csv`

审计解释口径：

- 若 `business_key` 命中，且 `measurement_uid` 也一致，记为 `exact_experiment_overlap`
- 若 `business_key` 命中，但 `measurement_uid` 不一致，记为 `same_entry_different_experiment_overlap`

### 10.4 条件表规则

无论来源类型如何，正式输出层都必须有：

- `outputs/conditions/`

当前固定输出两张条件全量表：

- `ph_long_table.csv`
- `temperature_long_table.csv`

正式规则如下：

1. 必须先完成正式 `merged` 结果层构建
2. `conditions` 只能从正式 `merged` 结果层导出
3. 不允许直接从未去重的 `master`、原始输入或任意中间表导出正式条件表
4. `ph_long_table.csv`
   - 从正式 `merged` 结果中筛选 `ph` 非空记录
   - 必须保留该正式记录的全部正式字段
5. `temperature_long_table.csv`
   - 从正式 `merged` 结果中筛选 `temperature` 非空记录
   - 必须保留该正式记录的全部正式字段
6. `conditions` 不再单独发明第二套业务去重规则
7. 同一条正式记录如果 `ph` 与 `temperature` 都非空，可以同时出现在两张条件表中
8. 条件表中的 `record_id` 必须直接继承正式 `merged` 中的对应值
9. 若某次 release 的条件表为空，也必须输出仅含表头的空表

## 11. 运行产物、Manifest、日志与审计规则

### 11.1 正式输出规则

正式输出统一进入：

- `outputs/master/`
- `outputs/merged/`
- `outputs/summary/`
- `outputs/conditions/`

这四类目录中的文件才属于本次 release 的正式结果。

#### 11.1.1 固定正式文件清单

正式输出文件清单固定如下。

`outputs/master/` 固定 7 个文件：

- `CataPro_kcat_master_v6_enriched.csv`
- `CataPro_km_master_v6_enriched.csv`
- `DLKcat_kcat_master_v6_enriched.csv`
- `IntEnzy_kcat_master_v6_enriched.csv`
- `IntEnzy_km_master_v6_enriched.csv`
- `SKiD_kcat_master_v6_enriched.csv`
- `SKiD_km_master_v6_enriched.csv`

`outputs/merged/` 固定 2 个文件：

- `merge_kcat_final_v6_enriched.csv`
- `merge_km_final_v6_enriched.csv`

`outputs/summary/` 固定 8 个文件：

- `summary_v6.txt`
- `summary_v6_counts.csv`
- `mutation/kcat_mutation_rows_v6.csv`
- `mutation/km_mutation_rows_v6.csv`
- `ph_tem_empty/kcat_ph_temperature_empty_v6.csv`
- `ph_tem_empty/km_ph_temperature_empty_v6.csv`
- `unit/kcat_unit_audit_v6.csv`
- `unit/km_unit_audit_v6.csv`

`outputs/conditions/` 固定 2 个文件：

- `ph_long_table.csv`
- `temperature_long_table.csv`

补充规则：

- `external_source` 和 `manual_override` 在 v1 中不允许新增新的正式顶层文件名
- 如需扩展正式文件清单，必须先修订本规范，再升级代码
- 所有正式 release 都必须生成两张条件表；即使为空表，也必须保留表头

#### 11.1.2 正式 `enriched` schema 固定合同

`outputs/master/*.csv`、`outputs/merged/*.csv`、`outputs/conditions/*.csv` 的正式字段顺序固定如下：

1. `dataset_name`
2. `parameter_name`
3. `source_db`
4. `source_release`
5. `source_record_id`
6. `record_id`
7. `measurement_uid`
8. `ec_number`
9. `organism`
10. `uniprot`
11. `enzyme_type`
12. `mutation`
13. `sequence`
14. `sequence_source`
15. `substrate`
16. `smiles`
17. `value`
18. `unit`
19. `ph`
20. `temperature`
21. `ions`
22. `reaction_raw`
23. `commentary`
24. `substrate_raw`
25. `parse_status`
26. `mutation_apply_status`
27. `WT_sequence`
28. `MUT_sequence`
29. `value_normalized`
30. `unit_normalized`
31. `kcat_km_source_value`
32. `kcat_km_source_unit`
33. `kcat_km_computed_value`
34. `kcat_km_computed_unit`

硬规则：

- 正式输出不允许改字段名
- 正式输出不允许改字段顺序
- 正式输出不允许删字段
- 正式输出不允许把工作区控制字段直接混入正式结果
- `ph_long_table.csv` 与 `temperature_long_table.csv` 必须使用与正式 `merged` 完全相同的字段顺序
- 第 6 列物理字段 `record_id` 是正式结果层最终单行身份
- 第 7 列物理字段 `measurement_uid` 是正式业务去重中的 measurement 级实验候选键

#### 11.1.3 `summary/` 固定合同

- `summary_v6_counts.csv` 固定列顺序：
  - `section`
  - `metric`
  - `value`
- `mutation/*.csv` 与 `ph_tem_empty/*.csv` 固定使用正式 `enriched` schema
- `unit/*.csv` 固定使用：
  - 正式 `enriched` schema
  - 再追加 `unit_audit_status`
  - 再追加 `unit_audit_reason`
- `summary_v6.txt` 固定至少包含以下段落标题：
  - `# CataPro V6 Summary`
  - `## inputs`
  - `## kcat_subsets`
  - `## kcat_unit_audit`
  - `## km_subsets`
  - `## km_unit_audit`

### 11.2 Manifest 固定文件规则（部分示例见附录B）

每个 release 的 `manifest/` 固定保留以下文件：

- `release_manifest.json`
- `input_manifest.json`
- `output_manifest.json`
- `file_inventory.csv`
- `run_summary.txt`
- `plan_preview.json`
- `plan_preview.txt`
- `validate_report.json`
- `validate_report.txt`
- `dedup_batch_manifest.json`                  # external_source 时会有
- `ph_long_table_manifest.json`                # 生成 conditions 时会有
- `temperature_long_table_manifest.json`       # 生成 conditions 时会有
以上 12 个文件全部为强制文件，不再区分“建议扩展”。

补充说明：

- `raw_source` 黑盒负责在 release workspace 内跑完整 14 步过程，并产出可同步的正式输出素材
- release 层的 `manifest/` 由应用层统一写出，作为三类更新链路共用的正式登记与审计入口

通用硬规则：

- JSON 文件缺失字段时不得省略 key；未知值写 `null`
- 数组字段若无内容，写空数组 `[]`
- CSV 文件缺失值写空字符串，不删列
- 所有路径字段统一写仓库内相对路径，必要时可额外补充绝对路径字段
- 所有时间字段统一使用 ISO 8601，带时区，例如 `2026-07-26T21:30:00+08:00`

#### 11.2.1 `release_manifest.json`

固定顶层键顺序如下：

1. `release_id`
2. `run_date`
3. `source_type`
4. `input_mode`
5. `status`
6. `operator`
7. `software_version`
8. `pipeline_mode`
9. `repo_root`
10. `data_root`
11. `notes`

字段规则：

- `release_id` 不可为空
- `run_date` 不可为空
- `source_type` 不可为空
- `input_mode` 不可为空
- `status` 只允许：
  - `planned`
  - `validated`
  - `running`
  - `completed`
  - `completed_with_warning`
  - `failed`
  - `rolled_back`
- `operator` 不可为空
- `software_version` 不可为空
- `pipeline_mode` 不可为空
- `repo_root` 不可为空
- `data_root` 不可为空
- `notes` 固定为字符串数组，可为空数组，但 key 不可缺失

#### 11.2.2 `input_manifest.json`

固定顶层键顺序如下：

1. `release_id`
2. `source_type`
3. `input_root`
4. `input_files`
5. `reference_files`
6. `current_baseline_root`
7. `snapshot_used`
8. `snapshot_path`
9. `input_file_count`

字段规则：

- `input_files` 为对象数组，每个对象固定键顺序：
  - `relative_path`
  - `format`
  - `size_bytes`
  - `modified_time`
  - `sha1`
- `reference_files` 为字符串数组
- `snapshot_used` 为布尔值
- `snapshot_path` 若未使用 snapshot，则写 `null`
- `input_file_count` 必须等于 `input_files` 数组长度

#### 11.2.3 `output_manifest.json`

固定顶层键顺序如下：

1. `release_id`
2. `run_status`
3. `source_type`
4. `outputs`
5. `audits`
6. `workspace`

字段规则：

- `outputs` 固定包含：
  - `master`
  - `merged`
  - `summary`
  - `conditions`
- 四个子对象都固定包含：
  - `root`
  - `file_count`
  - `files`
- `files` 为对象数组，每个对象固定键顺序：
  - `path`
  - `file_name`
  - `row_count`
  - `column_count`
  - `size_bytes`
  - `sha1`
- `audits` 固定包含：
  - `root`
  - `file_count`
  - `files`
- `workspace` 固定包含：
  - `raw_source_used`
  - `external_source_used`
  - `manual_override_used`

#### 11.2.4 `file_inventory.csv`

`file_inventory.csv` 一行一个文件，固定列顺序如下：

- `release_id`
- `category`
- `subtype`
- `relative_path`
- `file_name`
- `row_count`
- `column_count`
- `size_bytes`
- `modified_time`
- `sha1`

#### 11.2.5 `plan_preview.json` 

固定顶层键顺序如下：

- `release_id`
- `plan_time`
- `source_type`
- `input_mode`
- `input_path`
- `detected_formats`
- `input_file_count`
- `input_files`
- `pipeline_route`
- `planned_outputs`
- `current_snapshot_required`
- `snapshot_target`
- `can_proceed`
- `warnings`
- `standardized_file_count`

#### 11.2.6 `validate_report.json` 

固定顶层键顺序如下：

- `release_id`
- `validate_time`
- `source_type`
- `input_path`
- `status`
- `can_run`
- `file_checks`
- `schema_checks`
- `quality_checks`
- `issues`
- `summary`

#### 11.2.7 `plan_preview.txt` 

固定至少包含以下标题，顺序不得变：

1. `Release ID:`
2. `Source type:`
3. `Input path:`
4. `Detected formats:`
5. `Input file count:`
6. `Planned route:`
7. `Planned outputs:`
8. `Planned workspace:`
9. `Snapshot required:`
10. `Proceed recommendation:`
11. `Warnings:`

#### 11.2.8 `validate_report.txt` 

固定至少包含以下标题，顺序不得变：

1. `Release ID:`
2. `Source type:`
3. `Input path:`
4. `Validation status:`
5. `Can run:`
6. `File checks:`
7. `Schema checks:`
8. `Quality checks:`
9. `Issues:`
10. `Summary:`

#### 11.2.9 `run_summary.txt`

`run_summary.txt` 固定至少包含以下标题，顺序不得变：

1. `Release ID:`
2. `Source type:`
3. `Input mode:`
4. `Status:`
5. `Input files:`
6. `Outputs:`
7. `Audits:`
8. `Warnings:`
9. `Notes:`

### 11.3 日志规则

当前正式规则只要求：

- `releases/<release_id>/logs/` 目录必须存在
- `raw_source` 链路当前把旧黑盒每个脚本的标准输出写入：
  - `releases/<release_id>/logs/raw_source/<step_index>_<script_name>.log`

补充说明：

- 当前实现没有强制生成统一命名的 `run.log` / `validate.log` / `error.log`
- `plan`、`validate`、`run` 的可读摘要当前分别写入：
  - `manifest/plan_preview.txt`
  - `manifest/validate_report.txt`
  - `manifest/run_summary.txt`
- 若后续扩展统一日志聚合文件，必须先修订本规范，再升级代码

### 11.4 审计规则

本次 release 内部审计固定文件如下：

- `import_duplicate_rows.csv`
- `business_duplicate_rows.csv`
- `test_leakage_removed.csv`
- `rejected_rows.csv`
- `conflicts.csv`
- `validation_issues.csv`
- `override_applied.csv`
- `override_skipped.csv`
- `override_conflicts.csv`

通用规则：

- 不适用某链路的审计文件也必须生成空表头文件
- 所有审计 CSV 的前 8 列固定为：
  - `audit_id`
  - `release_id`
  - `source_type`
  - `audit_file`
  - `audit_stage`
  - `audit_reason`
  - `source_file`
  - `source_row`

各审计文件追加列固定如下：

- `import_duplicate_rows.csv`
  - `record_key`
  - `record_id`
  - `business_key`
  - `measurement_uid`
  - `parameter_name`
  - `source_db`
  - `source_record_id`
  - `notes`
- `business_duplicate_rows.csv`
  - `record_key`
  - `record_id`
  - `business_key`
  - `measurement_uid`
  - `parameter_name`
  - `organism`
  - `ions`
  - `survivor_source`
  - `notes`
- `test_leakage_removed.csv`
  - `record_key`
  - `record_id`
  - `business_key`
  - `matched_test_key`
  - `parameter_name`
  - `source_db`
  - `source_record_id`
  - `notes`
  - `matched_test_key` 固定记录命中的 test 侧 `business_key`
  - 如需更细审计，可在 `notes` 中记录 `exact_experiment_overlap` 或 `same_entry_different_experiment_overlap`
- `rejected_rows.csv`
  - `reject_stage`
  - `reject_reason`
  - `record_key`
  - `record_id`
  - `business_key`
  - `measurement_uid`
  - `parameter_name`
  - `source_db`
  - `source_record_id`
  - `notes`
- `conflicts.csv`
  - `conflict_type`
  - `conflict_detail`
  - `record_key`
  - `record_id`
  - `business_key`
  - `measurement_uid`
  - `parameter_name`
  - `organism`
  - `ions`
  - `field_name`
  - `old_value`
  - `new_value`
  - `notes`
- `validation_issues.csv`
  - `severity`
  - `field_name`
  - `issue_code`
  - `issue_message`
  - `record_key`
  - `record_id`
  - `notes`
- `override_applied.csv`
  - `operation_id`
  - `target_table`
  - `match_key_type`
  - `action`
  - `field_name`
  - `record_id`
  - `record_key`
  - `old_value`
  - `new_value`
  - `approved_by`
  - `approved_at`
  - `reason`
- `override_skipped.csv`
  - `operation_id`
  - `target_table`
  - `match_key_type`
  - `action`
  - `skip_reason`
  - `record_id`
  - `record_key`
  - `approved_by`
  - `approved_at`
  - `reason`
- `override_conflicts.csv`
  - `operation_id`
  - `target_table`
  - `match_key_type`
  - `action`
  - `conflict_type`
  - `conflict_detail`
  - `record_id`
  - `record_key`
  - `approved_by`
  - `approved_at`
  - `reason`

### 11.5 `history_logs` 文件与精确列定义

`history_logs` 用于记录正式结果层逐条变化日志，不是整表快照。

固定目录与文件如下：

- `database/history/history_logs/conditions/ph_history_log.csv`
- `database/history/history_logs/conditions/temperature_history_log.csv`
- `database/history/history_logs/master/master_change_log.csv`
- `database/history/history_logs/merged/merged_change_log.csv`

通用规则：

1. `history_logs` 只记录正式结果层变化：
   - `append`
   - `replace`
   - `fill_if_blank`
   - `clear`
   - `drop_row`
2. `log_id` 固定格式：
   - `log_<release_id>_<serial_no>`
3. `business_key` 在日志中固定写为 6 键 canonical string：
   - `uniprot|enzyme_type|mutation|sequence|substrate|smiles`
4. `measurement_uid` 在日志中固定写为 measurement 级 canonical string 的摘要键
5. `record_id` 在日志中固定写正式结果层最终单行 ID
6. `source_row` 必须保留原输入定位信息
7. `notes` 可为空，但列必须保留

`ph_history_log.csv` 与 `temperature_history_log.csv` 固定列顺序如下：

- `log_id`
- `release_id`
- `log_time`
- `target_table`
- `condition_type`
- `action`
- `record_id`
- `record_key`
- `business_key`
- `measurement_uid`
- `parameter_name`
- `ec_number`
- `uniprot`
- `enzyme_type`
- `mutation`
- `sequence`
- `substrate`
- `smiles`
- `field_name`
- `old_value`
- `new_value`
- `old_row_json`
- `new_row_json`
- `source_type`
- `source_file`
- `source_row`
- `operator`
- `reason`
- `notes`

其中：

- `ph_history_log.csv` 的 `condition_type` 固定为 `ph`
- `temperature_history_log.csv` 的 `condition_type` 固定为 `temperature`

`master_change_log.csv` 与 `merged_change_log.csv` 固定列顺序如下：

- `log_id`
- `release_id`
- `log_time`
- `table_scope`
- `dataset_key`
- `target_file`
- `change_type`
- `business_key`
- `record_id`
- `measurement_uid`
- `parameter_name`
- `old_row_json`
- `new_row_json`
- `source_type`
- `notes`

补充规则：

1. `master_change_log.csv` 与 `merged_change_log.csv` 记录的是正式结果层逐条 append / replace / remove 结果
2. `conditions` history log 记录的是条件表逐条 append / replace 结果
3. `operator` 对自动运行写系统操作者；对人工 patch 写审批或执行人
4. 任意正式结果变更若未写入对应 `history_logs`，则视为不合规变更

## 12. 结果审核与 `current` 切换规则

### 12.1 审核规则

每次新结果跑完后，不允许立即覆盖 `current`，必须先审核。

审核必须同时做结构审核和数量审核。

结构审核硬规则：

- `outputs/master/`、`outputs/merged/`、`outputs/summary/`、`outputs/conditions/` 的正式文件清单必须与本规范一致
- 正式 CSV 字段名和字段顺序必须与本规范一致
- 必须生成 12 个 `manifest/` 文件
- 必须生成 9 个 `audits/` 文件

数量审核硬规则以“上一版 `database/current/` 为基线”：

1. `raw_source`
   - `merged` 总行数下降超过 `20%`：`fail`
   - `merged` 总行数下降超过 `10%` 且不超过 `20%`：`pass_with_warning`
   - `master` 总行数下降超过 `20%`：`fail`
   - `summary/unit/*.csv` 行数增长超过 `100%`：`fail`
   - `summary/unit/*.csv` 行数增长超过 `50%` 且不超过 `100%`：`pass_with_warning`
2. `external_source`
   - `merged` 总行数下降超过 `5%`：`fail`
   - `merged` 总行数下降超过 `1%` 且不超过 `5%`：`pass_with_warning`
   - `merged` 总行数增长超过 `100%`：`fail`
   - `merged` 总行数增长超过 `50%` 且不超过 `100%`：`pass_with_warning`
   - `summary/ph_tem_empty/*.csv` 行数增长超过 `50%`：`fail`
   - `summary/ph_tem_empty/*.csv` 行数增长超过 `20%` 且不超过 `50%`：`pass_with_warning`
   - `summary/unit/*.csv` 行数增长超过 `100%`：`fail`
   - `summary/unit/*.csv` 行数增长超过 `50%` 且不超过 `100%`：`pass_with_warning`
3. `manual_override`
   - `override_applied.csv` 的数据行数必须 `>= 1`
   - `override_applied.csv` 的数据行数 `> 1000`：`fail`
   - `override_applied.csv` 的数据行数 `> 200` 且 `<= 1000`：`pass_with_warning`
   - `merged` 总行数绝对变化比例 `> 2%`：`fail`
   - `merged` 总行数绝对变化比例 `> 0.5%` 且 `<= 2%`：`pass_with_warning`

条件表审核硬规则：

- `ph_long_table.csv` 与 `temperature_long_table.csv` 必须存在
- 若文件非空，其字段顺序必须与正式 `merged` 完全一致
- 若文件为空表，也必须仅保留表头，且表头必须与正式 `merged` 完全一致

### 12.2 审核结果处理规则

如果审核失败：

- 保留本次 `release`
- 不修改 `current`

如果审核通过：

- 进入 `current` 切换步骤

补充规则：

- 运行成功不等于结果可正式生效
- 未审核通过时，`release` 可以保留，但 `current` 不得更新
- `pass_with_warning` 允许进入人工审核，但不得自动切换 `current`
- 只有审核结果为 `pass` 时，才允许自动进入 `current` 切换

### 12.3 `current` 切换规则

审核通过后，把：

- `releases/<release_id>/outputs/master/*`
- `releases/<release_id>/outputs/merged/*`
- `releases/<release_id>/outputs/summary/*`
- `releases/<release_id>/outputs/conditions/*`

复制覆盖到：

- `database/current/master/`
- `database/current/merged/`
- `database/current/summary/`
- `database/current/conditions/`

这一步才叫：

- 正式生效版本切换

补充规则：

- “跑完流程”只表示产物生成
- “切换 `current`”才表示正式生效

### 12.4 `current_switch_audit.csv` （示例表见附录B）

每次切换 `current` 后，应记录切换审计。

固定写入：

- `history/audits/current_switch_audit.csv`

固定列顺序如下：

- `release_id`
- `switch_time`
- `operator`
- `source_type`
- `snapshot_path`
- `output_path`
- `status`
- `notes`

## 13. 回滚与基线规则

### 13.1 回滚触发场景

以下情况允许发起回滚：

- 新 release 审核后发现结果异常
- `current/` 已切换，但后续发现主表、条件表、汇总表存在明显错误
- `manual_override` 误改了当前正式结果
- 发布后发现空值、单位、去重、条件导出等关键指标异常波动
- 需要恢复到某个已知稳定版本以继续后续更新

### 13.2 回滚对象

回滚的最小正式单位是：

- 一整套 `current`

不允许只回滚 `current` 里的单个字段而不记录版本动作。

标准回滚范围固定为：

- `database/current/master/`
- `database/current/merged/`
- `database/current/summary/`
- `database/current/conditions/`

### 13.3 回滚依据

正式回滚优先使用更新前快照：

- `database/history/snapshots/<release_id>-before/`

必要时，可将以下位置作为辅助核对来源：

- `releases/<release_id>/outputs/`
- `releases/<older_release_id>/outputs/`
- `releases/<release_id>/manifest/`
- `releases/<release_id>/audits/`

但正式恢复 `current` 时，默认恢复源仍应是对应的 `snapshot`。

### 13.4 回滚前强制动作

任何正式回滚执行前，都必须先把当前仍在生效的 `current` 再做一份快照。

建议写入：

- `database/history/snapshots/<rollback_release_id>-before/`

其中：

- `<rollback_release_id>` 是这次回滚动作本身的版本号

### 13.5 回滚执行步骤

正式回滚按以下顺序执行：

1. 确认需要回滚的问题 release
2. 生成本次回滚动作自己的 `rollback_release_id`
3. 将当前 `database/current/` 整套备份到：
   - `database/history/snapshots/<rollback_release_id>-before/`
4. 定位目标恢复快照：
   - `database/history/snapshots/<problem_release_id>-before/`
5. 校验目标快照是否完整
6. 将目标快照整套复制回 `database/current/`
7. 写入回滚审计、回滚说明和结果清单
8. 将本次回滚登记为一次独立 release 动作

补充规则：

- 回滚不是删除坏版本
- 回滚是把 `current` 恢复到目标快照对应状态

### 13.6 回滚审计要求

每次回滚至少要新增：（示例表见附录B）

- `history/audits/rollback_actions.csv`
- `history/audits/current_switch_audit.csv`
- `releases/<rollback_release_id>/manifest/release_manifest.json`
- `releases/<rollback_release_id>/manifest/run_summary.txt`

建议至少记录：

- `rollback_release_id`
- `rollback_time`
- `operator`
- `rollback_reason`
- `problem_release_id`
- `restored_snapshot_path`
- `current_before_rollback_snapshot`
- `restored_tables`
- `status`
- `notes`

### 13.7 旧 release 重新生效与回滚的区别

区分：

- 回滚
  - 恢复到某次更新前快照
- 旧 release 重新生效
  - 将某个历史 release 的 `outputs/` 重新提升为 `current`

规则：

- 如果目标是撤销某次错误更新，优先使用回滚
- 如果目标是让某个历史正式版本重新成为 `current`，可执行旧 release 重新提升
- 两者都必须先做当前快照并留下审计

### 13.8 `manual_override` 的回滚边界

`manual_override` 不做“按单字段静默撤销”。

正式规则：

- 如果某次 `manual_override` 已进入 `current`，默认仍按整套 `current` 回滚
- 不直接改写 `database/original/`
- 不允许绕开 release 和 history 机制直接手工删改 `current`

后续若要支持更细粒度撤销，也必须通过：

- `manual_override` 反向 patch
- 或新的正式 release 动作

并留下完整审计记录。

### 13.9 回滚后的状态要求

回滚完成后，应满足：

- `database/current/` 恢复为目标快照对应版本
- 本次回滚在 `history/audits/` 中可追溯
- 原有错误版本仍保留在 `releases/` 中，不删除
- 回滚前现场已保存在新的 `snapshot` 中
- 后续继续更新时，以回滚后的 `current` 作为新起点

回滚后历史中至少应保留：

- 问题版本本身
- 回滚前现场
- 恢复依据快照



## 附录 A. `plan` / `validate` / `run` 产物示例

### A.1 `plan_preview.json` 示例

```json
{
  "release_id": "20260725-ext001",
  "plan_time": "2026-07-25T14:30:00+08:00",
  "source_type": "external_source",
  "input_mode": "external_source",
  "input_path": "D:\\catapro_delivery\\.external_data\\incoming\\20260725_ext_batch_001\\external",
  "detected_formats": ["csv"],
  "input_file_count": 2,
  "input_files": [
    {
      "file_name": "external_update_1.csv",
      "format": "csv",
      "row_count_estimate": 1200
    }
  ],
  "pipeline_route": {
    "uses_legacy_pipeline": false,
    "uses_external_pipeline": true,
    "uses_manual_override_pipeline": false
  },
  "planned_outputs": {
    "workspace": [
      "workspace/external_source/standardized_inputs",
      "workspace/external_source/dedup",
      "workspace/external_source/conditions",
      "workspace/external_source/reports"
    ],
    "outputs": [
      "outputs/master",
      "outputs/merged",
      "outputs/summary",
      "outputs/conditions"
    ],
    "audits": [
      "audits/import_duplicate_rows.csv",
      "audits/business_duplicate_rows.csv",
      "audits/validation_issues.csv"
    ]
  },
  "current_snapshot_required": true,
  "snapshot_target": "database/history/snapshots/20260725-ext001-before",
  "can_proceed": true,
  "warnings": [],
  "standardized_file_count": 2
}
```

### A.2 `plan_preview.txt` 示例

```text
Release ID: 20260725-ext001
Source type: external_source
Input path: D:\catapro_delivery\.external_data\incoming\20260725_ext_batch_001\external
Detected formats: csv
Input file count: 2

Planned route:
- Legacy 14-step pipeline: no
- External incremental pipeline: yes
- Manual override pipeline: no

Planned outputs:
- outputs/master
- outputs/merged
- outputs/summary
- outputs/conditions

Planned workspace:
- workspace/external_source/standardized_inputs
- workspace/external_source/dedup
- workspace/external_source/conditions
- workspace/external_source/reports

Snapshot required: yes
Proceed recommendation: yes
Warnings: none
```

### A.3 `validate_report.json` 示例

```json
{
  "release_id": "20260725-ext001",
  "validate_time": "2026-07-25T14:35:00+08:00",
  "source_type": "external_source",
  "input_path": "D:\\catapro_delivery\\.external_data\\incoming\\20260725_ext_batch_001\\external",
  "status": "pass",
  "can_run": true,
  "file_checks": {
    "input_file_count": 2,
    "allowed_extensions": [".csv", ".json", ".tsv", ".xls", ".xlsx"],
    "bad_extensions": []
  },
  "schema_checks": {
    "required_columns": ["parameter_name", "value"],
    "row_level_required_rules": [
      "parameter_name must be non-empty",
      "value must be non-empty",
      "at least one of uniprot / sequence must be non-empty",
      "at least one of substrate / smiles must be non-empty"
    ],
    "missing_required_files": []
  },
  "quality_checks": {
    "standardized_row_count": 1200,
    "standardized_success_count": 1200,
    "insufficient_match_evidence_count": 0,
    "missing_parameter_name_row_count": 0,
    "missing_value_row_count": 0,
    "missing_uniprot_or_sequence_row_count": 0,
    "missing_substrate_or_smiles_row_count": 0
  },
  "issues": [],
  "summary": {
    "input_file_count": 2,
    "status": "pass",
    "can_run": true
  }
}
```

### A.4 `validate_report.txt` 示例

```text
Release ID: 20260725-ext001
Source type: external_source
Input path: D:\catapro_delivery\.external_data\incoming\20260725_ext_batch_001\external
Validation status: pass
Can run: yes

File checks: {"input_file_count": 2, "allowed_extensions": [".csv", ".json", ".tsv", ".xls", ".xlsx"], "bad_extensions": []}
Schema checks: {"required_columns": ["parameter_name", "value"], "row_level_required_rules": ["parameter_name must be non-empty", "value must be non-empty", "at least one of uniprot / sequence must be non-empty", "at least one of substrate / smiles must be non-empty"], "missing_required_files": []}
Quality checks: {"standardized_row_count": 1200, "standardized_success_count": 1200, "insufficient_match_evidence_count": 0, "missing_parameter_name_row_count": 0, "missing_value_row_count": 0, "missing_uniprot_or_sequence_row_count": 0, "missing_substrate_or_smiles_row_count": 0}
Issues: []
Summary: {"input_file_count": 2, "status": "pass", "can_run": true}
```

### A.5 `run_summary.txt` 示例

```text
Release ID: 20260725-ext001
Source type: external_source
Input mode: external_source
Status: completed

Input files: manifest/input_manifest.json
Outputs:
- outputs/master
- outputs/merged
- outputs/summary
- outputs/conditions

Audits:
- audits

Warnings: none
Notes:
- release completed by catapro_update_app
```

### A.6 `output_manifest.json` 示例

```json
{
  "release_id": "20260725-ext001",
  "run_status": "completed",
  "source_type": "external_source",
  "outputs": {
    "master": {
      "root": "outputs/master",
      "file_count": 7,
      "files": [
        {
          "path": "outputs/master/CataPro_kcat_master_v6_enriched.csv",
          "file_name": "CataPro_kcat_master_v6_enriched.csv",
          "row_count": 12346,
          "column_count": 34,
          "size_bytes": 2851934,
          "sha1": "2e7c8abf5d1234567890"
        }
      ]
    },
    "merged": {
      "root": "outputs/merged",
      "file_count": 2,
      "files": []
    },
    "summary": {
      "root": "outputs/summary",
      "file_count": 8,
      "files": []
    },
    "conditions": {
      "root": "outputs/conditions",
      "file_count": 2,
      "files": [
        {
          "path": "outputs/conditions/ph_long_table.csv",
          "file_name": "ph_long_table.csv",
          "row_count": 4568,
          "column_count": 34,
          "size_bytes": 384229,
          "sha1": "91bf83ccaa1234567890"
        },
        {
          "path": "outputs/conditions/temperature_long_table.csv",
          "file_name": "temperature_long_table.csv",
          "row_count": 4322,
          "column_count": 34,
          "size_bytes": 352118,
          "sha1": "ab12cd34ef5678901234"
        }
      ]
    }
  },
  "audits": {
    "root": "audits",
    "file_count": 9,
    "files": [
      {
        "path": "audits/business_duplicate_rows.csv",
        "file_name": "business_duplicate_rows.csv",
        "row_count": 11924,
        "column_count": 10,
        "size_bytes": 11923,
        "sha1": "1234567890abcdef1234"
      }
    ]
  },
  "workspace": {
    "raw_source_used": false,
    "external_source_used": true,
    "manual_override_used": false
  }
}
```

## 附录 B. 其他模板与示例

### B.1 `release_manifest.json` 示例

```json
{
  "release_id": "20260725-ext001",
  "run_date": "2026-07-25T14:50:00+08:00",
  "source_type": "external_source",
  "input_mode": "external_source",
  "status": "completed",
  "operator": "system",
  "software_version": "catapro_update_app_v1",
  "pipeline_mode": "incremental_update",
  "repo_root": "D:\\catapro_delivery",
  "data_root": "D:\\catapro_delivery\\.external_data",
  "notes": []
}
```

### B.2 `input_manifest.json` 示例

```json
{
  "release_id": "20260725-ext001",
  "source_type": "external_source",
  "input_root": "D:\\catapro_delivery\\.external_data\\incoming\\20260725_ext_batch_001\\external",
  "input_files": [
    {
      "relative_path": ".external_data/incoming/20260725_ext_batch_001/external/external_update_1.csv",
      "format": "csv",
      "size_bytes": 48291,
      "modified_time": "2026-07-25T13:58:12+08:00",
      "sha1": "2e7c8abf5d1234567890"
    },
    {
      "relative_path": ".external_data/incoming/20260725_ext_batch_001/external/external_update_2.xlsx",
      "format": "xlsx",
      "size_bytes": 105233,
      "modified_time": "2026-07-25T14:00:44+08:00",
      "sha1": "91bf83ccaa1234567890"
    }
  ],
  "reference_files": [
    ".external_data/database/reference/Ligands_all_final_v1.csv",
    ".external_data/database/reference/uniprot_sequence_cache_v1.csv"
  ],
  "current_baseline_root": ".external_data/database/current",
  "snapshot_used": true,
  "snapshot_path": ".external_data/database/history/snapshots/20260725-ext001-before",
  "input_file_count": 2
}
```

### B.3 `file_inventory.csv` 示例

```csv
release_id,category,subtype,relative_path,file_name,row_count,column_count,size_bytes,modified_time,sha1
20260725-ext001,manifest,run_summary.txt,manifest/run_summary.txt,run_summary.txt,0,0,812,2026-07-25T14:50:02+08:00,11111111111111111111
20260725-ext001,manifest,plan_preview.json,manifest/plan_preview.json,plan_preview.json,0,0,1398,2026-07-25T14:30:04+08:00,22222222222222222222
20260725-ext001,outputs,master,outputs/master/CataPro_kcat_master_v6_enriched.csv,CataPro_kcat_master_v6_enriched.csv,12346,34,2851934,2026-07-25T14:49:10+08:00,33333333333333333333
20260725-ext001,outputs,conditions,outputs/conditions/ph_long_table.csv,ph_long_table.csv,4568,34,384229,2026-07-25T14:49:33+08:00,44444444444444444444
20260725-ext001,audits,business_duplicate_rows.csv,audits/business_duplicate_rows.csv,business_duplicate_rows.csv,11924,10,11923,2026-07-25T14:47:51+08:00,55555555555555555555
```

### B.4 `current_switch_audit.csv` 示例

```csv
release_id,switch_time,operator,source_type,snapshot_path,output_path,status,notes
20260725-ext001,2026-07-25T15:02:10+08:00,reviewer_a,external_source,D:\catapro_delivery\.external_data\database\history\snapshots\20260725-ext001-before,D:\catapro_delivery\.external_data\releases\20260725-ext001\outputs,completed,review_passed_and_current_updated
```

### B.5 `rollback_actions.csv` 示例

```csv
rollback_release_id,rollback_time,operator,rollback_reason,problem_release_id,restored_snapshot_path,current_before_rollback_snapshot,restored_tables,status,notes
20260726-rollback001,2026-07-26T09:20:00+08:00,reviewer_b,unexpected_null_surge_after_ext_update,20260725-ext001,D:\catapro_delivery\.external_data\database\history\snapshots\20260725-ext001-before,D:\catapro_delivery\.external_data\database\history\snapshots\20260726-rollback001-before,master|merged|summary|conditions,completed,rollback_to_pre_ext001_snapshot
```

### B.6 旧版正式字段与新软件字段映射矩阵

本表只描述正式输出层与控制字段的统一语义。

| 字段 | `external_source` 映射 | `manual_override` 映射 | 规则说明 |
| --- | --- | --- | --- |
| `dataset_name` | 固定写本次来源身份或目标结果层约定值 | 默认继承目标行原值 | 正式结果字段 |
| `parameter_name` | 使用标准化后受控值 | 若 patch 到身份字段则同步重算相关键 | 受控名称，`kcat / km / kcat_km / ph / temperature` |
| `source_db` | 输入值，否则写本次来源系统 | 默认继承目标行原值 | provenance 字段，不参与正式去重键 |
| `source_release` | 输入值，否则写本次来源快照标签 | 默认继承目标行原值 | provenance 补充，不参与正式键 |
| `source_record_id` | 输入值，否则按来源定位规则生成 | 默认继承目标行原值 | 来源定位字段，不参与正式键 |
| `record_id` | 按 `measurement_uid + organism + ions` 生成正式单行 ID | `match_key_type == record_id` 时用于精准匹配；若身份字段变化则重算 | 正式结果层最终单行身份 |
| `measurement_uid` | 按 `business_key + parameter_name + value_normalized + ph + temperature` 生成 | 若 patch 到 identity 字段则重算 | 实验候选键，不是最终单行 ID |
| `ec_number` | 使用标准化后值 | 可 patch，但不参与正式去重键 | 保留字段 |
| `organism` | 使用标准化后值 | 可 patch | 不参与 `business_key / measurement_uid` 主判定，只用于冲突拦截 |
| `uniprot` | 使用标准化后值 | `business_key` 匹配时参与标准化比较 | 条目键字段 |
| `enzyme_type` | 使用标准化后值 | `business_key` 匹配时参与标准化比较 | 条目键字段 |
| `mutation` | 使用标准化后值 | `business_key` 匹配时参与标准化比较 | 条目键字段 |
| `sequence` | 使用标准化后值 | `business_key` 匹配时参与标准化比较 | 条目键字段 |
| `substrate` | 使用标准化后值 | `business_key` 匹配时参与标准化比较 | 条目键字段 |
| `smiles` | 使用标准化后值 | `business_key` 匹配时参与标准化比较 | 条目键字段 |
| `value` / `unit` | 使用标准化后值 | `field_name == value/unit` 时按 patch 更新 | 主测量值和主单位 |
| `value_normalized` | 若缺失则回填自 `value` | 身份字段变化时随 `value` 同步 | 正式实验比较值 |
| `ph` / `temperature` | 使用标准化后值 | 可 patch；属于 measurement 级 identity 字段 | 条件字段 |
| `ions` | 输入值，否则留空 | 可 patch | 不参与 `business_key / measurement_uid` 主判定，只用于冲突拦截 |
| `reaction_raw` / `commentary` / `substrate_raw` / `parse_status` / `mutation_apply_status` | 输入值，否则按规则补空或回填 | 仅当 patch 到对应字段时改写 | 非身份字段；单独修改时不应静默重算 `record_id` |

新增但不属于正式 `enriched` schema 的控制字段：

- `source`
- `source_file`
- `source_row`
- `release_id`
- `record_key`
- `business_key`
- `logical_source_type`
- `import_dedup_key`

这些控制字段只用于：

- 运行控制
- 审计追踪
- 去重定位
- 工作区 join

不允许把控制字段直接混入正式 `outputs/master` / `outputs/merged` / `outputs/conditions`。

### B.7 `external_source` 标准补充模板示例

```csv
parameter_name,ec_number,uniprot,enzyme_type,mutation,sequence,substrate,smiles,value,unit,organism,commentary,source_record_id,ph,temperature,sequence_source,parse_status,value_normalized,unit_normalized
kcat,1.1.1.1,P12345,wildtype,,MSEQUENCEEXAMPLE,glucose,C(C1C(C(C(C(O1)O)O)O)O)O,12.5,s^-1,Escherichia coli,manual_external_curation,ext_row_0001,7.4,37,uniprot,parsed,12.5,s^-1
temperature,1.1.1.1,P12345,wildtype,,MSEQUENCEEXAMPLE,glucose,C(C1C(C(C(C(O1)O)O)O)O)O,37,C,Escherichia coli,condition_supplement,ext_row_0002,7.4,37,uniprot,parsed,37,C
```

### B.8 `manual_override` 示例

```csv
operation_id,target_table,target_scope,match_key_type,record_id,record_key,uniprot,enzyme_type,mutation,sequence,substrate,smiles,field_name,old_value_expected,new_value,action,reason,approved_by,approved_at
example_replace_001,conditions,current,record_id,frid_a1b2c3d4e5f6a7b8c9d0,,,,,,,,temperature,25,37,replace,manual_review_confirmed_temperature,reviewer_a,2026-07-26T10:30:00+08:00
example_fill_blank_001,conditions,current,business_key,,,P12345,wildtype,,MSEQUENCEEXAMPLE,glucose,C(C1C(C(C(C(O1)O)O)O)O)O,ph,,7.4,fill_if_blank,fill_missing_ph_after_manual_review,reviewer_a,2026-07-26T10:35:00+08:00
example_drop_row_001,merged,current,record_id,frid_b1c2d3e4f5a6b7c8d9e0,,,,,,,,record_status,,drop_row,drop_row,duplicate_record_confirmed_by_manual_review,reviewer_c,2026-07-26T10:45:00+08:00
```

### B.9 输入字段别名映射矩阵

字段名标准化使用“去空白、转小写、仅保留字母数字”的 header 归一规则后，再做别名映射。

| 标准字段 | 允许识别的别名 |
| --- | --- |
| `record_id` | `record_id`, `formal_record_id`, `formal_id`, `formal record id` |
| `source_record_id` | `source_record_id`, `source_id`, `source record id` |
| `record_key` | `record_key`, `workspace_record_key`, `entry_id` |
| `source` | `source`, `data_source`, `dataset` |
| `source_file` | `source_file`, `file`, `filename` |
| `source_row` | `source_row`, `row`, `line_no` |
| `release_id` | `release_id`, `version`, `release` |
| `enzyme_id` | `enzyme_id`, `enzyme`, `enzyme accession`, `uniprot_id`, `uniprot` |
| `condition_type` | `condition_type`, `trait_type`, `trait`, `field_type` |
| `raw_value` | `raw_value`, `value`, `raw`, `measurement` |
| `normalized_value` | `normalized_value`, `normalized`, `normalized_measurement` |
| `raw_unit` | `raw_unit`, `unit`, `rawunit` |
| `normalized_unit` | `normalized_unit`, `std_unit` |
| `quality_flag` | `quality_flag`, `flag`, `qc_flag` |
| `condition` | `condition`, `condition_note`, `notes` |
| `species` | `species`, `organism` |
| `wildtype_mutant` | `wildtype_mutant`, `mutation_status`, `mutant`, `wt_mut` |
| `value` | `value`, `measurement`, `trait_value` |
| `unit` | `unit`, `measurement_unit` |

补充规则：

- 别名识别只解决列名归一问题，不改变字段语义
- 同一输入表若多个列同时映射到同一标准字段，必须进入 `validate` 警告或阻断
- 别名识别成功后，后续处理一律使用标准字段名
- `source_record_id` 不得作为 `record_key` 的别名自动吸收
- `row_id` 因同时可能被误解为 `record_key` 或 `source_row`，不再作为默认可识别别名

### B.10 工作区最小字段合同与条件导出前校验合同

#### B.10.1 标准化批次最小字段合同

以下字段是标准化批次进入统一 dedup 前的最小字段集合：

| 字段 | 是否必需 | 说明 |
| --- | --- | --- |
| `record_key` | 系统补齐 | 当前 release 内临时记录标识 |
| `source` | 系统补齐 | 逻辑来源身份 |
| `source_file` | 系统补齐 | 原始输入文件名或路径 |
| `source_row` | 系统补齐 | 原始输入行号或 JSON 路径 |
| `release_id` | 系统补齐 | 本次运行版本号 |
| `parameter_name` | 输入必填 | 必须已完成受控标准化 |
| `source_db` | 系统补齐 | 来源追踪字段 |
| `source_release` | 系统补齐 | 来源追踪字段 |
| `source_record_id` | 系统补齐 | 来源追踪字段 |
| `uniprot` | 证据字段 | 允许为空，但会降低自动匹配能力 |
| `enzyme_type` | 条目字段 | 允许提供 |
| `mutation` | 条目字段 | 允许提供 |
| `sequence` | 证据字段 | 允许为空，但会降低自动匹配能力 |
| `substrate` | 证据字段 | 允许为空，但会降低自动匹配能力 |
| `smiles` | 证据字段 | 允许为空，但会降低自动匹配能力 |
| `value` | 输入必填 | 原始或直接测量值 |
| `unit` | 可选输入 | 原始单位 |
| `value_normalized` | 系统补齐 | 若为空则回填自 `value` |
| `unit_normalized` | 系统补齐 | 若为空则回填自 `unit` |
| `ph` | 条件字段 | 可选输入 |
| `temperature` | 条件字段 | 可选输入 |
| `business_key` | 系统生成 | 标准化后 6 键条目键 |
| `measurement_uid` | 系统生成 | 标准化后实验候选键 |
| `record_id` | 系统生成 | 最终正式单行 ID |

自动补齐规则：

- 若缺少 `record_key`
  - 生成规则为 `<source_file_stem>:<row_number>`
- 若缺少 `source`
  - 写入本次 `source-type`
- 若缺少 `source_file`
  - 写入输入文件名
- 若缺少 `source_row`
  - 按 1 开始的行号生成
- 若缺少 `release_id`
  - 写入本次 `release_id`
- 若缺少 `value_normalized`
  - 优先使用输入的 `value_normalized`
  - 否则回退到 `value`
- `business_key` / `measurement_uid`
  - 必须按正文 10.2B 和 10.3 的显式字段规则重算
- `record_id`
  - 允许在 dedup 之前留空
  - 但进入正式 `merged` / `conditions` 前必须补齐

#### B.10.2 `ph` / `temperature` 条件导出前最小校验合同

本节不是正式 `outputs/conditions/` schema。

本节只用于：

- 工作区中间数据校验
- 条件导出前的最小完备性检查

正式 `ph_long_table.csv` 与 `temperature_long_table.csv` 的最终字段顺序，必须以正文 11.1.2 的正式 `enriched` schema 为准。

条件导出前至少应能拿到以下信息：

| 字段 | 是否必须保留 | 说明 |
| --- | --- | --- |
| `record_id` | 是 | 必须直接继承正式 merged 的正式单行 ID |
| `record_key` | 建议 | 当前 release 内的工作区定位键 |
| `business_key` | 是 | 6 键条目键 |
| `measurement_uid` | 建议 | 实验候选键 |
| `parameter_name` | 是 | 必须已受控标准化 |
| `uniprot` | 建议 | 条目键字段 |
| `enzyme_type` | 建议 | 条目键字段 |
| `mutation` | 建议 | 条目键字段 |
| `sequence` | 建议 | 条目键字段 |
| `substrate` | 建议 | 条目键字段 |
| `smiles` | 建议 | 条目键字段 |
| `value` | 建议 | 原始或直接值 |
| `value_normalized` | 建议 | 正式实验比较值 |
| `ph` | 条件表导出所需 | 正式 merged 中的 ph 字段 |
| `temperature` | 条件表导出所需 | 正式 merged 中的 temperature 字段 |
| `source` | 是 | 来源身份 |
| `source_file` | 是 | 来源文件 |
| `source_row` | 是 | 来源行号 |
| `release_id` | 是 | 生成该记录的 release |

补充规则：

- 若某次 release 的 conditions 表为空，也必须输出仅含表头的空表
- 条件导出前最小必填校验固定包括：
  - `record_id`
  - `business_key`
  - `record_key`
  - `parameter_name`
  - `source`
  - `source_file`
  - `source_row`
  - `release_id`
- 对 `ph_long_table.csv`：
  - `ph` 必须非空
- 对 `temperature_long_table.csv`：
  - `temperature` 必须非空
- 本节不允许被解释为“正式条件表只保留这些列”
