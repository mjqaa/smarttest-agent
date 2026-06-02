#!/usr/bin/env python
"""
SmartTest Agent — CLI入口
用法:
  python main.py <swagger_url_or_file>                # 基本使用
  python main.py <swagger_url_or_file> --header "Authorization: Bearer xxx"  # 带鉴权
  python main.py <swagger_url_or_file> --llm deepseek  # 指定LLM
  python main.py --demo                                # 演示模式(不需要Swagger)
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.swagger_parser import SwaggerParser
from core.test_generator import TestGenerator
from core.test_executor import TestExecutor
from core.result_validator import ResultValidator
from core.report_generator import ReportGenerator
from utils.helpers import print_banner, print_summary, print_case_result, save_results_json


def parse_headers(header_strs: list[str]) -> dict:
    """解析命令行传入的 Header: 'Authorization: Bearer xxx' -> dict"""
    headers = {}
    for h in header_strs:
        if ":" in h:
            key, val = h.split(":", 1)
            headers[key.strip()] = val.strip()
    return headers


def main():
    parser = argparse.ArgumentParser(description="SmartTest Agent — AI驱动的接口自动化测试")
    parser.add_argument("source", nargs="?", help="Swagger JSON 文件路径或URL")
    parser.add_argument("--header", "-H", action="append", default=[], help="全局请求头 (可多次使用)")
    parser.add_argument("--base-url", help="覆盖API基地址")
    parser.add_argument("--llm", choices=["qwen", "deepseek"], help="指定LLM模型")
    parser.add_argument("--dry-run", action="store_true", help="只生成用例不执行")
    parser.add_argument("--demo", action="store_true", help="运行内置演示")
    args = parser.parse_args()

    print_banner()

    # ---- 演示模式 ----
    if args.demo:
        run_demo(args)
        return

    if not args.source:
        parser.print_help()
        print("\n提示: 使用 --demo 运行内置演示")
        return

    # ---- 正常流程 ----
    run(args)


def run(args):
    headers = parse_headers(args.header)

    # 1. 解析 Swagger
    print(f"\n[1/5] 解析 Swagger 规范: {args.source}")
    parser = SwaggerParser(args.source)
    endpoints = parser.parse()
    info = parser.get_info()
    print(f"       API: {info['title']} v{info['version']}")
    print(f"       基地址: {info['base_url']}")
    print(f"       发现 {len(endpoints)} 个接口端点")

    # 2. 生成测试用例
    print(f"\n[2/5] 生成测试用例...")
    generator = TestGenerator(llm=args.llm)
    all_cases = []
    for ep in endpoints:
        cases = generator.generate(ep)
        all_cases.extend(cases)

    print(f"       共生成 {len(all_cases)} 个测试用例")
    for cat in ["正向用例", "边界值", "缺失必填参数", "类型错误", "鉴权失败", "AI增强"]:
        count = sum(1 for c in all_cases if c.get("category") == cat)
        if count:
            print(f"         {cat}: {count}")

    if args.dry_run:
        print("\n[Dry Run] 跳过执行，仅列出用例:")
        for i, c in enumerate(all_cases, 1):
            print(f"  [{i}] {c['name']}")
        return

    # 3. 执行测试
    print(f"\n[3/5] 执行测试用例...")
    executor = TestExecutor()
    base_url = args.base_url or info["base_url"]
    results = executor.execute(all_cases, headers=headers, base_url=base_url)

    for i, r in enumerate(results, 1):
        case = all_cases[i - 1] if i <= len(all_cases) else {}
        print_case_result(i, case, r)

    # 4. 校验结果
    print(f"\n[4/5] 校验测试结果...")
    validator = ResultValidator()
    results = validator.validate(results)
    issues = sum(r.get("issue_count", 0) for r in results)
    print(f"       发现 {issues} 个校验问题")

    # 5. 生成报告
    print(f"\n[5/5] 生成测试报告...")
    reporter = ReportGenerator()
    paths = reporter.generate(results, info)
    print(f"       Markdown: {paths['markdown_path']}")
    print(f"       HTML:     {paths['html_path']}")

    # 打印摘要
    print_summary(results)

    # 保存原始结果
    save_results_json(results, os.path.join("test_reports", "results.json"))


def run_demo(args):
    """内置演示: 使用一个模拟的 Swagger spec 展示完整流程"""
    print("\n  演示模式 — 使用内置模拟 API\n")

    # 创建一个最简单的模拟端点列表（不需要真实 Swagger 文件）
    demo_endpoints = [
        {
            "method": "GET",
            "path": "/api/users",
            "summary": "获取用户列表",
            "description": "分页查询所有用户",
            "tags": ["Users"],
            "parameters": [
                {"name": "page", "in": "query", "required": False, "type": "integer", "example": 1},
                {"name": "limit", "in": "query", "required": False, "type": "integer", "example": 10},
            ],
            "request_body": None,
            "responses": [{"status_code": 200, "description": "成功"}],
            "full_url": "https://jsonplaceholder.typicode.com/users",
        },
        {
            "method": "POST",
            "path": "/api/users",
            "summary": "创建用户",
            "description": "创建一个新用户",
            "tags": ["Users"],
            "parameters": [],
            "request_body": {
                "required": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                    },
                },
                "example": {"name": "testuser", "email": "test@example.com"},
            },
            "responses": [{"status_code": 201, "description": "创建成功"}],
            "full_url": "https://jsonplaceholder.typicode.com/users",
        },
    ]

    demo_info = {
        "title": "JSONPlaceholder API (演示)",
        "version": "1.0.0",
        "description": "免费在线 REST API 用于测试",
        "base_url": "https://jsonplaceholder.typicode.com",
        "endpoint_count": 2,
    }

    # 生成用例
    print("[2/5] 生成测试用例...")
    generator = TestGenerator(llm=args.llm)
    all_cases = []
    for ep in demo_endpoints:
        cases = generator.generate(ep)
        all_cases.extend(cases)
    print(f"       共生成 {len(all_cases)} 个测试用例")

    # 执行
    print("\n[3/5] 执行测试用例...")
    executor = TestExecutor()
    results = executor.execute(all_cases, base_url=demo_info["base_url"])
    for i, r in enumerate(results, 1):
        case = all_cases[i - 1] if i <= len(all_cases) else {}
        print_case_result(i, case, r)

    # 校验
    print("\n[4/5] 校验测试结果...")
    validator = ResultValidator()
    results = validator.validate(results)
    issues = sum(r.get("issue_count", 0) for r in results)
    print(f"       发现 {issues} 个校验问题")

    # 报告
    print("\n[5/5] 生成测试报告...")
    reporter = ReportGenerator()
    paths = reporter.generate(results, demo_info)
    print(f"       Markdown: {paths['markdown_path']}")
    print(f"       HTML:     {paths['html_path']}")

    print_summary(results)
    save_results_json(results, os.path.join("test_reports", "results.json"))


if __name__ == "__main__":
    main()
