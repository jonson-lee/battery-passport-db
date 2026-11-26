#!/usr/bin/env python3
"""Build data/Part4_Handover.zip from the generated Part 4 artifacts.

The package uses ASCII-only entry names for cross-platform safety, contains the
integrated snapshot, the own-table merge extract, the shared-event addon, DDL,
views, previews, data notes and helper scripts, plus SHA256SUMS.txt.

Usage:
    python scripts/build_part4_handover.py
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

README = """# Part 4 数据交接包 · 组包与维护管理

生成日期：2026-11-20（数据快照时钟 2026-11-20 11:20 +08:00）。
所有第四板块业务记录均为 synthetic（课程模拟），不代表真实企业运行事实，也不是认证安全判定。
上游公开数据：Battery Characterization Datasets（CC BY 4.0，BulyK47/battery-datasets）；
组包、维护、检查与使用决定为本项目课堂合成数据。

## 0. 先看这里：你要用哪个文件？

| 你的目的 | 用这个文件 |
|---|---|
| 直接拿到第 1–4 板块完整库（推荐） | `section4_integrated.sqlite`（23 张表 + 8 视图，外键检查为空） |
| 你已有第 1–3 板块权威整合库，需要自己合库 | 复制一份上游库，再用 `scripts/merge_section4_data.py` 合并（见下） |
| 只想快速看数据 | `preview_10_rows.html` |
| 合库后做回归验证 | `scripts/validate_section4_data.py` |

> **不要把 `section4_synthetic.sqlite` 单独当作完整数据库。**
> 它只含第四板块 7 张表，单独打开时 `PRAGMA foreign_key_check` 会报告缺
> `battery_unit` / `organization` / `ELIGIBILITY_ASSESSMENT` / `USE_PURPOSE` /
> `lifecycle_event` 等上游父表；这是与第三部分「合库」文件一致的预期行为，
> 合进含上游的库后即正常。

## 1. 文件说明

| 文件 | 说明 |
|---|---|
| `section4_integrated.sqlite` | **整合库**：第 1–3 板块 16 张表 + 第四板块 7 张表 = 23 张表，含 8 个视图与触发器；`PRAGMA foreign_key_check` 为空。上游行未被修改。 |
| `section4_synthetic.sqlite` | **合库提取文件**：只含第四板块 7 张表（与第三部分交接的「合库」口径相同）。 |
| `section4_lifecycle_event_addon.csv` | 第四板块追加到共享 `lifecycle_event` 的 23 条维护事件（UTF-8，空值为空字符串）。 |
| `section4_lifecycle_event_addon.sql` | 上述 23 条事件的 INSERT 语句。 |
| `section4_schema.sql` | 第四板块 7 张表、索引、触发器 DDL（SQLite）。 |
| `section4_views.sql` | 8 个查询/审计视图，合库后创建。 |
| `scripts/merge_section4_data.py` | **一键合库**：在含第①–③板块表的库上建表、追加共享事件、按外键顺序导入 7 张表、建视图，并自动做 FK/行数/审计检查。 |
| `scripts/validate_section4_data.py` | 独立校验脚本（72 项检查）。 |
| `scripts/generate_section4_data.py` | 重建脚本（需项目仓库布局和第③部分交接 zip，见文末）。 |
| `previews/` | 每张表 10 行 CSV 预览 + 汇总计数。 |
| `preview_10_rows.html` | 浏览器直接打开的数据预览。 |
| `SECTION4_DATA_NOTES.md` | 完整数据说明：字段映射、业务场景、统计、校验结果、接口与合库步骤（中文）。 |
| `SHA256SUMS.txt` | 全包文件校验和。 |

## 2. 一键合库（你已有第 1–3 板块整合库）

```bash
# 1) 先备份/复制你权威的第 1–3 板块整合库
cp section3_eligibility_整合库.sqlite full_1_4.sqlite

# 2) 在本包解压目录中运行（脚本会自动按外键顺序导入）
python scripts/merge_section4_data.py --target full_1_4.sqlite

# 3) 可选：独立回归校验
python scripts/validate_section4_data.py \\
  --integrated full_1_4.sqlite \\
  --own section4_synthetic.sqlite

# 4) 检查外键
sqlite3 full_1_4.sqlite "PRAGMA foreign_key_check;"   # 应输出 0 行
```

合库脚本会拒绝两种目标库：缺少第①–③板块共享表的库、已经建过第四板块表的库；
结束时自动核对 7 张表行数、`lifecycle_event = 原行数 + 23`、上游 15 张表行数不变、
4 个审计视图为空。

## 3. 数据规模

