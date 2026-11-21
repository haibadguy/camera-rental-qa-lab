# R01 — Kết quả kiểm tra danh mục

**Build:** Bản làm việc R01 trên Windows, dựa trên `0e9139e`, có quy trình khởi động Compose một lệnh. Chưa commit.

| Kiểm tra | Trạng thái | Kết quả thực tế |
| --- | --- | --- |
| Cú pháp Python và cấu hình Compose | Pass | `python -m compileall -q manage.py config catalog` và `docker compose config --quiet` trả mã thoát 0. |
| Khởi động Django và PostgreSQL | Blocked | `docker compose up --build --wait` trả `permission denied while trying to connect to the docker API` khi phiên Codex kết nối `dockerDesktopLinuxEngine`. |
| Bốn test Django | Not Run | `docker compose run --rm web python manage.py test` cần Docker Engine. Dữ liệu kiểm tra gồm bản ghi thử `CAM-900`, danh mục rỗng, ba thiết bị mẫu và bản ghi `CAM-001` đã được chỉnh sửa. |
| TC-R01-01 trên trình duyệt | Not Run | Chưa xác nhận kết quả trên bản làm việc này. |

## TC-R01-01 — Hiển thị đúng mã, tên và giá thuê

**Tiền điều kiện:** `docker compose up --build --wait` đã thành công với cơ sở dữ liệu demo mới theo [hướng dẫn](../setup.md).

**Bước thực hiện:** Mở [danh mục thiết bị](http://localhost:8000/), tìm thẻ `CAM-001` và đọc tên cùng giá thuê trên thẻ đó.

**Expected Result:** Cùng một thẻ hiển thị `CAM-001`, `Sony A6400` và `300.000 ₫/ngày`.

**Actual Result:** Chưa quan sát. Điền kết quả và phiên bản kiểm thử sau lượt chạy trên trình duyệt.
