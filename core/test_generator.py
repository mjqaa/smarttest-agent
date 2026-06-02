"""
LLM 驱动的测试用例生成器
对每个API端点生成5类用例: 正向 / 边界 / 缺参 / 类型错误 / 鉴权失败
"""
from __future__ import annotations
import json
import requests
from config.settings import (
    DASHSCOPE_API_KEY, DEEPSEEK_API_KEY, DEFAULT_LLM,
    QWEN_API_URL, QWEN_MODEL, DEEPSEEK_API_URL, DEEPSEEK_MODEL,
)


class TestGenerator:
    def __init__(self, llm: str = None):
        self.llm = llm or DEFAULT_LLM

    # ---- 公开方法 ----

    def generate(self, endpoint: dict) -> list[dict]:
        """
        为一个端点生成测试用例列表
        返回: [{"name": "用例名", "method": "GET", "url": "...", "headers": {}, "body": {}, "expected_status": 200}, ...]
        """
        # 1. 先生成规则驱动的确定性用例（快速、可靠）
        cases = []
        cases.extend(self._positive_cases(endpoint))
        cases.extend(self._boundary_cases(endpoint))
        cases.extend(self._missing_param_cases(endpoint))
        cases.extend(self._type_error_cases(endpoint))
        cases.extend(self._auth_failure_cases(endpoint))

        # 2. 再用LLM增强补充智能用例（覆盖规则难以发现的边界）
        try:
            llm_cases = self._llm_enhance(endpoint)
            cases.extend(llm_cases)
        except Exception:
            pass  # LLM不可用时静默降级，基础用例仍然有效

        # 去重
        seen = set()
        unique = []
        for c in cases:
            key = (c["name"], c.get("body_hash", ""))
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique

    # ---- 确定性用例生成（不依赖LLM） ----

    def _positive_cases(self, ep: dict) -> list[dict]:
        """正向用例：正常参数，预期成功"""
        params = self._build_default_params(ep["parameters"], ep.get("request_body"))
        case = {
            "name": f"[正向] {ep['method']} {ep['path']} — 正常请求",
            "method": ep["method"],
            "url": ep["full_url"],
            "headers": {"Content-Type": "application/json"},
            "query_params": params.get("query", {}),
            "path_params": params.get("path", {}),
            "body": params.get("body", {}),
            "expected_status": self._guess_success_status(ep),
            "category": "正向用例",
        }
        return [case]

    def _boundary_cases(self, ep: dict) -> list[dict]:
        """边界值用例"""
        cases = []
        for param in ep["parameters"]:
            ptype = param.get("type", "string")
            pname = param["name"]
            pin = param["in"]

            if ptype == "string":
                # 超长字符串
                long_val = "A" * 5000
                cases.append(self._make_param_variant(ep, pname, pin, long_val, f"边界值 — {pname}=超长字符串(5000字符)"))

            elif ptype in ("integer", "number"):
                # 极大值 / 负数 / 零
                for val, desc in [(999999999, "极大值"), (-1, "负数"), (0, "零")]:
                    cases.append(self._make_param_variant(ep, pname, pin, val, f"边界值 — {pname}={desc}"))

        # 空请求体
        if ep.get("request_body") and ep["request_body"].get("required"):
            cases.append({
                "name": f"[边界] {ep['method']} {ep['path']} — 空请求体",
                "method": ep["method"],
                "url": ep["full_url"],
                "headers": {"Content-Type": "application/json"},
                "query_params": {},
                "body": {},
                "expected_status": 400,
                "category": "边界值",
            })

        return cases

    def _missing_param_cases(self, ep: dict) -> list[dict]:
        """缺失必填参数用例"""
        cases = []
        required_params = [p for p in ep["parameters"] if p.get("required")]
        for param in required_params:
            cases.append({
                "name": f"[缺参] {ep['method']} {ep['path']} — 缺少 {param['name']}",
                "method": ep["method"],
                "url": ep["full_url"],
                "headers": {"Content-Type": "application/json"},
                "query_params": {},
                "body": {},
                "expected_status": 400,
                "category": "缺失必填参数",
                "_omit_param": param["name"],
            })
        return cases

    def _type_error_cases(self, ep: dict) -> list[dict]:
        """类型错误用例"""
        cases = []
        for param in ep["parameters"]:
            ptype = param.get("type", "string")
            pname = param["name"]
            pin = param["in"]

            wrong_val = None
            if ptype in ("integer", "number"):
                wrong_val = "not_a_number"
            elif ptype == "boolean":
                wrong_val = "not_bool"
            elif ptype == "array":
                wrong_val = "not_an_array"

            if wrong_val is not None:
                cases.append(self._make_param_variant(ep, pname, pin, wrong_val, f"类型错误 — {pname}=字符串(预期{ptype})", 400))

        return cases

    def _auth_failure_cases(self, ep: dict) -> list[dict]:
        """鉴权失败用例"""
        return [{
            "name": f"[鉴权] {ep['method']} {ep['path']} — 无Token",
            "method": ep["method"],
            "url": ep["full_url"],
            "headers": {"Content-Type": "application/json"},  # 不带 Authorization
            "query_params": {},
            "body": {},
            "expected_status": 401,  # 也可能是403
            "category": "鉴权失败",
        }]

    # ---- LLM智能增强 ----

    def _llm_enhance(self, ep: dict) -> list[dict]:
        """调用大模型生成补充用例"""
        prompt = self._build_prompt(ep)

        if self.llm == "deepseek":
            response = self._call_deepseek(prompt)
        else:
            response = self._call_qwen(prompt)

        return self._parse_llm_response(response, ep)

    def _build_prompt(self, ep: dict) -> str:
        return f"""你是一个资深测试工程师。请为以下API接口设计2-3个高价值的额外测试用例，
这些用例应该覆盖规则生成器难以发现的边界条件和业务逻辑漏洞。

API信息:
- 方法: {ep['method']}
- 路径: {ep['path']}
- 描述: {ep.get('summary', '无')}
- 参数: {json.dumps(ep['parameters'], ensure_ascii=False)}
- 请求体: {json.dumps(ep.get('request_body', {}), ensure_ascii=False)}
- 预期响应: {json.dumps(ep.get('responses', []), ensure_ascii=False)[:500]}

请严格按以下JSON格式回复（只返回JSON数组，不要其他内容）:
[
  {{
    "name": "用例名称(中文)",
    "description": "这个用例测试什么场景",
    "expected_status": 200
  }}
]"""

    def _call_qwen(self, prompt: str) -> str:
        resp = requests.post(
            QWEN_API_URL,
            headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}"},
            json={
                "model": QWEN_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 800,
                "temperature": 0.3,
            },
            timeout=30,
        )
        return resp.json()["choices"][0]["message"]["content"]

    def _call_deepseek(self, prompt: str) -> str:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 800,
                "temperature": 0.3,
            },
            timeout=30,
        )
        return resp.json()["choices"][0]["message"]["content"]

    def _parse_llm_response(self, raw: str, ep: dict) -> list[dict]:
        """从LLM的JSON回复中提取用例"""
        try:
            # 提取JSON片段
            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
            else:
                data = json.loads(raw)

            cases = []
            for item in data:
                cases.append({
                    "name": f"[AI] {item.get('name', 'AI增强用例')}",
                    "method": ep["method"],
                    "url": ep["full_url"],
                    "headers": {"Content-Type": "application/json"},
                    "query_params": {},
                    "body": {},
                    "expected_status": item.get("expected_status", 200),
                    "category": "AI增强",
                })
            return cases
        except Exception:
            return []

    # ---- 辅助方法 ----

    def _build_default_params(self, params: list, body: dict | None) -> dict:
        """根据参数定义构建默认请求参数"""
        result = {"query": {}, "path": {}, "body": {}}

        for p in params:
            val = p.get("example") or p.get("default")
            if val is None:
                ptype = p.get("type", "string")
                val = {"string": "test", "integer": 1, "number": 1.0, "boolean": True, "array": []}.get(ptype, "test")
            result[p["in"]][p["name"]] = val

        if body and body.get("example"):
            result["body"] = body["example"]
        elif body and body.get("schema"):
            result["body"] = self._schema_to_default(body["schema"])

        return result

    def _schema_to_default(self, schema: dict) -> dict:
        """从JSON Schema生成默认值"""
        if schema.get("example"):
            return schema["example"]
        result = {}
        for prop, details in schema.get("properties", {}).items():
            ptype = details.get("type", "string")
            result[prop] = {"string": "test", "integer": 1, "number": 1.0, "boolean": True, "array": []}.get(ptype, "test")
        return result

    def _guess_success_status(self, ep: dict) -> int:
        """推测成功时的HTTP状态码"""
        method = ep["method"]
        if method == "POST":
            return 201
        if method == "DELETE":
            return 204
        # 从responses中找2xx
        for resp in ep.get("responses", []):
            if 200 <= resp.get("status_code", 0) < 300:
                return resp["status_code"]
        return 200

    def _make_param_variant(self, ep: dict, pname: str, pin: str, value, desc: str, expected: int = None) -> dict:
        """生成单个参数变体用例"""
        params = self._build_default_params(ep["parameters"], ep.get("request_body"))
        if pin in ("query", "path"):
            params[pin][pname] = value
        return {
            "name": f"[边界] {ep['method']} {ep['path']} — {desc}",
            "method": ep["method"],
            "url": ep["full_url"],
            "headers": {"Content-Type": "application/json"},
            "query_params": params.get("query", {}),
            "path_params": params.get("path", {}),
            "body": params.get("body", {}),
            "expected_status": expected or self._guess_success_status(ep),
            "category": "边界值",
        }
