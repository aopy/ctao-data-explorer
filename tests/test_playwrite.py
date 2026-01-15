import re

from playwright.sync_api import Page


def test_frontend(page: Page):
    page.goto("http://test-chart-frontend.default.svc.cluster.local")
    assert "Welcome" in page.title()

    content = page.locator("h1").text_content()
    assert re.match(r"Welcome to nginx!", content)

    # save a screenshot
    page.screenshot(path="test_frontend.png")
