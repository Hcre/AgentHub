# 工作日志：修复 worklog 检查逻辑

- **谁**: 黎
- **日期**: 2026-05-23
- **分支**: fix/agenthub/worklog-per-push

## 目标
修复 check_worklog.py：每次 push 有 diff 就必须更新自己的 worklog，而不是一天写一次就混过去。

## 产出
- [x] check_worklog.py 重写：基于 git diff 检查推送内容中是否含 worklog
- [x] STATUS.md 新增 Git用户名-目录映射表
- [x] UTF-8 编码修复（Windows GBK 兼容）
- [x] 测试验证：无日志被拦截，有日志通过

## 给下一位的交接
> check_worklog.py 现在按 push 粒度检查，每次有代码 push 必须附带 worklog 更新。
> 新成员加入时需在 STATUS.md 的 Git映射表 中加一行。
