"""
SmartTest Agent — Streamlit Web UI
启动: streamlit run web_app.py
"""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from core.swagger_parser import SwaggerParser
from core.test_generator import TestGenerator
from core.test_executor import TestExecutor
from core.result_validator import ResultValidator
from core.report_generator import ReportGenerator

st.set_page_config(page_title="SmartTest Agent", page_icon="🧪", layout="wide")

# ---- 侧边栏配置 ----
with st.sidebar:
    st.title("🧪 SmartTest Agent")
    st.markdown("AI驱动的接口自动化测试")
    st.markdown("---")

    st.subheader("📎 API 来源")
    source_type = st.radio("选择输入方式", ["URL", "上传JSON文件", "内置演示"], label_visibility="collapsed")

    swagger_source = None
    if source_type == "URL":
        swagger_source = st.text_input("Swagger JSON URL", placeholder="https://api.example.com/swagger.json")
    elif source_type == "上传JSON文件":
        uploaded = st.file_uploader("上传 Swagger/OpenAPI JSON", type=["json"])
        if uploaded:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
            json.dump(json.loads(uploaded.read()), tmp)
            tmp.close()
            swagger_source = tmp.name
    else:
        swagger_source = "__demo__"

    st.markdown("---")
    st.subheader("⚙️ 配置")
    llm_choice = st.selectbox("LLM 模型", ["qwen", "deepseek"], help="用于生成AI增强用例")
    st.markdown("---")
    st.subheader("🔑 全局请求头")
    header_key = st.text_input("Header Key", placeholder="Authorization")
    header_val = st.text_input("Header Value", placeholder="Bearer xxx", type="password")
    extra_headers = {}
    if header_key and header_val:
        extra_headers[header_key.strip()] = header_val.strip()

# ---- 主区域 ----
st.title("SmartTest Agent")
st.caption("AI-Driven API Test Automation — 输入 Swagger 规范，自动生成并执行测试用例")

if st.button("🚀 开始测试", type="primary", use_container_width=True, disabled=not swagger_source):
    with st.spinner("正在解析 Swagger 规范..."):

        # 1. 解析
        if swagger_source == "__demo__":
            # 演示端点
            demo_endpoints = [
                {"method": "GET", "path": "/posts/1", "summary": "获取文章", "parameters": [],
                 "request_body": None, "responses": [{"status_code": 200}], "full_url": "https://jsonplaceholder.typicode.com/posts/1", "tags": ["Posts"]},
                {"method": "POST", "path": "/posts", "summary": "创建文章", "parameters": [],
                 "request_body": {"required": True, "schema": {"properties": {"title": {"type": "string"}, "body": {"type": "string"}}},
                 "example": {"title": "test", "body": "test body"}},
                 "responses": [{"status_code": 201}], "full_url": "https://jsonplaceholder.typicode.com/posts", "tags": ["Posts"]},
            ]
            info = {"title": "JSONPlaceholder (演示)", "version": "1.0", "base_url": "https://jsonplaceholder.typicode.com", "endpoint_count": 2}
        else:
            parser = SwaggerParser(swagger_source)
            demo_endpoints = parser.parse()
            info = parser.get_info()

        st.success(f"解析完成: {info['title']} v{info['version']} — {info['endpoint_count']} 个端点")

    # 2. 生成用例
    with st.spinner("正在生成测试用例..."):
        generator = TestGenerator(llm=llm_choice)
        all_cases = []
        for ep in demo_endpoints:
            all_cases.extend(generator.generate(ep))

        # 统计
        cat_counts = {}
        for c in all_cases:
            cat_counts[c.get("category", "其他")] = cat_counts.get(c.get("category", "其他"), 0) + 1

        cols = st.columns(len(cat_counts) + 1)
        cols[0].metric("总用例数", len(all_cases))
        for i, (cat, cnt) in enumerate(cat_counts.items(), 1):
            cols[i].metric(cat, cnt)

    # 3. 执行
    progress = st.progress(0, text="正在执行测试...")
    executor = TestExecutor()
    all_results = []
    total = len(all_cases)
    for i, case in enumerate(all_cases):
        results = executor.execute([case], headers=extra_headers, base_url=info["base_url"])
        all_results.extend(results)
        progress.progress((i + 1) / total, text=f"执行中... {i+1}/{total}")

    # 4. 校验
    validator = ResultValidator()
    all_results = validator.validate(all_results)

    # 5. 报告
    reporter = ReportGenerator()
    paths = reporter.generate(all_results, info)

    # ---- 展示结果 ----
    st.markdown("---")
    st.subheader("📊 测试结果")

    passed = sum(1 for r in all_results if r["passed"])
    failed = len(all_results) - passed
    rate = round(passed / len(all_results) * 100, 1) if all_results else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("通过", passed, delta=None)
    c2.metric("失败", failed, delta=None if failed == 0 else f"-{failed}")
    c3.metric("通过率", f"{rate}%")
    c4.metric("平均耗时", f"{round(sum(r.get('elapsed_ms',0) for r in all_results)/max(len(all_results),1))}ms")

    # 详细表格
    st.markdown("### 用例详情")
    table_data = []
    for i, r in enumerate(all_results, 1):
        table_data.append({
            "#": i,
            "用例名称": r["case_name"][:80],
            "分类": r.get("category", ""),
            "方法": r["method"],
            "URL": r["url"][:60],
            "状态码": r["status_code"],
            "预期": r["expected_status"],
            "耗时": f"{r.get('elapsed_ms',0)}ms",
            "结果": "✅" if r["passed"] else "❌",
        })
    st.dataframe(table_data, use_container_width=True, height=400)

    # 失败详情
    failed_cases = [r for r in all_results if not r["passed"]]
    if failed_cases:
        st.markdown("### ❌ 失败用例详情")
        for r in failed_cases:
            with st.expander(f"{r['case_name'][:80]} — 状态码 {r['status_code']} (预期 {r['expected_status']})"):
                st.write(f"**URL**: {r['url']}")
                st.write(f"**耗时**: {r.get('elapsed_ms', 0)}ms")
                if r.get("error"):
                    st.error(f"错误: {r['error']}")
                if r.get("validation_issues"):
                    for issue in r["validation_issues"]:
                        st.warning(f"{issue['type']}: {issue['detail']}")
                if r.get("response_body"):
                    st.json(r["response_body"])

    # 报告下载
    st.markdown("---")
    st.subheader("📄 报告下载")
    c1, c2 = st.columns(2)
    with c1:
        with open(paths["markdown_path"], "r", encoding="utf-8") as f:
            st.download_button("下载 Markdown 报告", f.read(), os.path.basename(paths["markdown_path"]), "text/markdown")
    with c2:
        with open(paths["html_path"], "r", encoding="utf-8") as f:
            st.download_button("下载 HTML 报告", f.read(), os.path.basename(paths["html_path"]), "text/html")

else:
    st.info("👈 在侧边栏配置 API 来源，然后点击「开始测试」")
    st.markdown("""
    ### 快速开始
    1. **选择一个 Swagger JSON** — 填入URL或上传文件
    2. **（可选）配置鉴权** — 在侧边栏添加 `Authorization` 请求头
    3. **点击「开始测试」** — 自动生成用例、执行、校验、出报告
    4. **下载报告** — Markdown + HTML 双格式

    ### 或先试试演示
    在侧边栏选择「内置演示」，使用 JSONPlaceholder 免费API体验完整流程。
    """)
