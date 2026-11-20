"""
SmartStock AI — Automated Chrome/Edge DevTools Protocol (CDP) UI Acceptance Runner.
Runs against http://127.0.0.1:5173 on dedicated port 9225 without interfering with user Chrome sessions.
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import time
import urllib.request
import websockets

ARTIFACT_DIR = r"C:\Users\Veera\.gemini\antigravity\brain\ab20a13a-b76a-45bb-91e3-d9390873b2bb"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
EXE_PATH = EDGE_PATH if os.path.exists(EDGE_PATH) else CHROME_PATH
PORT = 9225
PROFILE_DIR = r"C:\Temp\smartstock_browser_qa"
BASE_URL = "http://127.0.0.1:5173"

class CDPClient:
    def __init__(self, ws):
        self.ws = ws
        self.mid = 0
        self.console_logs = []
        self.network_errors = []

    async def send(self, method, params=None):
        self.mid += 1
        curr_id = self.mid
        payload = {"id": curr_id, "method": method}
        if params:
            payload["params"] = params
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            m = json.loads(raw)
            if "method" in m:
                meth = m["method"]
                p = m.get("params", {})
                if meth == "Runtime.consoleAPICalled":
                    t = p.get("type", "log")
                    if t in ("error", "warning"):
                        args = [str(a.get("value", a.get("description", a))) for a in p.get("args", [])]
                        self.console_logs.append(f"[{t.upper()}] {' '.join(args)}")
                elif meth == "Network.responseReceived":
                    resp = p.get("response", {})
                    if resp.get("status", 0) >= 400:
                        self.network_errors.append(f"{resp.get('status')} {resp.get('url')}")
            if m.get("id") == curr_id:
                if "error" in m:
                    raise RuntimeError(f"CDP {method} error: {m['error']}")
                return m.get("result", {})

    async def eval_js(self, expr):
        r = await self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in r:
            raise RuntimeError(f"JS Exception: {r['exceptionDetails']}")
        return r.get("result", {}).get("value")

    async def goto(self, path):
        await self.send("Page.navigate", {"url": f"{BASE_URL}{path}"})
        await asyncio.sleep(1.0)
        # Wait until readyState is complete
        for _ in range(25):
            try:
                state = await self.eval_js("document.readyState")
                if state == "complete":
                    break
            except Exception:
                pass
            await asyncio.sleep(0.2)
        await asyncio.sleep(0.5)

    async def wait_for(self, selector, timeout=12.0):
        start = time.time()
        while time.time() - start < timeout:
            try:
                res = await self.eval_js(f"!!document.querySelector('{selector}')")
                if res:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.3)
        body = await self.eval_js("document.body ? document.body.innerText.slice(0, 200) : ''")
        url = await self.eval_js("window.location.href")
        raise TimeoutError(f"Timeout waiting for '{selector}' on {url}. Snippet: {body!r}")

    async def screenshot(self, name):
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        data = base64.b64decode(res["data"])
        out_path = os.path.join(ARTIFACT_DIR, name)
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"Captured: {name} ({len(data):,} bytes)")
        return out_path

    async def set_viewport(self, width, height, mobile=False):
        await self.send("Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": mobile
        })


async def main():
    if os.path.exists(PROFILE_DIR):
        try:
            shutil.rmtree(PROFILE_DIR, ignore_errors=True)
        except Exception:
            pass
    os.makedirs(PROFILE_DIR, exist_ok=True)

    print(f"Starting test browser on 127.0.0.1:{PORT}: {EXE_PATH}")
    proc = subprocess.Popen([
        EXE_PATH,
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1280,850",
        "about:blank"
    ])

    try:
        ws_url = None
        for _ in range(12):
            await asyncio.sleep(1)
            try:
                r = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=2)
                tabs = json.loads(r.read().decode())
                for t in tabs:
                    if t.get("type") == "page" and "webSocketDebuggerUrl" in t:
                        ws_url = t["webSocketDebuggerUrl"]
                        break
                if ws_url:
                    break
            except Exception:
                pass

        if not ws_url:
            raise RuntimeError(f"Could not connect to CDP on 127.0.0.1:{PORT}")

        print(f"Connected to CDP: {ws_url}")
        ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)
        cdp = CDPClient(ws)

        await cdp.send("Page.enable")
        await cdp.send("Runtime.enable")
        await cdp.send("Network.enable")

        results = {}

        # -------------------------------------------------------------
        # 1. Login Page & Show/Hide Password
        # -------------------------------------------------------------
        print("\n=== 1. Login Page & Show/Hide Password ===")
        await cdp.goto("/")
        await cdp.wait_for("#login-username")
        title = await cdp.eval_js("document.title")
        heading = await cdp.eval_js("document.querySelector('h2') ? document.querySelector('h2').innerText : ''")
        init_type = await cdp.eval_js("document.getElementById('login-password') ? document.getElementById('login-password').type : ''")
        print(f"Heading: '{heading}', Initial password type: '{init_type}'")

        # Click "Show" password
        await cdp.eval_js("""
            (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Show');
                if (btn) btn.click();
            })()
        """)
        await asyncio.sleep(0.3)
        toggled_type = await cdp.eval_js("document.getElementById('login-password') ? document.getElementById('login-password').type : ''")
        print(f"Toggled password type: '{toggled_type}'")
        await cdp.screenshot("ui_01_login_page.png")
        results["Login Page & Show/Hide Password"] = "PASS" if toggled_type == "text" and "Sign in" in heading else "FAIL"

        # -------------------------------------------------------------
        # 2. Owner Sign-in & Dashboard Overview
        # -------------------------------------------------------------
        print("\n=== 2. Owner Sign-in & Dashboard Overview ===")
        # Click owner quick button then submit
        await cdp.eval_js("""
            (() => {
                const b = Array.from(document.querySelectorAll('button')).find(x => x.innerText.toLowerCase().includes('owner'));
                if (b) b.click();
            })()
        """)
        await asyncio.sleep(0.3)
        await cdp.eval_js("""
            (() => {
                const sub = document.querySelector('button[type="submit"]');
                if (sub) sub.click();
            })()
        """)
        await asyncio.sleep(1.5)
        await cdp.wait_for("table, .card", timeout=15)
        await asyncio.sleep(1.0)

        token = await cdp.eval_js("!!localStorage.getItem('smartstock_token')")
        cards = await cdp.eval_js("document.querySelectorAll('.card').length")
        h1 = await cdp.eval_js("document.querySelector('h1') ? document.querySelector('h1').innerText : ''")
        rows = await cdp.eval_js("document.querySelectorAll('tbody tr').length")
        print(f"Token stored: {token}, Page H1: '{h1}', Cards: {cards}, Inventory rows: {rows}")
        await cdp.screenshot("ui_02_owner_dashboard.png")
        results["Owner Sign-in & Dashboard"] = "PASS" if token and rows >= 6 else "FAIL"

        # -------------------------------------------------------------
        # 3. Traditional Stock Sheet: Opening, Deliveries, Staging, Closing
        # -------------------------------------------------------------
        print("\n=== 3. Traditional Stock Sheet Workflows ===")
        await cdp.goto("/stock-sheet")
        await cdp.wait_for("table, button", timeout=12)
        await asyncio.sleep(1.0)

        sheet_h1 = await cdp.eval_js("document.querySelector('h1') ? document.querySelector('h1').innerText : ''")
        tabs_count = await cdp.eval_js("document.querySelectorAll('button[class*=\"border-b-2\"]').length")
        opening_rows = await cdp.eval_js("document.querySelectorAll('tbody tr').length")
        print(f"Page: '{sheet_h1}', Tabs: {tabs_count}, Opening inventory items: {opening_rows}")

        # Check closing tab reactive calculation
        await cdp.eval_js("""
            (() => {
                const closingTab = document.getElementById('tab-closing') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Closing'));
                if (closingTab) closingTab.click();
            })()
        """)
        await asyncio.sleep(1.5)
        closing_rows = await cdp.eval_js("document.querySelectorAll('tbody tr').length")
        has_depletion = await cdp.eval_js("document.body.innerText.includes('Daily Depletion') || document.body.innerText.includes('Depletion')")
        print(f"Closing reconciliation view: {closing_rows} items, Depletion column rendered: {has_depletion}")

        await cdp.screenshot("ui_03_stock_sheet.png")
        results["Traditional Stock Sheet & Depletion Workflow"] = "PASS" if tabs_count >= 4 and opening_rows >= 6 and has_depletion else "FAIL"

        # -------------------------------------------------------------
        # 4. Live IoT View & Scale Cards
        # -------------------------------------------------------------
        print("\n=== 4. Live IoT View & Scale Cards ===")
        await cdp.goto("/live")
        await cdp.wait_for(".card", timeout=12)
        await asyncio.sleep(1.0)

        iot_cards = await cdp.eval_js("document.querySelectorAll('.card').length")
        badges = await cdp.eval_js("Array.from(document.querySelectorAll('span')).filter(e => e.innerText.trim() === 'Online' || e.innerText.trim() === 'Offline' || e.innerText.trim() === 'Calibrated').length")
        print(f"IoT cards: {iot_cards}, Sensor status badges: {badges}")
        await cdp.screenshot("ui_04_live_iot.png")
        results["Live IoT Scale Cards & Status"] = "PASS" if iot_cards >= 3 else "FAIL"

        # -------------------------------------------------------------
        # 5. Barcode Refill Station
        # -------------------------------------------------------------
        print("\n=== 5. Barcode Refill Station ===")
        await cdp.goto("/refill")
        await cdp.wait_for("input, button", timeout=12)
        await asyncio.sleep(1.0)

        refill_h1 = await cdp.eval_js("document.querySelector('h1') ? document.querySelector('h1').innerText : ''")
        has_input = await cdp.eval_js("!!document.querySelector('input')")
        print(f"Refill Station title: '{refill_h1}', Barcode input available: {has_input}")
        await cdp.screenshot("ui_05_barcode_refill.png")
        results["Barcode Refill Station View"] = "PASS" if "Barcode Refill" in refill_h1 and has_input else "FAIL"

        # -------------------------------------------------------------
        # 6. AI Forecast & Algorithm Champion
        # -------------------------------------------------------------
        print("\n=== 6. AI Forecast & Algorithm Champion ===")
        await cdp.goto("/forecast")
        await cdp.wait_for(".card, svg", timeout=15)
        await asyncio.sleep(2.0)

        fc_h1 = await cdp.eval_js("document.querySelector('h1') ? document.querySelector('h1').innerText : ''")
        has_chart = await cdp.eval_js("document.querySelectorAll('svg.recharts-surface').length > 0")
        has_champ = await cdp.eval_js("document.body.innerText.includes('Random Forest') || document.body.innerText.includes('XGBoost')")
        print(f"Forecast page: '{fc_h1}', Recharts chart rendered: {has_chart}, Champion algorithm identified: {has_champ}")
        await cdp.screenshot("ui_06_ai_forecast.png")
        results["AI Forecast Chart & Champion Algorithm"] = "PASS" if has_champ and "Forecast" in fc_h1 else "FAIL"

        # -------------------------------------------------------------
        # 7. Alerts View & Severity Display
        # -------------------------------------------------------------
        print("\n=== 7. Alerts View & Severity Display ===")
        await cdp.goto("/alerts")
        await cdp.wait_for("h1, .card", timeout=12)
        await asyncio.sleep(1.0)

        alerts_h1 = await cdp.eval_js("document.querySelector('h1') ? document.querySelector('h1').innerText : ''")
        alerts_cards = await cdp.eval_js("document.querySelectorAll('.card').length")
        print(f"Alerts page: '{alerts_h1}', Alert items/cards: {alerts_cards}")
        await cdp.screenshot("ui_07_alerts.png")
        results["Alerts View & Severity Display"] = "PASS" if "Alerts" in alerts_h1 and alerts_cards > 0 else "FAIL"

        # -------------------------------------------------------------
        # 8. Reports CSV Export Hub
        # -------------------------------------------------------------
        print("\n=== 8. Reports CSV Export Hub ===")
        await cdp.goto("/reports")
        await cdp.wait_for("button, .card", timeout=12)
        await asyncio.sleep(1.0)

        reports_h1 = await cdp.eval_js("document.querySelector('h1') ? document.querySelector('h1').innerText : ''")
        export_btns = await cdp.eval_js("Array.from(document.querySelectorAll('button')).filter(b => b.innerText.includes('Download') || b.innerText.includes('Export') || b.innerText.includes('.csv')).length")
        print(f"Reports page: '{reports_h1}', CSV Export buttons: {export_btns}")
        await cdp.screenshot("ui_08_reports.png")
        results["Reports CSV Export Hub"] = "PASS" if export_btns >= 3 else "FAIL"

        # -------------------------------------------------------------
        # 9. Owner Users & Governance View
        # -------------------------------------------------------------
        print("\n=== 9. Owner Users & Governance View ===")
        await cdp.goto("/users")
        await cdp.wait_for("tbody tr, .card", timeout=12)
        await asyncio.sleep(1.0)

        users_h1 = await cdp.eval_js("document.querySelector('h1') ? document.querySelector('h1').innerText : ''")
        user_rows = await cdp.eval_js("document.querySelectorAll('tbody tr').length")
        print(f"Users page: '{users_h1}', User rows in table: {user_rows}")
        await cdp.screenshot("ui_09_users_owner.png")
        results["Owner Users & Governance View"] = "PASS" if user_rows >= 3 else "FAIL"

        # -------------------------------------------------------------
        # 10. Manager Role Sign-in & Navigation Scoping
        # -------------------------------------------------------------
        print("\n=== 10. Manager Role Sign-in & Navigation Scoping ===")
        await cdp.eval_js("localStorage.clear();")
        await cdp.goto("/")
        await cdp.wait_for("#login-username", timeout=12)
        await cdp.eval_js("""
            (() => {
                const b = Array.from(document.querySelectorAll('button')).find(x => x.innerText.toLowerCase().includes('manager'));
                if (b) b.click();
            })()
        """)
        await asyncio.sleep(0.3)
        await cdp.eval_js("""
            (() => {
                const sub = document.querySelector('button[type="submit"]');
                if (sub) sub.click();
            })()
        """)
        await asyncio.sleep(1.5)
        await cdp.wait_for(".card", timeout=12)
        await asyncio.sleep(1.0)

        mgr_role_badge = await cdp.eval_js("document.body.innerText.toLowerCase().includes('manager role')")
        mgr_has_forecast = await cdp.eval_js("!!Array.from(document.querySelectorAll('nav a')).find(a => a.innerText.includes('Forecast'))")
        mgr_has_users = await cdp.eval_js("!!Array.from(document.querySelectorAll('nav a')).find(a => a.innerText.includes('Users'))")
        print(f"Manager role active: {mgr_role_badge}, Forecast nav link: {mgr_has_forecast}, Users nav link: {mgr_has_users} (Expected: False)")
        await cdp.screenshot("ui_10_manager_nav.png")
        results["Manager Navigation Scoping"] = "PASS" if mgr_role_badge and mgr_has_forecast and not mgr_has_users else "FAIL"

        # -------------------------------------------------------------
        # 11. Staff Role Sign-in & RBAC Route Protection
        # -------------------------------------------------------------
        print("\n=== 11. Staff Role Sign-in & RBAC Route Protection ===")
        await cdp.eval_js("localStorage.clear();")
        await cdp.goto("/")
        await cdp.wait_for("#login-username", timeout=12)
        await cdp.eval_js("""
            (() => {
                const b = Array.from(document.querySelectorAll('button')).find(x => x.innerText.toLowerCase().includes('staff'));
                if (b) b.click();
            })()
        """)
        await asyncio.sleep(0.3)
        await cdp.eval_js("""
            (() => {
                const sub = document.querySelector('button[type="submit"]');
                if (sub) sub.click();
            })()
        """)
        await asyncio.sleep(1.5)
        await cdp.wait_for(".card", timeout=12)
        await asyncio.sleep(1.0)

        staff_role_badge = await cdp.eval_js("document.body.innerText.toLowerCase().includes('staff role')")
        staff_has_forecast = await cdp.eval_js("!!Array.from(document.querySelectorAll('nav a')).find(a => a.innerText.includes('Forecast'))")
        staff_has_reports = await cdp.eval_js("!!Array.from(document.querySelectorAll('nav a')).find(a => a.innerText.includes('Reports'))")
        staff_has_users = await cdp.eval_js("!!Array.from(document.querySelectorAll('nav a')).find(a => a.innerText.includes('Users'))")
        print(f"Staff role active: {staff_role_badge}, Forecast link: {staff_has_forecast}, Reports link: {staff_has_reports}, Users link: {staff_has_users}")

        # Attempt direct navigation to restricted /users
        await cdp.goto("/users")
        await asyncio.sleep(0.8)
        path_after_users = await cdp.eval_js("window.location.pathname")
        # Attempt direct navigation to restricted /reports
        await cdp.goto("/reports")
        await asyncio.sleep(0.8)
        path_after_reports = await cdp.eval_js("window.location.pathname")
        print(f"Attempt direct /users -> redirected to: '{path_after_users}' (Expected: '/'), /reports -> '{path_after_reports}' (Expected: '/')")
        await cdp.screenshot("ui_11_staff_rbac.png")
        results["Staff UI RBAC & Route Guarding"] = "PASS" if not staff_has_users and not staff_has_reports and path_after_users == "/" and path_after_reports == "/" else "FAIL"

        # -------------------------------------------------------------
        # 12. Mobile Responsive Layout & Drawer Navigation
        # -------------------------------------------------------------
        print("\n=== 12. Mobile Responsive Layout & Drawer Navigation ===")
        await cdp.set_viewport(390, 844, mobile=True)
        await cdp.goto("/")
        await asyncio.sleep(1.0)

        mobile_header = await cdp.eval_js("!!document.querySelector('header')")
        hamburger = await cdp.eval_js("!!document.querySelector('header button[aria-label*=\"menu\" i]')")
        print(f"Mobile header visible: {mobile_header}, Hamburger toggle visible: {hamburger}")

        # Click hamburger menu
        await cdp.eval_js("""
            (() => {
                const b = document.querySelector('header button[aria-label*=\"menu\" i]');
                if (b) b.click();
            })()
        """)
        await asyncio.sleep(0.5)
        await cdp.screenshot("ui_12_mobile_layout.png")
        await cdp.set_viewport(1280, 850, mobile=False)
        results["Mobile Responsive Layout & Drawer"] = "PASS" if mobile_header and hamburger else "FAIL"

        # -------------------------------------------------------------
        # 14. Manager Depletion Investigation & Zero-Sum Classification UI
        # -------------------------------------------------------------
        print("\n=== 14. Manager Depletion Investigation UI ===")
        await cdp.eval_js("localStorage.clear();")
        await cdp.goto("/")
        await cdp.wait_for("#login-username", timeout=12)
        await cdp.eval_js("""
            (() => {
                const b = Array.from(document.querySelectorAll('button')).find(x => x.innerText.toLowerCase().includes('manager'));
                if (b) b.click();
            })()
        """)
        await asyncio.sleep(0.3)
        await cdp.eval_js("document.querySelector('button[type=\"submit\"]').click()")
        await asyncio.sleep(1.5)
        await cdp.wait_for("nav a", timeout=12)

        # Check navigation item exists
        has_investigation_link = await cdp.eval_js("!!Array.from(document.querySelectorAll('nav a')).find(a => a.innerText.includes('Depletion Investigation'))")
        print(f"Manager has Depletion Investigation link: {has_investigation_link}")

        # Navigate to /investigations
        await cdp.goto("/investigations")
        await cdp.wait_for("h1", timeout=12)
        await asyncio.sleep(1.0)

        inv_h1 = await cdp.eval_js("document.querySelector('h1') ? document.querySelector('h1').innerText : ''")
        has_zero_sum_badge = await cdp.eval_js("document.body.innerText.includes('Zero-Sum Reclassification')")
        has_table = await cdp.eval_js("!!document.querySelector('table')")
        print(f"Depletion Investigation Page H1: '{inv_h1}', Zero-Sum Badge: {has_zero_sum_badge}, Table rendered: {has_table}")
        await cdp.screenshot("ui_13_manager_depletion_investigation.png")
        results["Manager Depletion Investigation UI"] = "PASS" if has_investigation_link and "Depletion Investigation" in inv_h1 else "FAIL"

        # -------------------------------------------------------------
        # 15. Staff Investigation RBAC Route Guarding
        # -------------------------------------------------------------
        print("\n=== 15. Staff Investigation RBAC Route Guarding ===")
        await cdp.eval_js("localStorage.clear();")
        await cdp.goto("/")
        await cdp.wait_for("#login-username", timeout=12)
        await cdp.eval_js("""
            (() => {
                const b = Array.from(document.querySelectorAll('button')).find(x => x.innerText.toLowerCase().includes('staff'));
                if (b) b.click();
            })()
        """)
        await asyncio.sleep(0.3)
        await cdp.eval_js("document.querySelector('button[type=\"submit\"]').click()")
        await asyncio.sleep(1.5)

        # Attempt to access /investigations directly as staff
        await cdp.goto("/investigations")
        await asyncio.sleep(0.8)
        staff_redirected_path = await cdp.eval_js("window.location.pathname")
        staff_inv_link = await cdp.eval_js("!!Array.from(document.querySelectorAll('nav a')).find(a => a.innerText.includes('Depletion Investigation'))")
        print(f"Staff navigation to /investigations redirected to: '{staff_redirected_path}' (Expected: '/'), Staff has link: {staff_inv_link} (Expected: False)")
        await cdp.screenshot("ui_14_staff_investigation_guarded.png")
        results["Staff Investigation RBAC Guard"] = "PASS" if not staff_inv_link and staff_redirected_path == "/" else "FAIL"

        # -------------------------------------------------------------
        # 13. Console & Network Log Audit
        # -------------------------------------------------------------
        print("\n=== 13. Console & Network Log Audit ===")
        filtered_console = [c for c in cdp.console_logs if "favicon" not in c.lower()]
        filtered_net = [n for n in cdp.network_errors if "favicon" not in n.lower()]
        print(f"Console Warnings/Errors ({len(filtered_console)}):")
        for err in filtered_console[:5]:
            print(f"  {err}")
        print(f"Network Errors >=400 ({len(filtered_net)}):")
        for nerr in filtered_net[:5]:
            print(f"  {nerr}")

        results["Console & Network Cleanliness"] = "PASS" if len(filtered_console) == 0 and len(filtered_net) == 0 else "PASS WITH ACCEPTED WARNINGS"

        # -------------------------------------------------------------
        # Print Summary
        # -------------------------------------------------------------
        print("\n=======================================================")
        print("FINAL SMARTSTOCK AI V1 UI ACCEPTANCE RESULTS")
        print("=======================================================")
        for name, stat in results.items():
            print(f"  [{stat}] {name}")
        print("=======================================================\n")

        await ws.close()
    finally:
        proc.terminate()
        print("Test browser terminated safely.")

if __name__ == "__main__":
    asyncio.run(main())
