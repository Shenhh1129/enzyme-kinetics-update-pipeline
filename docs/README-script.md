# 脚本地图

本文只讲两件事：想做某个改动时该去哪里找脚本，以及 `.external_data` 里现有脚本副本分别做什么。

[`README-rules.md`](README-rules.md) 负责规则，本文只负责找脚本和认目录。

## 1. 总导航

- 想看入口命令和整条更新怎么编排：[`src/catapro_update_app/cli/main.py`](../src/catapro_update_app/cli/main.py)、[`src/catapro_update_app/pipeline/runner.py`](../src/catapro_update_app/pipeline/runner.py)
- 想改新链路代码：看 [`src/catapro_update_app`](../src/catapro_update_app)
- 想改 `raw_source` 黑盒每一步实际逻辑：看 [`database_update_pipeline`](../database_update_pipeline) 下各步的 `script/*.py`
- 想确认规则和目录约束：看 [`README-rules.md`](README-rules.md)

真正要改源码时，优先改仓库里的 `src/` 和 `database_update_pipeline/`，不要直接把 `.external_data/releases/.../workspace/...` 里的副本当成源码改。

## 2. `src` 脚本说明

`src/catapro_update_app/` 

- `cli/`
  - `main.py`：命令行主入口，解析 `plan / validate / run` 和公共参数。
  - `__main__.py`：支持 `python -m catapro_update_app` 风格启动。
- `config/`
  - `defaults.py`：默认仓库根目录、默认 `.external_data` 根目录。
  - `settings.py`：集中定义 `AppPaths`、`RunConfig`，负责 release/current/history/workspace 各路径计算。
- `io/`
  - `loaders.py`：发现输入文件、识别格式、读取文件基本信息。
  - `paths.py`：目录创建、路径状态检查等通用路径工具。
- `pipeline/`
  - `runner.py`：总编排入口，负责 plan、validate、run、snapshot、manifest、current 切换。
  - `legacy.py`：`raw_source` 黑盒封装层，负责同步黑盒源码到 release 工作区并顺序执行 14 步脚本。
  - `importer.py`：`external_source` 和 `manual_override` 的输入标准化。
  - `formal.py`：正式字段、空值标准化、业务键、`measurement_uid`、`record_id` 等核心规则。
  - `deduplicate.py`：导入级去重、业务去重、survivor 选择、test leakage 过滤、审计文件输出。
  - `conditions.py`：条件长表导出和 conditions 历史记录追加。
  - `summary_outputs.py`：summary 结果整理和输出。
- `reports/`
  - `manifest.py`：写各类 manifest、文件摘要、行列统计。
  - `summary.py`：把 plan/validate/dedup/conditions 等结果渲染成终端可读文本。
- `rules/`
  - `policy.py`：`source_type`、`update_mode`、策略枚举。
  - `registry.py`：固定字段、固定文件名、允许枚举、输出文件定义。
  - `mapping.py`：字段别名和表头归一化映射。
  - `validation.py`：输入校验规则。
  - `harmonize.py`：输入画像和字段对齐辅助规则。
  - `stages.py`：黑盒 14 步的阶段定义。

## 3. 黑盒 `database_update_pipeline` 脚本说明

`database_update_pipeline/` 是 `raw_source`  14 步黑盒的仓库源码位置。这里才是应当修改的地方，release 工作区里的副本只是运行时拷贝，不要直接改。

- `database_update_pipeline/01_new_raw/script/`
  - `rebuild_brenda_raw.py`：重建 BRENDA 原始表。
  - `rebuild_sabio_from_tsv.py`：重建 SABIO 原始表。
  - `parse_utils.py`：原始解析、清洗、归一化辅助函数。
- `database_update_pipeline/02_enrich+mutation/script/`
  - `enrich_and_mutate_sabio_tsv.py`：补充信息和 mutation 处理总入口。
  - `local_enrich.py`：本地补全序列、注释、关联字段。
  - `mutant_sequence_rebuild.py`：重建突变序列。
- `database_update_pipeline/03_subres/script/`
  - `sabio_tsv_substrate_resolve.py`：解析和拆解 substrate。
- `database_update_pipeline/04_QC/script/`
  - `build_raw_qc.py`：原始层 QC。
- `database_update_pipeline/05_qc_standardize/script/`
  - `standardize_raw_qc.py`：把 QC 后字段标准化给后续步骤使用。
- `database_update_pipeline/06_backfill_seq/6A_local_seqfill/script/`
  - `backfill_sequence_post_standardized.py`：标准化后做本地序列回填。
- `database_update_pipeline/06_backfill_seq/6B_UniProt_seq_cache/script/`
  - `uniprot_sequence_cache_build.py`：构建 UniProt 序列缓存。
- `database_update_pipeline/06_backfill_seq/6C_Uniprot_cache/script/`
  - `backfill_sequence_with_uniprot_cache.py`：用 UniProt 缓存继续回填序列。
- `database_update_pipeline/07_cata_updata/script/`
  - `export_catapro_update_v2.py`：导出 CataPro 更新表。
- `database_update_pipeline/08_cata_master/script/`
  - `build_catapro_master_v2.py`：生成 CataPro master。
- `database_update_pipeline/09_external_master/9A_ex_master/script/`
  - `build_external_masters.py`：生成外部 master。
  - `parse_utils.py`：外部 master 解析辅助函数。
- `database_update_pipeline/09_external_master/9B_SKID_seqfill/script/`
  - `backfill_skid_sequence_with_uniprot_cache.py`：给 SKiD 做序列回填。
- `database_update_pipeline/10_mut_status_repair/script/`
  - `repair_dlkcat_mutation_status_v2.py`：修复 DLKcat mutation 状态。
  - `repair_skid_mutation_status_v2.py`：修复 SKiD mutation 状态。
- `database_update_pipeline/11_merged_canonical_pool/candidate_pool/script/`
  - `build_merged_training_v2.py`：构建候选 merged 池。
- `database_update_pipeline/11_merged_canonical_pool/dedup-split/script/`
  - `final_dedup_and_split_v2.py`：做最终去重和拆分。
- `database_update_pipeline/12_status_fix/script/`
  - `export_final_enriched_v6_statusfixed_all.py`：导出 status-fixed 最终数据。
- `database_update_pipeline/13_final_data/script/`
  - `export_masters_merges_enriched_v6.py`：导出最终 master、merged 和条件长表。
- `database_update_pipeline/14_final_docs/conditions/script/`
  - `build_conditions_v6.py`：生成 conditions 结果。
- `database_update_pipeline/14_final_docs/drop/script/`
  - `build_dropped_v6.py`：生成 drop / 审计辅助结果。
- `database_update_pipeline/14_final_docs/summary/script/`
  - `build_summary_v6.py`：生成 summary 报告和汇总表。
