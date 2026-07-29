# CataPro 更新仓库说明

该仓库用于维护 CataPro 的整套数据更新体系，覆盖三条链路：

- `raw_source`
- `external_source`
- `manual_override`

同时管理：

- 更新脚本和应用代码
- 旧黑盒 14 步链路
- 输入校验、去重、条件表导出、审计和版本切换
- `.external_data/` 下的 release、current、history、workspace 目录体系

如果文档之间有冲突，以 [`docs/README-rules.md`](docs/README-rules.md) 为准。

## 1. 文档说明

- 文档导航页：[`docs/index.md`](docs/index.md)
- 规则：[`docs/README-rules.md`](docs/README-rules.md)
- 运行：[`docs/README-run.md`](docs/README-run.md)
- 脚本：[`docs/README-script.md`](docs/README-script.md)
- `.external_data/` 目录结构：[`docs/README-data.md`](docs/README-data.md)

## 2. 仓库里主要有什么

- [`src`](src)
  - 新链路应用代码。
  - 负责 `plan / validate / run`、输入标准化、去重、conditions、summary、manifest、current 切换。
- [`database_update_pipeline`](database_update_pipeline)
  - `raw_source` 旧 14 步黑盒源码。
  - 这里才是应维护的黑盒代码，release 工作区里的副本不要直接改。
- [`.external_data`](.external_data)      
  - 运行数据根目录。
  - 放输入、release、current、history、workspace、正式输出和审计。
- [`docs`](docs)
  - 规则或补充文档。
- [`tests`](tests)
  - 自动化测试。

## 3. 一句话流程

1. 把本次输入放进 `.external_data/incoming/<batch_id>/`
2. 选定 `source-type` 和 `release_id`
3. 执行 `plan`
4. 执行 `validate`
5. 执行 `run`
6. 结果先写进 `.external_data/releases/<release_id>/`
7. 审核通过后再切换 `.external_data/database/current/`

具体运行命令看 [`docs/README-run.md`](docs/README-run.md)。

## 4. 三条链路的定位

- `raw_source`
  - 官方原始更新源。
  - 走旧黑盒全量重建。
- `external_source`
  - 普通外部补充数据。
  - 走标准化、去重、conditions 导出和正式输出重建。
- `manual_override`
  - 人工审批后的 patch 指令。
  - 用于精准修改正式结果。

## 5. 维护时最重要的两点

- 改新链路逻辑时，优先改 [`src/catapro_update_app`](src/catapro_update_app)
- 改 `raw_source` 黑盒逻辑时，改 [`database_update_pipeline`](database_update_pipeline)，不要直接改 `.external_data/releases/.../workspace/...` 里的运行副本

## 6. 关于 `.external_data`

默认把大文件、原始数据、运行中间结果、正式输出、审计和历史记录都放在 `.external_data/` 下，而不是放进 Git。

如果仓库里没有 `.external_data/`，请先从百度网盘下载数据包，再解压到仓库根目录，保证最终目录结构为：

```text
D:\catapro_delivery\
├─ src\
├─ docs\
├─ database_update_pipeline\
└─ .external_data\
```

数据包下载信息：

- 百度网盘链接：`https://pan.baidu.com/s/18qYrdZkas9lwjg2SPEXbYg?pwd=kqkw`
- 提取码：`kqkw`

仓库本质上分成两层：

- Git 仓库层：代码、文档、测试、配置
- 数据运行层：`.external_data/` 下的输入、release、current、history

详细目录展开看 [`docs/README-data.md`](docs/README-data.md)。
