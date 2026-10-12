"""Headless browser QA for the native frontend.

This script is intentionally separate from pytest because it requires a locally
installed Chromium-based browser. Run with: uv run --with playwright python
tests/visual_qa.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import Route, async_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
BASE_URL = "http://127.0.0.1:8000"

CONNECTION = {
    "repository": "https://svn.example.local/warehouse/trunk",
    "username": "reviewer",
    "password": "local-test-only",
}

COMMITS = {
    "commits": [
        {
            "revision": 1842,
            "author": "liwei",
            "date": "2026-10-12T08:42:00Z",
            "message": "修复库存同步时的重复写入",
            "changed_paths": [],
            "changed_file_count": 4,
        },
        {
            "revision": 1841,
            "author": "chenyu",
            "date": "2026-10-11T13:18:00Z",
            "message": "新增供应商筛选条件",
            "changed_paths": [],
            "changed_file_count": 2,
        },
        {
            "revision": 1840,
            "author": "zhangyan",
            "date": "2026-10-10T06:03:00Z",
            "message": "重构订单导出服务",
            "changed_paths": [],
            "changed_file_count": 7,
        },
    ],
    "next_before": None,
}

DETAIL = {
    "revision": {
        "revision": 1842,
        "author": "liwei",
        "date": "2026-10-12T08:42:00Z",
        "message": "修复库存同步时的重复写入\n\n避免重试任务重复落库，并补充审计字段。",
        "changed_paths": [],
        "changed_file_count": 4,
    },
    "diffs": [
        {
            "path": "src/services/inventory.py",
            "old_path": "src/services/inventory.py",
            "new_path": "src/services/inventory.py",
            "status": "modified",
            "binary": False,
            "property_changes": [],
            "raw_fallback": [],
            "hunks": [
                {
                    "header": "@@ -18,3 +18,4 @@ def normalize(item):",
                    "old_start": 18,
                    "old_count": 3,
                    "new_start": 18,
                    "new_count": 4,
                    "lines": [
                        {"kind": "context", "content": "def normalize(item):", "old_line": 18, "new_line": 18},
                        {"kind": "deletion", "content": "    return mapper.apply(item)", "old_line": 19, "new_line": None},
                        {"kind": "addition", "content": "    record = mapper.apply(item)", "old_line": None, "new_line": 19},
                        {"kind": "addition", "content": "    return validate(record)", "old_line": None, "new_line": 20},
                        {"kind": "context", "content": "", "old_line": 20, "new_line": 21},
                    ],
                },
                {
                    "header": "@@ -42,3 +43,4 @@ def sync(item):",
                    "old_start": 42,
                    "old_count": 3,
                    "new_start": 43,
                    "new_count": 4,
                    "lines": [
                        {"kind": "context", "content": "record = normalize(item)", "old_line": 42, "new_line": 43},
                        {"kind": "deletion", "content": "save(record)", "old_line": 43, "new_line": None},
                        {"kind": "addition", "content": "if not exists(record.id):", "old_line": None, "new_line": 44},
                        {"kind": "addition", "content": "    save(record)", "old_line": None, "new_line": 45},
                        {"kind": "context", "content": "return record", "old_line": 44, "new_line": 46},
                    ],
                },
            ],
        },
        {
            "path": "src/models/audit.py",
            "old_path": "src/models/audit.py",
            "new_path": "src/models/audit.py",
            "status": "added",
            "binary": False,
            "property_changes": [],
            "raw_fallback": [],
            "hunks": [{
                "header": "@@ -0,0 +1,3 @@",
                "old_start": 0,
                "old_count": 0,
                "new_start": 1,
                "new_count": 3,
                "lines": [
                    {"kind": "addition", "content": "class AuditEntry:", "old_line": None, "new_line": 1},
                    {"kind": "addition", "content": "    revision: int", "old_line": None, "new_line": 2},
                    {"kind": "addition", "content": "    actor: str", "old_line": None, "new_line": 3},
                ],
            }],
        },
        {
            "path": "docs/legacy-sync.md",
            "old_path": "docs/legacy-sync.md",
            "new_path": "docs/legacy-sync.md",
            "status": "deleted",
            "binary": False,
            "property_changes": [],
            "raw_fallback": [],
            "hunks": [{
                "header": "@@ -1,2 +0,0 @@",
                "old_start": 1,
                "old_count": 2,
                "new_start": 0,
                "new_count": 0,
                "lines": [
                    {"kind": "deletion", "content": "# Legacy sync", "old_line": 1, "new_line": None},
                    {"kind": "deletion", "content": "Deprecated workflow.", "old_line": 2, "new_line": None},
                ],
            }],
        },
        {
            "path": "assets/warehouse-map.png",
            "old_path": "assets/warehouse-map.png",
            "new_path": "assets/warehouse-map.png",
            "status": "binary",
            "binary": True,
            "property_changes": [],
            "raw_fallback": ["Cannot display: file marked as a binary type."],
            "hunks": [],
        },
    ],
}


async def mock_api(route: Route) -> None:
    url = route.request.url
    if url.endswith("/api/repository/check"):
        body = {"ok": True, "repository": {"revision": 1842, "kind": "dir", "url": CONNECTION["repository"]}}
    elif url.endswith("/api/commits"):
        body = COMMITS
    elif url.endswith("/api/commits/1842"):
        body = DETAIL
    elif url.endswith("/api/files/content"):
        payload = route.request.post_data_json
        start = payload["start_line"]
        count = payload["line_count"]
        total = 320
        end = min(total, start + count - 1)
        body = {
            "path": payload["path"],
            "revision": payload["revision"],
            "start_line": start,
            "end_line": end,
            "total_lines": total,
            "has_before": start > 1,
            "has_after": end < total,
            "lines": [f"sample source line {line}" for line in range(start, end + 1)],
        }
    else:
        await route.continue_()
        return
    await route.fulfill(status=200, content_type="application/json", body=json.dumps(body, ensure_ascii=False))


async def assert_viewport(page, *, allow_vertical: bool = True) -> None:
    metrics = await page.evaluate(
        """() => ({
          innerWidth: window.innerWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          scrollHeight: document.documentElement.scrollHeight,
          clientHeight: document.documentElement.clientHeight
        })"""
    )
    assert metrics["scrollWidth"] <= metrics["clientWidth"], metrics
    if not allow_vertical:
        assert metrics["scrollHeight"] <= metrics["clientHeight"], metrics


async def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    executable = next((path for path in candidates if path.exists()), None)
    if executable is None:
        raise RuntimeError("No installed Chromium browser was found")

    errors: list[str] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, executable_path=str(executable))

        desktop = await browser.new_context(viewport={"width": 1440, "height": 900})
        desktop_page = await desktop.new_page()
        desktop_page.on("pageerror", lambda error: errors.append(str(error)))
        await desktop_page.route("**/api/**", mock_api)
        await desktop_page.goto(BASE_URL, wait_until="networkidle")
        await desktop_page.get_by_role("heading", name="连接你的 SVN 仓库").wait_for()
        await assert_viewport(desktop_page)
        await desktop_page.screenshot(path=ARTIFACTS / "setup-desktop.png", full_page=True)

        await desktop_page.get_by_label("仓库地址").fill(CONNECTION["repository"])
        await desktop_page.get_by_label("用户名").fill(CONNECTION["username"])
        await desktop_page.get_by_label("密码").fill(CONNECTION["password"])
        await desktop_page.get_by_role("button", name="测试连接并进入").click()
        await desktop_page.get_by_role("heading", name="提交记录").wait_for()
        assert await desktop_page.locator(".commit-row").count() == 3
        await assert_viewport(desktop_page)
        await desktop_page.screenshot(path=ARTIFACTS / "commits-desktop.png", full_page=True)

        await desktop_page.locator(".commit-row").first.click()
        await desktop_page.locator(".diff-file").first.wait_for()
        assert await desktop_page.locator(".diff-file").count() == 4
        assert await desktop_page.get_by_text("二进制文件已变更").count() == 1
        assert await desktop_page.locator(".mode-switch .active").inner_text() == "并排"
        await assert_viewport(desktop_page)
        await desktop_page.screenshot(path=ARTIFACTS / "diff-desktop.png", full_page=False)

        source_folder = desktop_page.locator('.file-tree-folder[title="src"]')
        assert await source_folder.get_attribute("aria-expanded") == "true"
        await source_folder.click()
        assert await source_folder.get_attribute("aria-expanded") == "false"
        assert not await desktop_page.get_by_role("treeitem", name="跳转到 src/models/audit.py").is_visible()
        await source_folder.click()
        assert await source_folder.get_attribute("aria-expanded") == "true"

        detail_hash = await desktop_page.evaluate("location.hash")
        audit_file = desktop_page.get_by_role("treeitem", name="跳转到 src/models/audit.py")
        assert await audit_file.get_attribute("title") == "src/models/audit.py"
        await audit_file.click()
        await desktop_page.wait_for_function("window.scrollY > 0")
        assert await desktop_page.evaluate("location.hash") == detail_hash
        assert await desktop_page.get_by_role("heading", name="提交记录").count() == 0

        await desktop_page.get_by_role("button", name="单栏").click()
        assert await desktop_page.locator(".mode-switch .active").inner_text() == "单栏"
        await desktop_page.get_by_role("button", name="并排").click()
        assert await desktop_page.locator(".mode-switch .active").inner_text() == "并排"

        await desktop_page.locator('[aria-label="向下读取 20 行"]').first.click()
        await desktop_page.get_by_text("sample source line 22").wait_for()
        await desktop_page.get_by_role("button", name="查看文件").first.click()
        await desktop_page.locator(".source-row").first.wait_for()
        assert await desktop_page.locator(".source-row").count() == 200
        await desktop_page.get_by_role("button", name="返回差异").first.click()
        await desktop_page.locator(".diff-split").first.wait_for()

        mobile = await browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        seed = json.dumps(CONNECTION, ensure_ascii=False)
        await mobile.add_init_script(
            f"localStorage.setItem('svnlab.connection.v1', JSON.stringify({seed}));"
        )
        mobile_page = await mobile.new_page()
        mobile_page.on("pageerror", lambda error: errors.append(str(error)))
        await mobile_page.route("**/api/**", mock_api)
        await mobile_page.goto(f"{BASE_URL}/#/commits/1842", wait_until="networkidle")
        await mobile_page.locator(".diff-file").first.wait_for()
        assert await mobile_page.locator(".mode-switch .active").inner_text() == "单栏"
        await assert_viewport(mobile_page)
        await mobile_page.screenshot(path=ARTIFACTS / "diff-mobile.png", full_page=False)

        await mobile.close()
        await desktop.close()
        await browser.close()

    if errors:
        raise AssertionError(f"Browser page errors: {errors}")
    print("Visual QA passed: setup, commits, complete diff, controls, source view, and mobile layout")


if __name__ == "__main__":
    asyncio.run(main())

