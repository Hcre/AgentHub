"""命名规范 — 反模式示例。

对比 naming_good.py 查看正确做法。
"""

# ❌ 模糊命名
def process(d):
    return d[0] + d[1]


# ❌ 缩写到不可读
def calc_usr_sc(u, s):
    return u * s / 100


# ❌ 魔法数字
def is_adult(age):
    return age >= 18  # 18 是什么意思？法定年龄？会员年龄？


# ❌ 布尔变量命名不清晰
flag = True
status = 1
mode = "edit"


# ❌ 不统一的命名风格
user_name = "张三"
UserAge = 28
useraddress = "北京"


if __name__ == "__main__":
    print("查看 naming_good.py 了解正确做法")
