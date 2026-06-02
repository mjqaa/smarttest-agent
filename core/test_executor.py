"""
测试执行器
并发执行所有测试用例，收集HTTP响应数据
"""
from __future__ import annotations
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from config.settings import REQUEST_TIMEOUT, MAX_RETRIES, CONCURRENT_WORKERS


class TestExecutor:
    def __init__(self):
        self.results: list[dict] = []

    def execute(self, test_cases: list[dict], headers: dict = None, base_url: str = None) -> list[dict]:
        """
        执行测试用例列表
        test_cases: TestGenerator.generate() 的输出
        headers: 全局请求头 (如 Authorization)
        base_url: 全局基地址 (覆盖单个用例的)
        """
        self.results = []
        global_headers = headers or {}

        with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as pool:
            futures = {}
            for i, case in enumerate(test_cases):
                future = pool.submit(self._execute_one, case, i, global_headers, base_url)
                futures[future] = i

            for future in as_completed(futures):
                result = future.result()
                self.results.append(result)

        # 按原始顺序排列
        self.results.sort(key=lambda r: r.get("index", 0))
        return self.results

    def _execute_one(self, case: dict, index: int, global_headers: dict, base_url: str = None) -> dict:
        """执行单个测试用例(含重试)"""
        url = base_url or case["url"]

        # 替换路径参数
        for pname, pval in case.get("path_params", {}).items():
            url = url.replace(f"{{{pname}}}", str(pval))

        # 合并请求头
        req_headers = {**global_headers, **(case.get("headers") or {})}
        method = case["method"]

        # 处理省略参数的特殊用例
        query_params = dict(case.get("query_params", {}))
        if case.get("_omit_param"):
            query_params.pop(case["_omit_param"], None)

        body = case.get("body")

        for attempt in range(1 + MAX_RETRIES):
            start_time = time.time()
            try:
                resp = requests.request(
                    method=method,
                    url=url,
                    headers=req_headers,
                    params=query_params if query_params else None,
                    json=body if body else None,
                    timeout=REQUEST_TIMEOUT,
                )
                elapsed_ms = round((time.time() - start_time) * 1000)

                return {
                    "index": index,
                    "case_name": case["name"],
                    "method": method,
                    "url": url,
                    "category": case.get("category", ""),
                    "status_code": resp.status_code,
                    "expected_status": case.get("expected_status", 200),
                    "passed": self._check_pass(resp.status_code, case.get("expected_status", 200)),
                    "response_body": self._safe_json(resp.text),
                    "response_headers": dict(resp.headers),
                    "elapsed_ms": elapsed_ms,
                    "attempts": attempt + 1,
                    "error": None,
                }

            except requests.exceptions.Timeout:
                elapsed_ms = round((time.time() - start_time) * 1000)
                if attempt == MAX_RETRIES:
                    return self._error_result(case, index, "请求超时", elapsed_ms)
            except requests.exceptions.ConnectionError as e:
                if attempt == MAX_RETRIES:
                    return self._error_result(case, index, f"连接失败: {e}", 0)
            except Exception as e:
                if attempt == MAX_RETRIES:
                    return self._error_result(case, index, str(e), 0)

        return self._error_result(case, index, "未知错误", 0)

    def _check_pass(self, actual: int, expected: int) -> bool:
        """判断测试是否通过"""
        # 2xx 之间互相匹配（POST 可能返回200或201）
        if 200 <= actual < 300 and 200 <= expected < 300:
            return True
        # 4xx / 5xx 精确匹配
        if (actual >= 400) and (expected >= 400):
            return actual == expected
        return actual == expected

    def _safe_json(self, text: str) -> dict | str:
        try:
            return __import__("json").loads(text)
        except Exception:
            return text[:500]  # 截断过长文本

    def _error_result(self, case: dict, index: int, error: str, elapsed_ms: int) -> dict:
        return {
            "index": index,
            "case_name": case["name"],
            "method": case["method"],
            "url": case["url"],
            "category": case.get("category", ""),
            "status_code": 0,
            "expected_status": case.get("expected_status", 200),
            "passed": False,
            "response_body": None,
            "response_headers": {},
            "elapsed_ms": elapsed_ms,
            "attempts": MAX_RETRIES + 1,
            "error": error,
        }
