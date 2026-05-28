"""安全编码 — 规范示例。

运行: python security_demo.py

对应 02-coding 规范中的安全章节。
"""
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# === 1. 密钥管理：环境变量 ===

# ❌ 反模式：硬编码
# API_KEY = "sk-abc123def456"

# ✅ 正例：从环境变量读取
API_KEY = os.environ.get("API_KEY", "your-api-key-here")


# === 2. SQL 注入防护：参数化查询 ===

def query_user_by_id_safe(user_id: str) -> str:
    """✅ 参数化查询 — SQL 与数据分离。"""
    # 实际项目中：cursor.execute("SELECT * FROM users WHERE id = ?", [user_id])
    return f"SELECT * FROM users WHERE id = ? (params: [{user_id}])"


def query_user_by_id_unsafe(user_id: str) -> str:
    """❌ 字符串拼接 — SQL 注入风险（仅演示）。"""
    # 攻击者输入: 1; DROP TABLE users; --
    return f"SELECT * FROM users WHERE id = {user_id}"


# === 3. 输入校验：白名单优先 ===

VALID_STATUSES = {"pending", "paid", "shipped", "completed", "cancelled"}


def filter_orders(status: str) -> list:
    """✅ 白名单校验 — 只接受已知合法值。"""
    if status not in VALID_STATUSES:
        raise ValueError(f"非法订单状态: {status}，允许: {VALID_STATUSES}")
    return [f"order with status={status}"]


# === 4. 日志安全：脱敏 ===

def mask_phone(phone: str) -> str:
    """手机号脱敏：138****1234"""
    if len(phone) >= 7:
        return phone[:3] + "****" + phone[-4:]
    return phone


def log_user_action(user_id: str, phone: str, action: str):
    """✅ 日志脱敏 — 不输出完整手机号。"""
    logger.info("用户操作 | user_id=%s | phone=%s | action=%s",
                user_id, mask_phone(phone), action)


if __name__ == "__main__":
    # 1. 密钥
    logger.info("API_KEY: %s", API_KEY[:10] + "..." if len(API_KEY) > 10 else API_KEY)
    logger.info("提示: 设置环境变量 export API_KEY=your-real-key")

    # 2. SQL 注入对比
    logger.info("安全查询: %s", query_user_by_id_safe("user_001"))
    logger.info("危险查询: %s", query_user_by_id_unsafe("1; DROP TABLE users; --"))

    # 3. 白名单校验
    try:
        logger.info("合法状态: %s", filter_orders("pending"))
        filter_orders("hacked_status")
    except ValueError as e:
        logger.info("拦截: %s", e)

    # 4. 日志脱敏
    log_user_action("user_001", "13812345678", "登录")
