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
    assert "Đã bàn giao" in staff.request(f"/staff/rentals/{order}/pick-up/", form={})
    result = api.request(
        f"/api/rentals/{order}/return/",
        payload={},
        credentials=(staff_name, staff_password),
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
    assert "Đã hủy đơn thuê" in customer.request(f"/rentals/{order}/cancel/", form={})
    assert (
        api.request(f"/api/rentals/{order}/", credentials=credentials)["status"]
        == "CANCELLED"
    )
    print(
        "PASS: live registration, login, authorization, catalog, availability, booking, pickup, early return and cancellation"
    )


if __name__ == "__main__":
    main()
