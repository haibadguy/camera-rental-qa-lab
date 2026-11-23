"""Exercise the live demo on a disposable Compose database."""

import base64
import json
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4
from zoneinfo import ZoneInfo

BASE = "http://127.0.0.1:8000"


class WebClient:
    def __init__(self):
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(self, path, *, form=None, payload=None, credentials=None, expected=200):
        headers = {}
        data = None
        if form is not None:
            csrf = next(
                cookie.value for cookie in self.cookies if cookie.name == "csrftoken"
            )
            data = urlencode(form | {"csrfmiddlewaretoken": csrf}).encode()
        if payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        if credentials:
            token = base64.b64encode(":".join(credentials).encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        request = Request(BASE + path, data=data, headers=headers)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            body = response.read().decode("utf-8")
            if response.code != expected:
                raise AssertionError(
                    f"{path}: expected HTTP {expected}, received {response.code}: {body[:500]}"
                )
            if response.headers.get_content_type() == "application/json":
                return json.loads(body)
            return body

    def login(self, username, password):
        self.request("/login/")
        self.request("/login/", form={"username": username, "password": password})


def main():
    customer, staff, api = WebClient(), WebClient(), WebClient()
    username = f"smoke-{uuid4().hex[:10]}"
    password = f"Camera-{uuid4().hex}"
    customer.request("/register/")
    assert "Đã tạo tài khoản" in customer.request(
        "/register/",
        form={"username": username, "password1": password, "password2": password},
    )
    customer.login(username, password)
    customer.request("/staff/equipment/", expected=403)
    staff_name, staff_password = "demo-staff", "camera-demo-2026"
    staff_credentials = (staff_name, staff_password)
    staff.login(staff_name, staff_password)
    assert "Có thực tế trong kho" in staff.request("/staff/equipment/")

    equipment = api.request("/api/equipment/?search=LEN-001&kind=LENS")[0]
    detail_url = f"/equipment/{equipment['id']}/"
    assert "Sigma 30mm" in customer.request(detail_url)
    customer.request("/static/catalog/site.css")
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    tomorrow = today + timedelta(days=1)
    period = {"pickup_date": today.isoformat(), "return_date": tomorrow.isoformat()}
    listing_url = "/api/equipment/?search=LEN-001&" + urlencode(period)
    assert api.request(listing_url)[0]["available_stock"] == 2
    assert "Còn 2 thiết bị theo lịch đã chọn." in customer.request(
        detail_url + "?" + urlencode(period)
    )

    credentials = (username, password)
    booking = {"equipment_id": equipment["id"], "quantity": 1}
    rental = api.request(
        "/api/rentals/", payload=booking | period, credentials=credentials, expected=201
    )
    order = rental["id"]
    assert "Đã đặt" in customer.request(f"/rentals/{order}/")
    assert api.request(listing_url)[0]["available_stock"] == 1
    ops_url = f"/api/v2/operations/rentals/{order}/"
    api.request(ops_url, credentials=credentials, expected=403)
    reservation = api.request(ops_url, credentials=staff_credentials)["reservations"][0]
    api.request(
        f"{ops_url}reservations/{reservation['id']}/prepare/",
        payload={"notes": "Kiểm tra thiết bị trước giao."},
        credentials=staff_credentials,
        expected=204,
    )
    api.request(
        f"{ops_url}pick-up/", payload={}, credentials=staff_credentials, expected=409
    )
    finance_entry = f"{ops_url}finance/entries/"
    receipt = {
        "kind": "RENT_RECEIPT",
        "amount_vnd": rental["total_vnd"],
        "method": "CASH",
        "command_id": str(uuid4()),
    }
    api.request(finance_entry, payload=receipt, credentials=credentials, expected=403)
    first = api.request(
        finance_entry, payload=receipt, credentials=staff_credentials, expected=201
    )
    repeated = api.request(
        finance_entry, payload=receipt, credentials=staff_credentials, expected=201
    )
    assert first["id"] == repeated["id"]
    assert "Sổ giao dịch" in staff.request(f"/staff/rentals/{order}/finance/")
    assert "Đã bàn giao" in staff.request(
        f"/staff/rentals/{order}/operations/", form={"action": "pick_up"}
    )
    api.request(
        f"/api/rentals/{order}/return/",
        payload={},
        credentials=staff_credentials,
        expected=409,
    )
    handover = api.request(ops_url, credentials=staff_credentials)["handovers"][0]
    item_url = f"{ops_url}handovers/{handover['id']}/"
    api.request(
        f"{item_url}receive/", payload={}, credentials=staff_credentials, expected=204
    )
    api.request(
        f"{item_url}inspect/",
        payload={"result": "READY"},
        credentials=staff_credentials,
        expected=204,
    )
    result = api.request(
        f"/api/rentals/{order}/",
        credentials=credentials,
    )
    assert (
        result["status"] == "RETURNED"
        and result["picked_up_at"]
        and result["returned_at"]
    )
    assert api.request(listing_url)[0]["available_stock"] == 1

    future = {
        "pickup_date": tomorrow.isoformat(),
        "return_date": (tomorrow + timedelta(days=1)).isoformat(),
    }
    cancellable = api.request(
        "/api/rentals/", payload=booking | future, credentials=credentials, expected=201
    )
    order = cancellable["id"]
    entry_url = f"/api/v2/operations/rentals/{order}/finance/entries/"
    paid = {
        "kind": "RENT_RECEIPT",
        "amount_vnd": 50_000,
        "method": "CASH",
        "command_id": str(uuid4()),
    }
    api.request(entry_url, payload=paid, credentials=staff_credentials, expected=201)
    assert "Đã hủy đơn thuê" in customer.request(f"/rentals/{order}/cancel/", form={})
    assert (
        api.request(f"/api/rentals/{order}/", credentials=credentials)["status"]
        == "CANCELLED"
    )
    summary_url = f"/api/v2/rentals/{order}/finance/"
    assert (
        api.request(summary_url, credentials=credentials)["rent_to_refund_vnd"]
        == "50000"
    )
    api.request(
        entry_url,
        payload=paid | {"kind": "RENT_REFUND", "command_id": str(uuid4())},
        credentials=staff_credentials,
        expected=201,
    )
    assert (
        api.request(summary_url, credentials=credentials)["rent_to_refund_vnd"] == "0"
    )
    print(
        "PASS: live booking, finance authorization and retry, pickup, early return, inspection, cancellation and refund"
    )

    camera = api.request("/api/equipment/?search=CAM-001")[0]
    assert "Kỳ thuê chung" in customer.request("/rentals/new/")
    customer.request(
        "/rentals/new/",
        form=future | {f"quantity_{camera['id']}": 1, f"quantity_{equipment['id']}": 1},
    )
    multi = api.request("/api/v2/rentals/", credentials=credentials)[0]
    assert len(multi["lines"]) == 2
    multi_id = multi["id"]
    api.request(f"/api/rentals/{multi_id}/", credentials=credentials, expected=404)
    changes = f"/api/v2/rentals/{multi_id}/changes/"
    proposed = {
        "kind": "RESCHEDULE",
        "pickup_date": (tomorrow + timedelta(days=2)).isoformat(),
        "return_date": (tomorrow + timedelta(days=4)).isoformat(),
    }
    quote = api.request(changes + "quote/", payload=proposed, credentials=credentials)
    assert quote["consent_required"] and quote["total_vnd"] == "900000"
    change = api.request(
        changes,
        payload=proposed | {"accepted_total_vnd": quote["total_vnd"]},
        credentials=credentials,
        expected=201,
    )
    review = api.request(
        f"/api/v2/operations/changes/{change['id']}/review/",
        payload={"approve": True},
        credentials=staff_credentials,
    )
    assert review["status"] == "APPROVED"
    assert "Đã duyệt" in customer.request(f"/rentals/{multi_id}/")
    calendar = staff.request(f"/staff/equipment/{camera['id']}/assets/")
    assert f"Đơn #{multi_id}" in calendar and "CAM-001-U" in calendar
    cancelled = api.request(
        f"/api/v2/rentals/{multi_id}/cancel/", payload={}, credentials=credentials
    )
    assert cancelled["status"] == "CANCELLED"
    print(
        "PASS: multi-SKU web booking, v2 quote and approval, staff asset calendar and full cancellation"
    )


if __name__ == "__main__":
    main()
