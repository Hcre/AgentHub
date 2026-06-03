"""K4TestCorpus ORM 模型 - M-D01.

[文件路径] src/agenthub/data/metadata/models/k4_test_corpus.py
[文件职责] 映射 PG 表 k4_test_corpus（K4 200 样本校准结果）
[所属模块] M-D01 Metadata Store
[关联设计规范] [DD-001:DS-016 + DE-021 + MD:M-C02]
[功能描述]
  功能1: 定义 K4TestCorpus 类
  功能2: 字段 id / rule_set_id (FK) / sample_count (200) / fpr (NUMERIC(5,4)) / calibrated_at
[依赖关系]
  依赖文件: ./base.py
  被依赖文件: ../repositories/k4_test_corpus.py
[注意事项]
  注意1: fpr (false positive rate) 用 NUMERIC 而非 FLOAT，避免浮点误差
  注意2: 校准触发由 M-C02 CorpusCalibrator 控制，本模块仅持久化
[代码风格] 遵循 [DD-001:CS-MCP §1 + §2]
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-D01 - 初始注释框架创建
[作者] DD-M-D01-20260603
[来源标注] [DD-001:DS-016 + DE-021]
"""

# ============================================================
# [类名] K4TestCorpus
# [职责] 映射 k4_test_corpus 表
# [属性] id / rule_set_id (FK) / sample_count / fpr / calibrated_at
# [来源标注] [DD-001:DS-016]
# ============================================================
