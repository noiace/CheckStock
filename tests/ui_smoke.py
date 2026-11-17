"""Run in a disposable Playwright container against a freshly seeded test API."""
import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


BASE_URL = "http://127.0.0.1:18000"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{BASE_URL}/ui/")
    expect(page.locator("#connection-text")).to_have_text("API подключён")
    expect(page.locator("#metric-physical")).to_have_text("25")
    expect(page.locator("#metric-sku")).to_have_text("3")

    def view(name):
        page.locator(f'[data-view="{name}"]').click()

    def submit(form_id, path, fields, status=201):
        form = page.locator(f"#{form_id}")
        for name, value in fields.items():
            field = form.locator(f'[name="{name}"]')
            if field.evaluate("element => element.tagName") == "SELECT":
                field.select_option(str(value))
            else:
                field.fill(str(value))
        with page.expect_response(lambda response: response.url.endswith(path) and response.request.method == "POST") as response:
            if status < 400:
                with page.expect_response(lambda response: response.url.endswith("/products") and response.request.method == "GET"):
                    form.locator('button[type="submit"]').click()
            else:
                form.locator('button[type="submit"]').click()
        assert response.value.status == status, response.value.text()
        expect(page.locator("#refresh-btn")).to_be_enabled()
        if status < 400:
            expect(page.locator("#operation-result")).not_to_have_class(re.compile(r"\berror\b"))
        else:
            expect(page.locator("#operation-result")).to_have_class(re.compile(r"\berror\b"))
        return response.value.json()

    def action(kind, operation_id):
        paths = {"fbs-cancel": f"/fbs/reservations/{operation_id}/cancel", "fbs-ship": f"/fbs/reservations/{operation_id}/ship", "fbs-deliver": f"/fbs/reservations/{operation_id}/deliver", "fbo-receive": f"/fbo/shipments/{operation_id}/receive", "transfer-receive": f"/transfers/{operation_id}/receive"}
        return submit("form-action", paths[kind], {"action": kind, "id": operation_id}, 200)

    def stocks():
        response = page.request.get(f"{BASE_URL}/stocks/1")
        assert response.ok
        return {row["warehouse_id"]: (row["physical_quantity"], row["reserved_quantity"], row["available_quantity"]) for row in response.json()}

    view("stocks")
    expect(page.locator("#stocks-rows tr")).to_have_count(6)
    page.locator("#stocks-search").fill("SKU-101")
    expect(page.locator("#stocks-rows tr")).to_have_count(2)
    view("operations")
    reserve = submit("form-fbs", "/fbs/reservations", {"product_id": 1, "warehouse_id": 1, "quantity": 3})
    assert stocks()[1] == (10, 3, 7)
    action("fbs-ship", reserve["id"])
    assert stocks()[1] == (7, 0, 7)
    fbo = submit("form-fbo", "/fbo/shipments", {"product_id": 1, "warehouse_id": 1, "quantity": 2})
    transfer = submit("form-transfer", "/transfers", {"product_id": 1, "from_warehouse_id": 1, "to_warehouse_id": 2, "quantity": 2})
    assert stocks() == {1: (3, 0, 3), 2: (6, 0, 6)}
    submit("form-fbo", "/fbo/shipments", {"product_id": 1, "warehouse_id": 1, "quantity": 4}, 409)
    expect(page.locator("#operation-result")).to_contain_text("Недостаточно доступного остатка")
    assert stocks()[1] == (3, 0, 3)
    view("transit")
    expect(page.locator("#transit-rows tr")).to_have_count(3)
    page.locator("#transit-filter").select_option("TRANSFER")
    expect(page.locator("#transit-rows tr")).to_have_count(1)
    page.locator('#transit-rows [data-quick-action="transfer-receive"]').click()
    expect(page.locator("#refresh-btn")).to_be_enabled()
    view("operations")
    action("transfer-receive", transfer["id"])
    assert stocks()[2] == (8, 0, 8)
    action("fbo-receive", fbo["id"])
    action("fbs-deliver", reserve["id"])
    reserve2 = submit("form-fbs", "/fbs/reservations", {"product_id": 1, "warehouse_id": 2, "quantity": 1})
    action("fbs-cancel", reserve2["id"])
    assert stocks()[2] == (8, 0, 8)
    product = submit("form-product", "/products", {"sku": "UI-104", "name": "Тест интерфейса"})
    submit("form-receipt", "/receipts", {"product_id": product["id"], "warehouse_id": 2, "quantity": 2})
    view("warehouses")
    submit("form-warehouse", "/warehouses", {"name": "Тестовый ФФ"})
    page.once("dialog", lambda dialog: dialog.accept("Север новый"))
    page.locator('[data-warehouse-op="rename"][data-id="1"]').click()
    expect(page.locator("#warehouse-rows")).to_contain_text("Север новый")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator('[data-warehouse-op="archive"][data-id="1"]').click()
    expect(page.locator("#warehouse-rows tr").filter(has_text="Север новый")).to_contain_text("Архив")
    view("stocks")
    page.locator("#stocks-search").fill("SKU-101")
    expect(page.locator("#stocks-rows tr").filter(has_text="Север новый")).to_contain_text("Архив")
    assert stocks()[1] == (3, 0, 3)
    page.locator("#stocks-show-archived").uncheck()
    expect(page.locator("#stocks-rows")).not_to_contain_text("Север новый")
    view("history")
    expect(page.locator("#history-rows")).to_contain_text("Маркетплейс")
    expect(page.locator("#history-rows")).to_contain_text("Покупатель")
    page.locator("#history-type").select_option("TRANSFER_RECEIVED")
    page.locator("#history-filter-btn").click()
    expect(page.locator("#history-rows tr")).to_have_count(1)

    Path("/artifacts").mkdir(exist_ok=True)
    page.screenshot(path="/artifacts/history.png", full_page=True)
    # Exercise the visible error banner for a failed catalogue request.
    page.route("**/products", lambda route: route.fulfill(status=503, json={"detail": "Каталог временно недоступен"}))
    page.locator("#refresh-btn").click()
    expect(page.locator("#global-error")).to_contain_text("товары: Каталог временно недоступен")
    page.unroute("**/products")
    page.locator("#refresh-btn").click()
    expect(page.locator("#global-error")).to_be_hidden()
    view("overview")
    page.screenshot(path="/artifacts/overview.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path="/artifacts/mobile.png", full_page=True)
    assert not errors, errors
    print("UI smoke passed: all forms, FBS/FBO/transfers, shortage, archive, history and API errors; no JS errors")
    browser.close()
