"""工具函数"""
import json, os, sys, time
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

# Windows GBK 编码兼容
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def print_banner():
    print(f"{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}  SmartTest Agent — AI驱动的接口自动化测试工具")
    print(f"{Fore.CYAN}{'='*60}")


def print_summary(results: list[dict]):
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    rate = round(passed / total * 100, 1) if total > 0 else 0

    color = Fore.GREEN if rate >= 90 else (Fore.YELLOW if rate >= 70 else Fore.RED)
    print(f"\n{'─'*60}")
    print(f"  总计: {total}  |  通过: {Fore.GREEN}{passed}{Style.RESET_ALL}  |  "
          f"失败: {Fore.RED}{failed}{Style.RESET_ALL}  |  通过率: {color}{rate}%{Style.RESET_ALL}")
    print(f"{'─'*60}\n")

    if failed > 0:
        print(f"{Fore.RED}失败用例明细:{Style.RESET_ALL}")
        for r in results:
            if not r["passed"]:
                status = r.get("status_code", 0)
                expected = r.get("expected_status", "?")
                error = r.get("error", "")
                err_msg = f" — {error}" if error else ""
                print(f"  [FAIL] {r['case_name']}")
                print(f"     {status} (预期 {expected}){err_msg}")
        print()


def print_case_result(idx: int, case: dict, result: dict):
    mark = f"{Fore.GREEN}PASS{Style.RESET_ALL}" if result["passed"] else f"{Fore.RED}FAIL{Style.RESET_ALL}"
    elapsed = result.get("elapsed_ms", 0)
    status = result.get("status_code", 0)
    print(f"  [{idx}] [{mark}] {case['name'][:70]}")
    print(f"      {status} | {elapsed}ms")
    if not result["passed"] and result.get("error"):
        print(f"      {Fore.RED}错误: {result['error']}{Style.RESET_ALL}")


def save_results_json(results: list[dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"{Fore.GREEN}结果已保存到: {path}{Style.RESET_ALL}")
