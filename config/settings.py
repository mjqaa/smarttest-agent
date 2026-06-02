"""
SmartTest Agent — 配置中心
所有可调参数集中管理，方便修改
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---- LLM 配置 ----
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEFAULT_LLM = os.getenv("DEFAULT_LLM", "qwen")  # qwen | deepseek

# 千问 API
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = "qwen-plus"  # plus 性价比高，max 效果最好

# DeepSeek API (可选)
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# ---- 测试执行配置 ----
REQUEST_TIMEOUT = 30       # 单次请求超时(秒)
MAX_RETRIES = 2             # 失败重试次数
CONCURRENT_WORKERS = 5      # 并发执行数
RESPONSE_TIME_THRESHOLD = 5000  # 响应时间告警阈值(毫秒)

# ---- 报告配置 ----
REPORT_DIR = "test_reports"  # 报告输出目录
