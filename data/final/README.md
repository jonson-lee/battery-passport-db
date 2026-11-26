# 全组合库交付物（2026-11-22）

本目录是第①–⑤板块合并后的**最终交付物**，来自 `Project/合图与数据说明/final_integration/`。
与 `data/section4_integrated.sqlite`（23 表，第①–④板块）不同，这里是 **27 表**的完整库，含第⑤板块的项目与租赁表。

| 文件 | 内容 |
|---|---|
| `IBA6151_Integrated.sqlite` | 27 表、14 视图、44 触发器、59 索引；SQLite 交付快照 |
| `Global_Integrated_ERD.pdf` / `.png` | 全局 ER/EER 图（矢量 / 位图） |
| `Global_Integrated_ERD.drawio` | 可编辑图源 |
| `System_Overview_and_Database_Integration.docx` | 系统说明与合库说明（源文件） |
| `System_Overview_and_Database_Integration_ZH.pdf` | 中文版 |
| `System_Overview_and_Database_Integration_EN.pdf` | 英文版 |

**用途**

- 数据事实：报告与演示中的行数、键值、业务规则均以此库为准。
- 迁移基线：PostgreSQL 实施按本库的 27 表结构改写，见 [开发计划](../../docs/DEVELOPMENT_PLAN.md) 附录 A。
- 止损兜底：若 PG 迁移未在 11/30 门禁前跑通，本库冻结为正式交付库。

**注意**

- 库内业务记录均为合成数据（`data_origin = 'synthetic'`），电池单元与曲线来自公开数据（CC BY 4.0），不得表述为真实企业观测。
- 12 MB 的 `Global_Integrated_ERD.svg` 未入库（与 PDF 内容重复且体积大），需要时从源目录重新导出。
