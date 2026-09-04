<div align="middle">

**English** | [简体中文](README_zh-CN.md)

</div>

# Enzyme Activity Data Update Repository

This repository maintains the complete data update system for enzyme activity data and covers three update pipelines:

- `raw_source`
- `external_source`
- `manual_override`

It also manages:

- Update scripts and application code
- The legacy 14-step black-box pipeline
- Input validation, deduplication, condition-table export, auditing, and version switching
- The release, current, history, and workspace directory structure under `.external_data/`

If any documentation conflicts, [`docs/README-rules.md`](docs/README-rules.md) takes precedence.

## 1. Documentation

- Documentation index: [`docs/index.md`](docs/index.md)
- Rules: [`docs/README-rules.md`](docs/README-rules.md)
- Running the pipeline: [`docs/README-run.md`](docs/README-run.md)
- Scripts: [`docs/README-script.md`](docs/README-script.md)
- `.external_data/` directory structure: [`docs/README-data.md`](docs/README-data.md)

## 2. Main Repository Components

- [`src`](src)
  - Application code for the new pipeline.
  - Responsible for `plan / validate / run`, input normalization, deduplication, conditions, summary, manifest generation, and switching `current`.

- [`database_update_pipeline`](database_update_pipeline)
  - Source code for the legacy 14-step `raw_source` black-box pipeline.
  - This is the black-box code that should be maintained. Do not directly modify copies inside release workspaces.

- [`.external_data`](.external_data)
  - Root directory for runtime data.
  - Stores inputs, releases, current data, history, workspaces, production outputs, and audit records.

- [`docs`](docs)
  - Rules and supplementary documentation.

- [`tests`](tests)
  - Automated tests.

## 3. Workflow in One Sentence

1. Place the input data for the current batch in `.external_data/incoming/<batch_id>/`
2. Select the `source-type` and `release_id`
3. Run `plan`
4. Run `validate`
5. Run `run`
6. Write the results first to `.external_data/releases/<release_id>/`
7. After review and approval, switch `.external_data/database/current/`

For detailed commands, see [`docs/README-run.md`](docs/README-run.md).

## 4. Purpose of the Three Pipelines

- `raw_source`
  - Official raw update source.
  - Uses the legacy black-box pipeline for a full rebuild.

- `external_source`
  - Standard supplementary data from external sources.
  - Uses normalization, deduplication, conditions export, and production-output rebuilding.

- `manual_override`
  - Manually approved patch instructions.
  - Used for precise modifications to production results.

## 5. Two Most Important Maintenance Rules

- When modifying logic in the new pipeline, update [`src/catapro_update_app`](src/catapro_update_app) first.
- When modifying the `raw_source` black-box logic, update [`database_update_pipeline`](database_update_pipeline). Do not directly modify runtime copies under `.external_data/releases/.../workspace/...`.

## 6. About `.external_data`

By default, large files, raw data, intermediate runtime results, production outputs, audit records, and historical records are stored under `.external_data/` rather than committed to Git.

If the repository does not contain `.external_data/`, first download the data package from Baidu Netdisk and extract it into the repository root so that the final directory structure is:

```text
D:\catapro_delivery\
├─ src\
├─ docs\
├─ database_update_pipeline\
└─ .external_data\
```

Data package download information:

- Baidu Netdisk link: `https://pan.baidu.com/s/18qYrdZkas9lwjg2SPEXbYg?pwd=kqkw`
- Extraction code: `kqkw`

The repository is essentially divided into two layers:

- Git repository layer: code, documentation, tests, and configuration
- Runtime data layer: inputs, releases, current data, and history under `.external_data/`

For the detailed directory structure, see [`docs/README-data.md`](docs/README-data.md).

## 7. License

The source code in this repository is licensed under the [Apache License 2.0](LICENSE), unless otherwise stated.

The license does **not** automatically apply to third-party datasets, raw source data, or other externally obtained materials stored under `.external_data/`. Such materials remain subject to the terms, licenses, and usage restrictions of their original providers.
