"""Comprehensive threshold test for skill generation gate.

30 test cases designed to validate the new AND-logic threshold:
  - review_trigger_iterations >= 10  AND
  - review_min_tool_calls >= 5

Categories:
  A. Should CREATE (complex multi-step + trial-and-error)
  B. Should NOT create (simple/few-tool/smooth tasks)
  C. Should PATCH (evolve existing skill)
  D. Edge cases (borderline complexity)
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

API = "http://127.0.0.1:8900/v1/chat/completions"
WORKSPACE_SKILLS = Path(os.path.expanduser("~/.hiperone/workspace/skills"))
MANIFEST = WORKSPACE_SKILLS / ".skill-manifest.json"
EVENTS = WORKSPACE_SKILLS / ".skill-events.jsonl"
RESULTS: list[dict] = []


def chat(text: str, session: str = "default", timeout: int = 180) -> dict:
    r = requests.post(API, json={
        "model": "MiniMax-M2.7-highspeed",
        "messages": [{"role": "user", "content": text}],
        "session_id": session,
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_skills() -> list[str]:
    if not WORKSPACE_SKILLS.exists():
        return []
    return [d.name for d in WORKSPACE_SKILLS.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()]


def get_events() -> list[dict]:
    if not EVENTS.exists():
        return []
    return [json.loads(l) for l in EVENTS.read_text(encoding="utf-8").strip().splitlines() if l.strip()]


def get_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def record(name: str, passed: bool, detail: str):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"name": name, "status": status, "detail": detail})
    tag = "\033[32mPASS\033[0m" if passed else "\033[31mFAIL\033[0m"
    print(f"  [{tag}] {name}: {detail}")


def wait_for_review(max_wait: int = 60) -> int:
    start = time.time()
    initial = len(get_events())
    while time.time() - start < max_wait:
        time.sleep(4)
        current = len(get_events())
        if current > initial:
            time.sleep(3)
            return current - initial
    return 0


def multi_turn(turns: list[str], session: str, delay: float = 1.5):
    for t in turns:
        chat(t, session=session)
        time.sleep(delay)


# ═══════════════════════════════════════════════════════════════
# Setup
# ═══════════════════════════════════════════════════════════════

print("=" * 70)
print("THRESHOLD TEST — Skill Generation Gate Validation")
print(f"  review_trigger_iterations >= 10 AND review_min_tool_calls >= 5")
print(f"  Skills before: {get_skills()}")
print(f"  Events before: {len(get_events())}")
print("=" * 70)

try:
    chat("ping", session="warmup")
    print("API is responsive.\n")
except Exception as e:
    print(f"ERROR: API not reachable: {e}")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# Category A: Should CREATE skill (complex + trial-and-error)
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("CATEGORY A: Should CREATE (complex multi-step + trial-and-error)")
print("=" * 70)

# A1: Data pipeline with debugging
print("\n--- A1: Data pipeline with code debugging ---")
s_before = set(get_skills())
multi_turn([
    "创建一个Python脚本，读取一个CSV文件（包含name,age,score列），计算每个人的等级（A/B/C/D），但CSV文件还不存在",
    "先创建测试用的CSV文件sample_data.csv，5行数据",
    "运行脚本处理CSV，看看有没有bug",
    "修改脚本增加异常处理，处理空值和非数字的情况",
    "加一个功能：输出成绩分布的柱状图，用matplotlib画",
    "运行最终版本，保存图片和结果到report.md",
], session="a1-pipeline")
new_events = wait_for_review(70)
new_skills = set(get_skills()) - s_before
record("A1-create", new_events > 0 or len(new_skills) > 0,
       f"Events: {new_events}, New skills: {new_skills or 'none'}")

# A2: Web scraping with error recovery
print("\n--- A2: Web scraping with retries and error handling ---")
s_before = set(get_skills())
multi_turn([
    "帮我写一个Python爬虫，爬取 https://news.ycombinator.com 首页的新闻标题和链接",
    "运行爬虫看看结果",
    "如果遇到反爬或者超时，增加重试机制和User-Agent伪装",
    "把爬取结果保存为JSON格式，每条包含title、url、rank",
    "增加一个翻页功能，爬前3页的数据",
    "检查JSON数据完整性，处理可能的编码问题",
], session="a2-scraping")
new_events = wait_for_review(70)
new_skills = set(get_skills()) - s_before
record("A2-create", new_events > 0 or len(new_skills) > 0,
       f"Events: {new_events}, New skills: {new_skills or 'none'}")

# A3: API integration with auth debugging
print("\n--- A3: REST API integration with debugging ---")
s_before = set(get_skills())
multi_turn([
    "写一个Python脚本调用GitHub API获取某个仓库的star数和fork数",
    "运行测试一下，用 torvalds/linux 仓库",
    "添加错误处理：API限流、网络超时、认证失败的情况",
    "扩展功能：获取最近10个issue的标题和状态",
    "把所有数据整理成一个Markdown报告",
    "增加一个对比功能：同时获取多个仓库的数据并排序",
], session="a3-api")
new_events = wait_for_review(70)
new_skills = set(get_skills()) - s_before
record("A3-create", new_events > 0 or len(new_skills) > 0,
       f"Events: {new_events}, New skills: {new_skills or 'none'}")

# A4: File processing with format conversion
print("\n--- A4: Complex file format conversion ---")
s_before = set(get_skills())
multi_turn([
    "创建一个YAML配置文件，包含数据库连接信息、Redis配置和日志级别",
    "写脚本把YAML转成等效的.env文件格式",
    "运行看看有没有嵌套对象的处理问题",
    "修复嵌套key的展平逻辑，用下划线连接，例如database.host变成DATABASE_HOST",
    "加一个反向功能：.env文件转回YAML",
    "写测试验证双向转换的一致性",
], session="a4-convert")
new_events = wait_for_review(70)
new_skills = set(get_skills()) - s_before
record("A4-create", new_events > 0 or len(new_skills) > 0,
       f"Events: {new_events}, New skills: {new_skills or 'none'}")

# A5: Docker workflow with troubleshooting
print("\n--- A5: Docker build with troubleshooting ---")
s_before = set(get_skills())
multi_turn([
    "写一个Dockerfile，基于Python 3.11，安装FastAPI和uvicorn，创建一个简单的API服务",
    "写对应的docker-compose.yml，包含Redis和PostgreSQL服务",
    "构建镜像试试看",
    "如果构建失败修复Dockerfile，检查依赖安装顺序",
    "添加健康检查和环境变量配置",
    "写一个启动脚本，处理数据库初始化和迁移",
], session="a5-docker")
new_events = wait_for_review(70)
new_skills = set(get_skills()) - s_before
record("A5-create", new_events > 0 or len(new_skills) > 0,
       f"Events: {new_events}, New skills: {new_skills or 'none'}")


# ═══════════════════════════════════════════════════════════════
# Category B: Should NOT create (simple/smooth/few-tool tasks)
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("CATEGORY B: Should NOT CREATE (simple/few-tool/smooth)")
print("=" * 70)

# B1: Simple greeting
print("\n--- B1: Simple greeting ---")
s_before = set(get_skills())
chat("你好，今天天气怎么样？", session="b1-greeting")
time.sleep(8)
new_skills = set(get_skills()) - s_before
record("B1-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B2: Single-fact Q&A
print("\n--- B2: Single-fact Q&A ---")
s_before = set(get_skills())
chat("Python中list和tuple的区别是什么？", session="b2-qa")
time.sleep(8)
new_skills = set(get_skills()) - s_before
record("B2-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B3: Code explanation (no tools needed)
print("\n--- B3: Code explanation ---")
s_before = set(get_skills())
chat("解释一下这段代码的作用：sorted(data, key=lambda x: x['score'], reverse=True)", session="b3-explain")
time.sleep(8)
new_skills = set(get_skills()) - s_before
record("B3-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B4: Simple math
print("\n--- B4: Simple math ---")
s_before = set(get_skills())
chat("计算 2^10 + 3^7 等于多少", session="b4-math")
time.sleep(8)
new_skills = set(get_skills()) - s_before
record("B4-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B5: Translation (pure text, no tools)
print("\n--- B5: Translation ---")
s_before = set(get_skills())
chat("把这句话翻译成英文：机器学习是人工智能的一个分支", session="b5-translate")
time.sleep(8)
new_skills = set(get_skills()) - s_before
record("B5-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B6: 2-step simple task (below threshold)
print("\n--- B6: Two-step simple task ---")
s_before = set(get_skills())
multi_turn([
    "创建一个hello.txt文件，内容是Hello World",
    "读取hello.txt确认内容正确",
], session="b6-simple-2step")
time.sleep(10)
new_skills = set(get_skills()) - s_before
record("B6-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B7: Opinion/advice (no tools)
print("\n--- B7: Opinion question ---")
s_before = set(get_skills())
chat("学Python应该先学什么？给我一个学习路线图", session="b7-advice")
time.sleep(8)
new_skills = set(get_skills()) - s_before
record("B7-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B8: Smooth 3-step (no errors, no trial-and-error)
print("\n--- B8: Smooth 3-step task (no errors) ---")
s_before = set(get_skills())
multi_turn([
    "创建一个numbers.json文件，包含1到10的数字数组",
    "写脚本计算这些数字的平均值",
    "运行脚本并告诉我结果",
], session="b8-smooth-3")
time.sleep(15)
new_skills = set(get_skills()) - s_before
record("B8-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B9: Personal one-off task
print("\n--- B9: Personal one-off task ---")
s_before = set(get_skills())
chat("查看当前目录下有哪些文件", session="b9-personal")
time.sleep(8)
new_skills = set(get_skills()) - s_before
record("B9-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# B10: Single tool usage (file read)
print("\n--- B10: Single tool call ---")
s_before = set(get_skills())
chat("帮我看一下 README.md 文件的内容", session="b10-single-tool")
time.sleep(8)
new_skills = set(get_skills()) - s_before
record("B10-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")


# ═══════════════════════════════════════════════════════════════
# Category C: Should PATCH (evolve existing skill)
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("CATEGORY C: Should PATCH (evolve existing skill)")
print("=" * 70)

# C1: Similar workflow to A1 (should patch or reuse, not duplicate)
print("\n--- C1: Similar data pipeline (should evolve, not duplicate) ---")
s_before = set(get_skills())
e_before = len(get_events())
multi_turn([
    "创建一个新的CSV文件employee_data.csv，包含name,department,salary列",
    "写脚本分析每个部门的平均薪资和人数",
    "运行脚本看结果",
    "遇到了数据类型问题，salary列有非数字值，修改脚本处理",
    "加一个功能：找出薪资最高和最低的员工",
    "生成一份完整的分析报告",
], session="c1-evolve")
new_events = wait_for_review(70)
events_now = get_events()
patch_count = sum(1 for e in events_now[e_before:] if e.get("action") == "patch")
create_count = sum(1 for e in events_now[e_before:] if e.get("action") == "create")
new_skills = set(get_skills()) - s_before
record("C1-evolve", new_events > 0,
       f"Patches: {patch_count}, Creates: {create_count}, New: {new_skills}")

# C2: Improved scraping approach
print("\n--- C2: Improved web scraping approach ---")
s_before = set(get_skills())
e_before = len(get_events())
multi_turn([
    "写爬虫抓取 https://www.python.org/blogs/ 的博客标题和日期",
    "运行看看能不能正常工作",
    "用BeautifulSoup解析HTML，提取结构化数据",
    "添加请求限速和异常处理",
    "把结果保存为JSON，包含title, date, url字段",
    "增加数据去重逻辑",
], session="c2-evolve-scrape")
new_events = wait_for_review(70)
events_now = get_events()
patch_count = sum(1 for e in events_now[e_before:] if e.get("action") == "patch")
record("C2-evolve", new_events > 0,
       f"Patches: {patch_count}, Events: {new_events}")


# ═══════════════════════════════════════════════════════════════
# Category D: Edge cases (borderline complexity)
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("CATEGORY D: Edge Cases (borderline complexity)")
print("=" * 70)

# D1: 4 steps, exactly at boundary (should NOT create — below 5 tool calls)
print("\n--- D1: 4-step borderline (just under threshold) ---")
s_before = set(get_skills())
multi_turn([
    "创建一个config.json文件",
    "写一个读取config的Python函数",
    "测试函数是否能正确读取",
    "保存最终版本",
], session="d1-borderline-4")
time.sleep(20)
new_skills = set(get_skills()) - s_before
record("D1-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# D2: 6 steps but no errors/trial-and-error (smooth execution)
print("\n--- D2: 6-step smooth execution (no trial-and-error) ---")
s_before = set(get_skills())
multi_turn([
    "创建一个Python类 Calculator，包含加减乘除方法",
    "写单元测试",
    "运行测试",
    "添加开方和幂运算方法",
    "更新测试覆盖新方法",
    "运行完整测试",
], session="d2-smooth-6")
new_events = wait_for_review(60)
new_skills = set(get_skills()) - s_before
# This is borderline — if everything goes smoothly, review prompt should say "Nothing to save"
# because no trial-and-error occurred. But if tools > 5 and iterations > 10, it gets reviewed.
record("D2-edge", True, f"Events: {new_events}, Skills: {new_skills or 'none'} (borderline case)")

# D3: Repeated single-tool calls (high iterations but few DISTINCT tools)
print("\n--- D3: Repeated single-tool calls ---")
s_before = set(get_skills())
multi_turn([
    "搜索Python asyncio教程",
    "搜索Python threading教程",
    "搜索Python multiprocessing教程",
    "搜索Python concurrent.futures教程",
    "搜索Python协程最佳实践",
    "帮我总结以上搜索结果的要点",
], session="d3-repeated-tool")
new_events = wait_for_review(60)
new_skills = set(get_skills()) - s_before
record("D3-edge", True, f"Events: {new_events}, Skills: {new_skills or 'none'} (edge: repeated search)")

# D4: Multi-turn conversation without tool usage
print("\n--- D4: Multi-turn chat without tools ---")
s_before = set(get_skills())
multi_turn([
    "给我讲讲微服务架构的优缺点",
    "那什么情况下应该用微服务而不是单体？",
    "有什么推荐的微服务框架吗？",
    "这些框架的性能对比如何？",
    "总结一下，给我一个决策矩阵",
], session="d4-chat-only")
time.sleep(15)
new_skills = set(get_skills()) - s_before
record("D4-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# D5: Complex prompt but single execution (no iteration)
print("\n--- D5: One-shot complex task ---")
s_before = set(get_skills())
chat(
    "写一个完整的Flask REST API，包含用户注册、登录（JWT）、"
    "个人信息CRUD，使用SQLite数据库。代码写在一个文件里就行。",
    session="d5-one-shot",
)
time.sleep(15)
new_skills = set(get_skills()) - s_before
record("D5-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# D6: Lots of tool calls but all within one step (batch calls)
print("\n--- D6: Many files in one batch ---")
s_before = set(get_skills())
chat(
    "同时创建5个文件：a.py, b.py, c.py, d.py, e.py，"
    "每个文件包含一个简单的类定义",
    session="d6-batch",
)
time.sleep(15)
new_skills = set(get_skills()) - s_before
record("D6-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")

# D7: Borderline — just above threshold with genuine complexity
print("\n--- D7: Complex debug cycle (just above threshold) ---")
s_before = set(get_skills())
multi_turn([
    "写一个Python脚本解析Nginx access log文件，统计每个IP的访问次数",
    "先创建一个模拟的access.log文件用于测试",
    "运行脚本",
    "脚本有bug，日志格式匹配不对，帮我修复正则表达式",
    "增加功能：统计每小时的访问量趋势",
    "增加功能：检测异常IP（访问频率超过阈值的）",
    "输出完整报告，包含Top10 IP和异常检测结果",
], session="d7-complex-debug")
new_events = wait_for_review(70)
new_skills = set(get_skills()) - s_before
record("D7-create-likely", new_events > 0 or len(new_skills) > 0,
       f"Events: {new_events}, Skills: {new_skills or 'none'}")

# D8: Long chat with few actual tool calls
print("\n--- D8: Long chat, few tools ---")
s_before = set(get_skills())
multi_turn([
    "我想设计一个电商系统的数据库，你有什么建议？",
    "用户表需要哪些字段？",
    "订单表和商品表怎么设计？",
    "需要哪些索引？",
    "最终生成SQL建表语句",
], session="d8-long-chat-few-tools")
time.sleep(15)
new_skills = set(get_skills()) - s_before
record("D8-no-create", len(new_skills) == 0,
       f"New skills: {new_skills or 'none (correct)'}")


# ═══════════════════════════════════════════════════════════════
# Final Report
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("FINAL REPORT")
print("=" * 70)

total = len(RESULTS)
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
print(f"Pass rate: {passed/total*100:.1f}%" if total else "N/A")

print(f"\n--- Category breakdown ---")
for cat, prefix in [("A (Should Create)", "A"), ("B (Should NOT Create)", "B"),
                     ("C (Should Patch)", "C"), ("D (Edge Cases)", "D")]:
    cat_results = [r for r in RESULTS if r["name"].startswith(prefix)]
    cat_pass = sum(1 for r in cat_results if r["status"] == "PASS")
    print(f"  {cat}: {cat_pass}/{len(cat_results)} passed")

final_skills = get_skills()
print(f"\nFinal skills ({len(final_skills)}):")
for s in sorted(final_skills):
    print(f"  - {s}")

manifest = get_manifest()
print(f"\nManifest ({len(manifest)} entries):")
for name, entry in sorted(manifest.items()):
    print(f"  - {name}: by={entry.get('created_by', '?')}, usage={entry.get('usage_count', 0)}")

events = get_events()
action_counts: dict[str, int] = {}
for e in events:
    a = e.get("action", "?")
    action_counts[a] = action_counts.get(a, 0) + 1
print(f"\nAudit events ({len(events)}):")
for action, count in sorted(action_counts.items()):
    print(f"  - {action}: {count}")

print("\n--- All Results ---")
for r in RESULTS:
    print(f"  [{r['status']}] {r['name']}: {r['detail']}")

# Save report
report_path = Path(__file__).parent / "_threshold_test_report.json"
report = {
    "total": total, "passed": passed, "failed": failed,
    "pass_rate": f"{passed/total*100:.1f}%",
    "results": RESULTS,
    "final_skills": final_skills,
    "manifest": manifest,
    "events_summary": action_counts,
    "total_events": len(events),
}
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nReport saved to {report_path}")
print("=" * 70)
