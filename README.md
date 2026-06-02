# SmartTest Agent

**AI 驱动的接口自动化测试工具** — 输入 Swagger/OpenAPI 规范，自动生成智能测试用例、执行 HTTP 请求、校验结果、输出双格式报告。

> 毕业设计/校招作品 | 马加琦 | 2026

---

## 目录

- [项目概述](#项目概述)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [使用方式](#使用方式)
- [项目结构](#项目结构)
- [测试用例类型](#测试用例类型)
- [设计决策](#设计决策)
- [技术栈](#技术栈)
- [后续规划](#后续规划)

---

## 项目概述

### 解决的问题

传统接口测试的痛点：
1. **手写用例耗时** — 每个接口要手动编写正向/反向/边界用例
2. **覆盖不全** — 人容易遗漏边界条件和异常场景
3. **结果分析零散** — 没有结构化的测试报告

SmartTest Agent 解决方式：
1. **自动解析** — 读取 Swagger JSON，提取全部接口元信息
2. **规则 + AI 双引擎** — 确定性规则覆盖常见场景，LLM 补充高价值边缘用例
3. **一键出报告** — Markdown + HTML 双格式，可直接发给面试官或团队成员

### 核心能力

```
Swagger URL / JSON文件
        │
        ▼
   ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
   │ 解析器   │ → │ 用例生成器 │ → │ 执行器    │ → │ 校验器    │ → │ 报告生成器 │
   │ Parser  │    │ Generator│    │ Executor │    │ Validator│    │ Reporter │
   └─────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                        │                                │               │
                   规则引擎 + LLM                   状态码/Schema      MD + HTML
                        │                          /耗时校验           报告
                   5类确定性用例
                   + AI增强用例
```

---

## 技术架构

```
┌─────────────────────────────────────────────────┐
│                  输入层                           │
│  Swagger URL | 本地JSON | Streamlit文件上传       │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│            SwaggerParser (解析器)                 │
│  · 支持 OpenAPI 3.0 / Swagger 2.0               │
│  · 提取: 路径、方法、参数、请求体、响应Schema      │
│  · 自动推断 API 基地址                           │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│          TestGenerator (用例生成器)               │
│                                                  │
│  ┌──────────────┐    ┌──────────────────┐        │
│  │  规则引擎     │    │  LLM 增强引擎     │        │
│  │  (确定性)     │    │  (千问 / DeepSeek)│        │
│  │              │    │                  │        │
│  │ · 正向用例    │    │ · 业务逻辑漏洞    │        │
│  │ · 边界值      │    │ · 组合参数异常    │        │
│  │ · 缺失必填参数 │    │ · 隐式依赖推断    │        │
│  │ · 类型错误    │    │                  │        │
│  │ · 鉴权失败    │    └──────────────────┘        │
│  └──────────────┘                                │
│       ↓ 合并去重                                  │
│  最终用例集 (15-30条/端点)                         │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│           TestExecutor (执行器)                   │
│  · ThreadPoolExecutor 并发执行                    │
│  · 自动重试 (2次)                                │
│  · 超时控制 (30s)                                │
│  · 路径参数替换                                  │
│  · 全局 Headers 注入                             │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│         ResultValidator (校验器)                  │
│  · 状态码比对 (2xx模糊匹配)                       │
│  · 响应时间告警 (>5s标记)                         │
│  · 5xx空响应体检测                                │
│  · 连接错误标记                                  │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│        ReportGenerator (报告生成器)               │
│                                                  │
│  ┌──────────────────┐  ┌──────────────────┐      │
│  │  Markdown 报告    │  │  HTML 报告        │      │
│  │  · 概览统计       │  │  · 可视化仪表盘    │      │
│  │  · 分类通过率     │  │  · 可折叠详情      │      │
│  │  · 失败用例明细   │  │  · 暗色主题        │      │
│  └──────────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────┘
```

### 数据流 — 以一个端点为例

输入: `POST /api/users`

```
SwaggerParser 提取:
  method: POST
  path: /api/users
  parameters: []
  request_body: { name: string, email: string }
  responses: [{ status_code: 201 }]

TestGenerator 生成:
  1. [正向] 正常创建用户 → 预期201
  2. [边界] 空请求体 → 预期400
  3. [边界] name=超长字符串5000字符 → 预期400
  4. [缺参] 缺少name字段 → 预期400
  5. [类型错误] name=数字123 → 预期400
  6. [鉴权] 无Token → 预期401
  7. [AI增强] email格式异常但其他字段正确 → 预期400

TestExecutor 执行 → 7条HTTP请求
ResultValidator 校验 → 发现2个慢请求告警
ReportGenerator 输出 → test_report_20260602_143025.{md,html}
```

---

## 快速开始

### 环境要求

- Python 3.9+
- 千问 API Key（[DashScope](https://dashscope.aliyuncs.com) 免费注册）
- （可选）DeepSeek API Key

### 安装

```bash
# 1. 进入项目目录
cd smarttest-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env 文件，填入你的千问 API Key
# DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx

# 4. 运行演示（无需 Swagger 文件）
python main.py --demo
```

### 5 分钟体验

```bash
# CLI 方式 — 使用真实 Swagger URL
python main.py https://petstore3.swagger.io/api/v3/openapi.json

# 或使用本地 Swagger 文件
python main.py ./docs/swagger.json

# 带鉴权头
python main.py https://api.example.com/swagger.json -H "Authorization: Bearer YOUR_TOKEN"

# Web UI 方式
streamlit run web_app.py
# 浏览器打开 http://localhost:8501
```

---

## 使用方式

### 方式一：CLI 命令行

```bash
# 基本用法
python main.py <swagger_url_or_file>

# 带鉴权
python main.py api.swagger.json -H "Authorization: Bearer xxx"

# 指定 LLM
python main.py api.swagger.json --llm deepseek

# 只生成用例不执行（预览）
python main.py api.swagger.json --dry-run

# 内置演示
python main.py --demo
```

### 方式二：Streamlit Web UI

```bash
streamlit run web_app.py
```

功能：
- 输入 Swagger URL 或上传 JSON 文件
- 配置全局请求头（如 Token）
- 实时进度条展示执行状态
- 交互式结果表格（排序、筛选）
- 失败用例可展开查看详情（请求体、响应体、错误信息）
- 一键下载 Markdown / HTML 报告

### 方式三：作为 Python 库使用

```python
from core.swagger_parser import SwaggerParser
from core.test_generator import TestGenerator
from core.test_executor import TestExecutor

# 解析
parser = SwaggerParser("https://api.example.com/swagger.json")
endpoints = parser.parse()

# 生成用例
gen = TestGenerator(llm="qwen")
cases = gen.generate(endpoints[0])  # 只测试第一个端点

# 执行
executor = TestExecutor()
results = executor.execute(cases, headers={"Authorization": "Bearer xxx"})

for r in results:
    print(f"{'✅' if r['passed'] else '❌'} {r['case_name']} — {r['status_code']}")
```

---

## 项目结构

```
smarttest-agent/
├── README.md                  ← 本文档
├── requirements.txt           ← Python依赖
├── .env.example               ← 环境变量模板
├── .gitignore
│
├── main.py                    ← CLI入口 (命令行模式)
├── web_app.py                 ← Web UI入口 (Streamlit)
│
├── config/
│   ├── __init__.py
│   └── settings.py            ← 全局配置 (超时、重试、阈值)
│
├── core/                      ← 核心模块
│   ├── __init__.py
│   ├── swagger_parser.py      ← Swagger/OpenAPI 解析器
│   ├── test_generator.py      ← 测试用例生成器 (规则+LLM)
│   ├── test_executor.py       ← HTTP请求执行器 (并发)
│   ├── result_validator.py    ← 结果校验器
│   └── report_generator.py    ← 报告生成器 (MD+HTML)
│
├── utils/
│   ├── __init__.py
│   └── helpers.py             ← CLI输出美化、统计打印
│
├── test_reports/              ← 测试报告输出目录 (自动创建)
│   ├── test_report_*.md
│   ├── test_report_*.html
│   └── results.json
│
└── tests/                     ← 项目自身测试
    └── test_demo.py           ← 单元测试
```

---

## 测试用例类型

每个 API 端点自动生成 **5 类确定性用例 + AI 增强用例**：

| 类别 | 说明 | 示例 |
|------|------|------|
| **正向用例** | 正常参数，预期成功 | `GET /users?page=1` → 200 |
| **边界值** | 超长字符串、极大数值、负数、空请求体 | `name=5000字符` → 400 |
| **缺失必填参数** | 逐个去掉必填参数 | 缺少 `email` → 400 |
| **类型错误** | 整数参数传字符串 | `page="abc"` → 400 |
| **鉴权失败** | 不带 Token 请求 | 无 Authorization → 401 |
| **AI 增强** | LLM 生成的补充用例 | 业务逻辑组合异常、隐式约束违反 |

---

## 设计决策

### 为什么不用 LangChain / AutoGPT？

- **太重** — SmartTest Agent 的核心流程是线性的（解析→生成→执行→校验→报告），不需要复杂的 Agent 编排
- **面试可解释性** — 自定义代码比框架更好讲清楚"为什么这么做"
- **依赖最小化** — requirements.txt 只有 5 个依赖

### 为什么规则引擎 + LLM 双引擎？

- **规则引擎** — 覆盖 80% 常见场景，速度快、零成本、确定性100%
- **LLM 增强** — 覆盖规则难以发现的业务逻辑漏洞，提升测试深度
- **降级设计** — LLM 不可用时静默降级，基础用例依然完整可用

### 为什么支持双模型？

- 千问（默认）— 国内直连、中文友好、免费额度充足
- DeepSeek — 性价比高、代码理解能力强
- 插件化设计：新增模型只需加一个 `_call_xxx` 方法

### 为什么 2xx 做模糊匹配？

- POST 创建可能返回 200 或 201，取决于服务端实现
- GET 无内容时可能返回 200 或 204
- 严格匹配会导致误报，模糊匹配更符合实际测试场景

---

## 技术栈

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| 语言 | Python 3.9+ | 测试领域主流语言 |
| HTTP | requests | 最成熟的 Python HTTP 库 |
| LLM | 千问 qwen-plus / DeepSeek | 国内可直连、成本低 |
| Web UI | Streamlit | 无需前端代码、5分钟搭出完整界面 |
| 报告 | Jinja2 | 轻量模板引擎、HTML渲染 |
| 并发 | concurrent.futures | 标准库、零依赖 |
| CLI | argparse + colorama | 标准库 + 终端着色 |

---

## 后续规划

- [ ] 支持 Swagger 2.0 (当前仅 OpenAPI 3.0)
- [ ] 支持 GraphQL Schema
- [ ] 支持 Postman Collection 导入
- [ ] 支持自定义断言脚本 (JavaScript)
- [ ] Docker 一键部署
- [ ] CI/CD 集成 (GitHub Actions 模板)
- [ ] 历史报告对比 (回归测试)

---

## 作者

**马加琦** — 哈尔滨信息工程学院 · 计算机科学与技术 · 2027届

- GitHub: [mjqaa](https://github.com/mjqaa)
- 邮箱: 1297408499@qq.com

---

*Built with Python · Streamlit · 千问 LLM*