160 个电池组 / 653 条成员安装 / 175 次组装作业 / 23 次维护事件 /
175 次组级检查 / 179 次使用决定 / 175 条决定-检查证据；
另向共享 `lifecycle_event` 追加 23 条维护事件。

组包来源：第③板块 750 次 final 评估中用途为 P01–P09 的 **725 个单元**，
使用了 **638 个**（另 87 个为未组装备件）；250 个 draft 评估单元和 25 个
P10 拆解回收单元不参与组包。每条成员安装都引用 `assessment_id`，并通过触发器
校验 `status='final'`、用途 P01–P09、单元一致。

## 4. 两个必须注意的接口

1. `pack_id` 是 **TEXT（UUID v5）**，与第①板块 `lifecycle_event.battery_pack_id`
   （TEXT）对齐；可读业务编码在 `pack_code`（形如 `SIM-PACK-0001`）。
   第⑤板块租赁明细请引用 `pack_id`，展示时用 `pack_code`。
   组内 2026-11-16 汇稿里的 `integer pack_id` 与此不同，原因见 NOTES §4.2。
2. `maintenance_id` 是 **TEXT（UUID）**，与父事件 `lifecycle_event.event_id`
   完全相同（维护继承共享事件身份），不是独立整数键。

## 5. 校验与完整性

```bash
# 校验和（任选其一）
shasum -a 256 -c SHA256SUMS.txt       # macOS
sha256sum -c SHA256SUMS.txt           # Linux

# 独立校验（在解压目录中；上游未改动一项会自动跳过）
python scripts/validate_section4_data.py \\
  --integrated section4_integrated.sqlite \\
  --own section4_synthetic.sqlite
# 72/72 checks passed
```

关键结果：整合库 `foreign_key_check` 0 行；`PRAGMA integrity_check` 为 ok；
允许使用的决定全部有同组同组成检查证据；暂缓决定全部有缺失证据理由；
所有业务时间不晚于数据快照时钟。

## 6. 版本与重建

- 对齐的上游版本：第三部分交接的 `section3_eligibility_整合库.sqlite`
  （1,000 单元 / 1,000 次评估 / 1,200 条生命周期事件）。
- 若上游数据更新，请勿直接合入本包旧数据；在项目仓库中重新运行
  `python scripts/generate_section4_data.py` 后再合库。
- 重建需要 `data/Part3_Handover.zip` 与项目仓库布局；生成结果由固定 seed、
  固定 UUID 命名空间和固定模拟时钟保证可复现。
- 为避免跨平台中文文件名乱码，包内文件名统一使用 ASCII；中文说明见
  `SECTION4_DATA_NOTES.md`。
"""

ENTRIES = [
    ("README.md", None),
    ("section4_integrated.sqlite", "data/section4_integrated.sqlite"),
    ("section4_synthetic.sqlite", "data/section4_synthetic.sqlite"),
    ("section4_lifecycle_event_addon.csv", "data/section4_lifecycle_event_addon.csv"),
    ("section4_lifecycle_event_addon.sql", "sql/section4_lifecycle_event_addon.sql"),
    ("section4_schema.sql", "sql/section4_schema.sql"),
    ("section4_views.sql", "sql/section4_views.sql"),
    ("preview_10_rows.html", "data/section4_preview.html"),
    ("SECTION4_DATA_NOTES.md", "docs/2026-11-20_第四板块数据实现说明.md"),
    ("scripts/merge_section4_data.py", "scripts/merge_section4_data.py"),
    ("scripts/validate_section4_data.py", "scripts/validate_section4_data.py"),
    ("scripts/generate_section4_data.py", "scripts/generate_section4_data.py"),
]
for p in sorted((ROOT / "data" / "section4_previews").glob("*")):
    ENTRIES.append((f"previews/{p.name}", str(p.relative_to(ROOT))))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "data" / "Part4_Handover.zip"))
    args = parser.parse_args(argv)
    output = Path(args.output)
    payload = {}
    for arcname, src in ENTRIES:
        payload[arcname] = (
            README.encode("utf-8") if src is None else (ROOT / src).read_bytes()
        )
    checksums = "".join(
        f"{hashlib.sha256(payload[name]).hexdigest()}  {name}\n"
        for name, _ in sorted(ENTRIES)
    )
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Part4_Handover/README.md", payload["README.md"])
        zf.writestr("Part4_Handover/SHA256SUMS.txt", checksums)
        for arcname, _ in ENTRIES:
            if arcname == "README.md":
                continue
            zf.writestr("Part4_Handover/" + arcname, payload[arcname])
    print(f"[ok] wrote {output} ({output.stat().st_size} bytes, "
          f"{len(ENTRIES) + 1} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
