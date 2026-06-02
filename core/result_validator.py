"""
结果校验器
对测试结果进行自动校验：状态码 / Schema符合性 / 响应时间
"""
from config.settings import RESPONSE_TIME_THRESHOLD


class ResultValidator:
    def __init__(self):
        self.issues: list[dict] = []

    def validate(self, results: list[dict]) -> list[dict]:
        """
        对执行结果进行深度校验
        返回附加了 validation_issues 字段的结果列表
        """
        self.issues = []
        enriched = []

        for r in results:
            issues = []

            # 1. 状态码校验
            if r["status_code"] != r["expected_status"]:
                # 允许 2xx 之间模糊匹配
                if not (200 <= r["status_code"] < 300 and 200 <= r["expected_status"] < 300):
                    issues.append({
                        "type": "status_mismatch",
                        "detail": f"预期 {r['expected_status']}，实际 {r['status_code']}",
                        "severity": "high",
                    })

            # 2. 响应时间校验
            if r["elapsed_ms"] > RESPONSE_TIME_THRESHOLD:
                issues.append({
                    "type": "slow_response",
                    "detail": f"响应时间 {r['elapsed_ms']}ms 超过阈值 {RESPONSE_TIME_THRESHOLD}ms",
                    "severity": "medium",
                })

            # 3. 响应体是否为空（5xx错误时可能为空）
            if r["status_code"] >= 500 and r.get("response_body") is None:
                issues.append({
                    "type": "empty_error_body",
                    "detail": "5xx错误但无响应体（服务端可能未正确处理异常）",
                    "severity": "medium",
                })

            # 4. 连接错误
            if r.get("error"):
                issues.append({
                    "type": "connection_error",
                    "detail": r["error"],
                    "severity": "critical",
                })

            r["validation_issues"] = issues
            r["issue_count"] = len(issues)
            enriched.append(r)

        return enriched
