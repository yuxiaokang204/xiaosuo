"""
日志配置模块 - 统一日志格式和输出
"""
import logging
import sys
from typing import Optional


def setup_logger(
    name: str = "novel-agent",
    level: str = "INFO",
    log_to_console: bool = True,
    log_to_file: bool = False,
    log_file: str = "novel_agent.log",
) -> logging.Logger:
    """
    配置并返回一个日志记录器
    
    Args:
        name: 日志器名称
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_to_console: 是否输出到控制台
        log_to_file: 是否输出到文件
        log_file: 日志文件路径
        
    Returns:
        配置好的 logging.Logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 统一格式
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # 控制台 handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 文件 handler
    if log_to_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)  # 文件记录更详细
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError as e:
            print(f"[LOGGING] 无法创建日志文件 {log_file}: {e}")
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取已配置的日志记录器"""
    if name:
        return logging.getLogger(name)
    return logging.getLogger("novel-agent")


# 默认日志器（直接导入使用）
default_logger = setup_logger()
