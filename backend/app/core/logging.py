"""结构化日志配置。"""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # 降噪：第三方库
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
