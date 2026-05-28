# 测试规范示例

> **👤 人类参考** | 对应规范：`conventions/05-testing_测试规范.md`
> 依赖：`pip install pytest` | 运行：`pytest test_discount.py -v`

## 示例列表

| 文件 | 对应规范章节 | 运行 |
|------|------------|------|
| `discount.py` | 被测代码（纯业务逻辑） | - |
| `test_discount.py` | AAA 模式 / 命名规范 / 边界覆盖 / Mock 策略 | `pytest test_discount.py -v` |
| `pytest.ini` | §二 覆盖率门禁（`--cov-fail-under=80`） | `pip install pytest-cov && pytest` |
