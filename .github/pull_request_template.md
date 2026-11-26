## 关联

Closes #

## 改了什么

-

## 怎么验证

- [ ] 空库执行 `psql -v ON_ERROR_STOP=1 -f sql/postgres/00_schema.sql` 通过
- [ ] `python scripts/pg_validate.py` 全绿（数据/约束类 PR 必填）
- [ ] 截图 / `EXPLAIN` / 行数对比已附在 PR 或 Issue

## 风险与回滚

-
