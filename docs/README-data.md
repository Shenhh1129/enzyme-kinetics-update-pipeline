`.external_data/` 不随 Git 仓库一起提交。

如果是第一次拿到这套仓库，需要先下载独立数据包，并把它解压到仓库根目录，保证最终直接存在：

```text

D:\catapro_delivery\.external_data\

```

数据包下载：

- 百度网盘链接：`https://pan.baidu.com/s/18qYrdZkas9lwjg2SPEXbYg?pwd=kqkw`
- 提取码：`kqkw`

下载并解压完成后，再按本文件下面的目录结构去检查各个子目录是否齐全。

运行文件导航：

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
