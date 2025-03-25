import sys
from loguru import logger
import os

# 创建logs目录
if not os.path.exists('logs'):
    os.makedirs('logs')

# 配置日志
logger.remove()  # 移除默认的处理器

# 添加控制台输出
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# 添加文件输出
logger.add(
    "logs/backtest_{time:YYYY-MM-DD}.log",
    rotation="00:00",  # 每天午夜轮换
    retention="30 days",  # 保留30天
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    encoding="utf-8"
) 