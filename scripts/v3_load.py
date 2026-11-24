"""Exercise HTTP against an isolated server seeded by manage.py seed_scale."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from http.client import HTTPConnection, HTTPSConnection
from json import dumps, loads
from math import ceil
from os import environ
from queue import Empty, SimpleQueue
from random import Random
from time import monotonic, sleep
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.test import Client
from django.utils import timezone

from catalog.models import Equipment, Rental


class Session:
    def __init__(self, url, host, user=None):
        target = urlsplit(url)
        connect = HTTPSConnection if target.scheme == "https" else HTTPConnection
        self.http = connect(target.hostname, target.port, timeout=12)
        self.headers = {"Host": host, "Accept": "application/json"}
        if user is not None:
            client = Client()
            client.force_login(user)
            login = client.get("/login/", HTTP_HOST=host, secure=target.scheme == "https")
            csrf_token = get_token(login.wsgi_request)
            secret = client.cookies["csrftoken"].value
            self.headers |= {
                "Cookie": f"sessionid={client.cookies['sessionid'].value}; csrftoken={secret}",
                "X-CSRFToken": csrf_token,
                "Referer": f"{target.scheme}://{host}/",
            }

    def request(self, path, body=None):
        headers = self.headers.copy()
        data = None
        if body is not None:
            data = dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        try:
            self.http.request("GET" if data is None else "POST", path, data, headers)
            response = self.http.getresponse()
            payload = response.read()
            return response.status, payload
        except (OSError, TimeoutError):
            self.http.close()
            return 0, b""


def workload(config):
    today = timezone.localdate()
    days = tuple(today + timedelta(days=index) for index in range(1, 32))
    report_period = urlencode({"first": today - timedelta(days=360), "last": today})
    sku_ids = list(Equipment.objects.filter(code__startswith="SCALE-").values_list("pk", flat=True))
    history_ids = list(Rental.objects.filter(
        equipment__code__startswith="SCALE-"
    ).values_list("pk", flat=True)[:200])
    if not sku_ids or not history_ids:
        raise SystemExit("Run seed_scale on the benchmark database first.")
    users = get_user_model().objects
    staff = users.get(username="scale-staff")
    customers = list(users.filter(username__startswith="scale-customer-").order_by("pk"))
    roster = [
        (Session(config.url, config.host), Session(config.url, config.host, staff),
         Session(config.url, config.host, customers[index % len(customers)]))
        for index in range(config.users)
    ]
    orders_to_prepare = SimpleQueue()
    finish_warmup = monotonic() + config.warmup
    deadline = finish_warmup + config.duration

    def worker(index):
        anon, office, renter = roster[index]
        rng = Random(index + 81)
        recorded = defaultdict(list)
        count = Counter()
        while monotonic() < deadline:
            draw = rng.randrange(100)
            day_index = rng.randrange(len(days) - 1)
            dates = {"pickup_date": str(days[day_index]), "return_date": str(days[day_index + 1])}
            started = monotonic()
            if draw < 60:
                action = "catalog"
                status, _ = anon.request("/api/v3/catalog/?" + urlencode(dates))
            elif draw < 85:
                action = "operations"
                try:
                    order_id = orders_to_prepare.get_nowait()
                except Empty:
                    order_id = None
                target = order_id or rng.choice(history_ids)
                status, payload = office.request(f"/api/v2/operations/rentals/{target}/")
                if order_id and status == 200:
                    codes = [hold["asset_code"] for hold in loads(payload)["reservations"]]
                    status, _ = office.request(f"/api/v3/operations/orders/{target}/scan/", {
                        "command_id": str(uuid4()), "action": "PREPARE", "codes": codes,
                    })
            elif draw < 95:
                action = "book"
                hot = rng.randrange(10) == 0
                item = sku_ids[0] if hot else rng.choice(sku_ids)
                status, payload = renter.request("/api/v2/rentals/", dates | {
                    "lines": [{"equipment_id": item, "quantity": 1}],
                })
                if status == 201:
                    orders_to_prepare.put(loads(payload)["id"])
            else:
                action = "report"
                status, _ = office.request("/api/v3/management/reports/summary/?" + report_period)
            elapsed = (monotonic() - started) * 1000
            if started >= finish_warmup:
                recorded[action].append(elapsed)
                count[(action, status)] += 1
            sleep(config.think)
        for session in (anon, office, renter):
            session.http.close()
        return recorded, count

    timings = defaultdict(list)
    outcomes = Counter()
    with ThreadPoolExecutor(max_workers=config.users) as workers:
        for samples, count in workers.map(worker, range(config.users)):
            for action, values in samples.items():
                timings[action].extend(values)
            outcomes.update(count)

    targets = {"catalog": 300, "operations": 600, "book": 700, "report": 2000}
    passed = True
    print(dumps({"users": config.users, "duration_s": config.duration, "warmup_s": config.warmup,
                 "think_s": config.think, "sku_count": len(sku_ids)}))
    for action, target in targets.items():
        values = sorted(timings[action])
        p95 = round(values[ceil(len(values) * .95) - 1], 1) if values else None
        statuses = {code: count for (key, code), count in outcomes.items() if key == action}
        print(dumps({"action": action, "p95_ms": p95, "target_ms": target, "statuses": statuses}))
        passed &= p95 is not None and p95 <= target
    total = outcomes.total()
    failures = sum(count for (_, code), count in outcomes.items() if code == 0 or code >= 500)
    invalid = sum(count for (action, code), count in outcomes.items()
                  if 400 <= code < 500 and (code != 409 or action != "book"))
    print(dumps({"requests": total, "timeouts_or_5xx": failures, "unexpected_4xx": invalid}))
    return 0 if passed and total and failures / total < .001 and not invalid else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--users", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--think", type=float, default=2.5)
    raise SystemExit(workload(parser.parse_args()))
