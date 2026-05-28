"""错误处理 — 规范示例。

运行: python error_handling_demo.py

对比 02-coding 规范中"静默吞异常"和"宽泛捕获"反模式。
"""
import logging

# 配置日志（生产环境用 INFO，开发环境用 DEBUG）
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# --- 自定义异常（具体类型，而非泛用 Exception）---
class UserNotFoundError(Exception):
    """用户不存在。"""
    pass


class DatabaseError(Exception):
    """数据库错误。"""
    pass


class ServiceUnavailableError(Exception):
    """服务不可用。"""
    pass


# --- 模拟数据库查询 ---
def query_user(user_id: str) -> dict:
    """模拟数据库查询。"""
    if user_id == "db_down":
        raise DatabaseError("数据库连接超时")
    if user_id != "user_001":
        raise UserNotFoundError(f"用户 {user_id} 不存在")
    return {"id": user_id, "name": "张三"}


# --- ✅ 正确：具体异常类型，日志含上下文 ---
def fetch_user_correct(user_id: str) -> dict | None:
    """查询用户 — 正确做法。"""
    try:
        return query_user(user_id)
    except UserNotFoundError:
        # 已知业务异常，记录后传播
        logger.warning("用户不存在 | user_id=%s", user_id)
        raise
    except DatabaseError as e:
        # 系统异常，记录完整上下文后转换
        logger.error("查询用户失败 | user_id=%s | error=%s", user_id, e)
        raise ServiceUnavailableError("数据库服务不可用") from e


# --- ❌ 反模式：静默吞异常 ---
def fetch_user_bad(user_id: str) -> dict | None:
    """查询用户 — 错误做法（反模式演示）。"""
    try:
        return query_user(user_id)
    except Exception:
        pass  # 危险！所有异常被吞掉
    return None


# --- ❌ 反模式：宽泛捕获 ---
def fetch_user_bad2(user_id: str) -> dict | None:
    """查询用户 — 另一个反模式。"""
    try:
        return query_user(user_id)
    except Exception:
        return None  # 丢失了异常类型和上下文


if __name__ == "__main__":
    print("=== 正确做法：具体异常 + 日志上下文 ===")
    try:
        user = fetch_user_correct("user_001")
        print(f"查询成功: {user}")
    except Exception as e:
        print(f"调用方收到: {e}")

    print()
    try:
        fetch_user_correct("user_999")
    except UserNotFoundError:
        print("调用方处理：展示'用户不存在'提示")

    print()
    try:
        fetch_user_correct("db_down")
    except ServiceUnavailableError:
        print("调用方处理：展示'服务繁忙，请稍后再试'")

    print()
    print("=== 反模式演示 ===")
    print("静默吞异常结果:", fetch_user_bad("db_down"))  # None，但不知道原因
    print("宽泛捕获结果:", fetch_user_bad2("db_down"))    # None，同样无法排查
