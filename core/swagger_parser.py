"""
Swagger / OpenAPI 规范解析器
支持: OpenAPI 3.0, Swagger 2.0, 本地JSON文件, 远程URL
"""
from __future__ import annotations
import json
import requests
from urllib.parse import urljoin, urlparse


class SwaggerParser:
    """解析 OpenAPI 规范，提取所有接口的元信息"""

    def __init__(self, source: str):
        """
        source: 本地文件路径 或 远程URL
        """
        self.source = source
        self.spec = self._load_spec()
        self.base_url = self._get_base_url()

    # ---- 加载 ----

    def _load_spec(self) -> dict:
        if self.source.startswith(("http://", "https://")):
            resp = requests.get(self.source, timeout=15)
            resp.raise_for_status()
            return resp.json()
        with open(self.source, "r", encoding="utf-8") as f:
            return json.load(f)

    def _get_base_url(self) -> str:
        """推断 API 基地址"""
        # OpenAPI 3.0: servers[0].url
        servers = self.spec.get("servers", [])
        if servers:
            return servers[0]["url"].rstrip("/")

        # Swagger 2.0: host + basePath + schemes
        host = self.spec.get("host", "localhost")
        base_path = self.spec.get("basePath", "/")
        schemes = self.spec.get("schemes", ["http"])
        return f"{schemes[0]}://{host}{base_path}".rstrip("/")

    # ---- 解析 ----

    def parse(self) -> list[dict]:
        """返回所有接口端点列表"""
        endpoints = []
        paths = self.spec.get("paths", {})

        for path, methods in paths.items():
            for method in ["get", "post", "put", "patch", "delete", "options", "head"]:
                operation = methods.get(method)
                if not operation:
                    continue

                endpoints.append({
                    "method": method.upper(),
                    "path": path,
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "tags": operation.get("tags", []),
                    "parameters": self._parse_params(operation.get("parameters", [])),
                    "request_body": self._parse_body(operation.get("requestBody", {})),
                    "responses": self._parse_responses(operation.get("responses", {})),
                    "full_url": urljoin(self.base_url, path),
                })

        return endpoints

    def _parse_params(self, params: list) -> list[dict]:
        result = []
        for p in params:
            schema = p.get("schema", {})
            result.append({
                "name": p.get("name", ""),
                "in": p.get("in", ""),      # query / path / header
                "required": p.get("required", False),
                "type": schema.get("type", "string"),
                "example": schema.get("example", ""),
                "default": schema.get("default", None),
            })
        return result

    def _parse_body(self, body: dict) -> dict | None:
        if not body or not body.get("content"):
            return None
        json_content = body["content"].get("application/json", {})
        schema = json_content.get("schema", {})
        return {
            "required": body.get("required", False),
            "schema": schema,
            "example": schema.get("example", {}),
        }

    def _parse_responses(self, responses: dict) -> list[dict]:
        result = []
        for code, detail in responses.items():
            json_content = detail.get("content", {}).get("application/json", {})
            result.append({
                "status_code": int(code) if code.isdigit() else 0,
                "description": detail.get("description", ""),
                "schema": json_content.get("schema", {}),
            })
        return result

    def get_info(self) -> dict:
        """返回 API 基本信息"""
        info = self.spec.get("info", {})
        return {
            "title": info.get("title", "Unknown API"),
            "version": info.get("version", "0.0.0"),
            "description": info.get("description", ""),
            "base_url": self.base_url,
            "endpoint_count": len(self.parse()),
        }
