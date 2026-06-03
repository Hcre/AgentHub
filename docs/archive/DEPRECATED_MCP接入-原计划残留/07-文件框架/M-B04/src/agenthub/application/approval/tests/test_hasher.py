"""M-B04 — hasher.py 测试（含 hypothesis 属性测试）.

[文件] tests/test_hasher.py  [所属模块] M-B04  [作者] DD-M-B04-20260603
[来源] [DD-001:ADR-006 + CS §1.7]

[测试场景 1] test_compute_returns_64_hex
  断言: len(hash)==64 且全为 hex 字符
[测试场景 2] test_compute_key_order_independent
  断言: hash({"a":1,"b":2}) == hash({"b":2,"a":1})  Mock: 无
[测试场景 3] test_compute_nested_dict_key_order_independent
  断言: 嵌套 dict 子层顺序无关
[测试场景 4] test_compute_distinct_args_distinct_hash
  断言: 不同 args 哈希必不同
[测试场景 5] test_compute_with_non_serializable_raises_value_error
  断言: args 含 datetime/set → ValueError
[测试场景 6] test_compute_with_non_dict_raises_type_error
  断言: 入参为 list/str → TypeError
[测试场景 7] test_verify_hash_true_when_consistent
[测试场景 8] test_verify_hash_false_when_tampered
[测试场景 9] test_property_idempotence (hypothesis)
  断言: ∀ args, compute(args) == compute(args)  Mock: hypothesis 生成 200 例
[测试场景 10] test_property_collision_resistance (hypothesis)
  断言: 1000 随机 args 互不哈希碰撞（SHA256 强度合理近似）
[测试场景 11] test_performance_under_1ms
  断言: 1KB args 处理 < 1ms（pytest-benchmark）
"""
