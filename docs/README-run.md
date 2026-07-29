# 运行说明

## 0. 先进入仓库

在仓库根目录执行。

```powershell
cd D:\catapro_delivery
```

## 1. 准备环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

安装后优先用：

```powershell
catapro-update
```

如果不想安装，也可以直接：

```powershell
python -m catapro_update_app.cli.main
```

## 2. 放输入

三种输入模板要求和模板示例见 [`README-rules.md`](README-rules.md) 的 4.2 模板层和附录B。

输入统一放进 `.external_data\incoming\<batch_id>\`。

- `raw_source` 放到 `raw`
- `external_source` 放到 `external`
- `manual_override` 放到 `manual_override`

示例：

```powershell
.external_data\incoming\20260729_raw_batch_001\raw
.external_data\incoming\20260729_ext_batch_001\external
.external_data\incoming\20260729_manual_batch_001\manual_override
```

## 3. 运行

`run` 会自动先从 `.external_data\database\current\` 生成 snapshot，再写本次 release，不需要手工复制 `current`。

### 3.1 `raw_source`

```powershell
$inputPath = ".\.external_data\incoming\20260729_raw_batch_001\raw"
catapro-update plan --source-type raw_source --input-path $inputPath --release-id 20260729-raw001 --data-root .\.external_data --repo-root .
catapro-update validate --source-type raw_source --input-path $inputPath --release-id 20260729-raw001 --data-root .\.external_data --repo-root .
catapro-update run --source-type raw_source --input-path $inputPath --release-id 20260729-raw001 --data-root .\.external_data --repo-root .
```

这条链路会走黑盒 14 步，工作区副本落在：

```text
.external_data\releases\20260729-raw001\workspace\raw_source\database_update_pipeline\
```

### 3.2 `external_source`

```powershell
$inputPath = ".\.external_data\incoming\20260729_ext_batch_001\external"
catapro-update plan --source-type external_source --input-path $inputPath --release-id 20260729-ext001 --data-root .\.external_data --repo-root .
catapro-update validate --source-type external_source --input-path $inputPath --release-id 20260729-ext001 --data-root .\.external_data --repo-root .
catapro-update run --source-type external_source --input-path $inputPath --release-id 20260729-ext001 --data-root .\.external_data --repo-root .
```

这条链路会做标准化、去重、conditions 导出，再写正式输出。

### 3.3 `manual_override`

```powershell
$inputPath = ".\.external_data\incoming\20260729_manual_batch_001\manual_override"
catapro-update plan --source-type manual_override --input-path $inputPath --release-id 20260729-manual001 --data-root .\.external_data --repo-root .
catapro-update validate --source-type manual_override --input-path $inputPath --release-id 20260729-manual001 --data-root .\.external_data --repo-root .
catapro-update run --source-type manual_override --input-path $inputPath --release-id 20260729-manual001 --data-root .\.external_data --repo-root .
```

这条链路是 patch 流，只接受修正规则模板。

## 4. 没装 `catapro-update` 时怎么跑

直接用下面这个入口：

```powershell
python -m catapro_update_app.cli.main
```

### 4.1 `raw_source`

```powershell
$inputPath = ".\.external_data\incoming\20260729_raw_batch_001\raw"
python -m catapro_update_app.cli.main plan --source-type raw_source --input-path $inputPath --release-id 20260729-raw001 --data-root .\.external_data --repo-root .
python -m catapro_update_app.cli.main validate --source-type raw_source --input-path $inputPath --release-id 20260729-raw001 --data-root .\.external_data --repo-root .
python -m catapro_update_app.cli.main run --source-type raw_source --input-path $inputPath --release-id 20260729-raw001 --data-root .\.external_data --repo-root .
```

### 4.2 `external_source`

```powershell
$inputPath = ".\.external_data\incoming\20260729_ext_batch_001\external"
python -m catapro_update_app.cli.main plan --source-type external_source --input-path $inputPath --release-id 20260729-ext001 --data-root .\.external_data --repo-root .
python -m catapro_update_app.cli.main validate --source-type external_source --input-path $inputPath --release-id 20260729-ext001 --data-root .\.external_data --repo-root .
python -m catapro_update_app.cli.main run --source-type external_source --input-path $inputPath --release-id 20260729-ext001 --data-root .\.external_data --repo-root .
```

### 4.3 `manual_override`

```powershell
$inputPath = ".\.external_data\incoming\20260729_manual_batch_001\manual_override"
python -m catapro_update_app.cli.main plan --source-type manual_override --input-path $inputPath --release-id 20260729-manual001 --data-root .\.external_data --repo-root .
python -m catapro_update_app.cli.main validate --source-type manual_override --input-path $inputPath --release-id 20260729-manual001 --data-root .\.external_data --repo-root .
python -m catapro_update_app.cli.main run --source-type manual_override --input-path $inputPath --release-id 20260729-manual001 --data-root .\.external_data --repo-root .
```

## 5. 结果

- 本次 release：`.external_data\releases\<release_id>\`
- 正式结果：`.external_data\releases\<release_id>\outputs\`
- 审计：`.external_data\releases\<release_id>\audits\`
- 计划和校验报告：`.external_data\releases\<release_id>\manifest\`
- 过程文件：`.external_data\releases\<release_id>\workspace\`
- 当前生效版本：`.external_data\database\current\`
- 快照：`.external_data\database\history\snapshots\<release_id>-before\`

`run` 成功后，审核通过才会自动切换 `current`。

## 6. 常用检查

```powershell
Get-ChildItem .\.external_data\releases\<release_id>\
Get-ChildItem .\.external_data\database\current\
```

如果 `validate` 没过，就先停，不要直接跑 `run`。
