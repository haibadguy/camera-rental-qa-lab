# Trạng thái xác minh Camera Rental Base v1.0

**NOT READY — BLOCKERS REMAIN**

Bản làm việc Windows ngày 21/11/2026 trên `main`, dựa trên `0e9139e`. Phạm vi là R01–R08 trong [đặc tả](requirements.md). Kiểm tra local đã đạt. GitHub Actions còn chờ một lần chạy trên bản có workflow.

| Mốc | Kết quả trên bản làm việc |
| --- | --- |
| M1 | Đã xác minh đăng ký, vòng đời đơn, kỳ thuê 1–30 ngày, `NO_SHOW` sau ngày nhận, tồn thực tế khi bàn giao và bảo toàn lịch khi trả sớm. Hai bài kiểm tra đồng thời trên PostgreSQL đạt. |
| M2 | Hoàn tất tra lịch tại trang chi tiết, giữ ngày sang form đặt, tiền tạm tính theo số lượng và định dạng VND dùng chung trên web. Có script dựng môi trường sạch, workflow và tài liệu bàn giao. Danh mục dùng minh họa CSS theo loại thiết bị. |
| M3 | Build, migration, seed, 22 test Django, HTTP smoke và kiểm tra giao diện đều đạt local. Đã rà phân quyền, thứ tự khóa, dữ liệu chuyển trạng thái và đường đi từ web/API tới service. GitHub Actions chưa chạy trên GitHub. |

## Kết quả đã quan sát

| Kiểm tra | Kết quả |
| --- | --- |
| `.\scripts\dev.ps1 -Action Verify -Port 18012` | Pass với Docker Desktop trên Windows. Project `camera-rental-qa-lab-1a33c12d` dùng volume mới và PostgreSQL 17.11. Compose config hợp lệ, image web build thành công, `db` và `web` healthy. |
| Migration, seed và khởi động web | Pass. Log ghi migration `catalog.0001`–`0004` đã áp dụng, seed 3 mẫu thiết bị và tài khoản demo, `GET /` trả 200. |
| `manage.py check`, `manage.py makemigrations --check --dry-run` | Pass. Không có lỗi Django hoặc thay đổi schema chưa có migration. |
| `manage.py test` | 22/22 pass, không skip. Hai kết nối đặt món cuối nhận `201` và `409` với đúng một đơn mới. Hai bàn giao đồng thời khi còn một món thực tế nhận `200` và `409`. Các bài khác kiểm tra hủy, `NO_SHOW`, trả sớm, trả muộn, quyền, tồn và dữ liệu demo. |
| `python scripts/smoke.py` | Pass qua HTTP trên Compose. Dữ liệu gồm khách mới, nhân viên demo và ống kính `LEN-001`. Đã kiểm tra đăng ký, đăng nhập, quyền, danh mục, tra lịch, đặt, bàn giao, trả sớm và hủy qua web/API. |
| Chrome headless, 1440 × 1000 và 390 × 844 | Pass. Đã xem ảnh danh mục, chi tiết, đặt thuê, kho và danh sách đơn nhân viên ở cả hai kích thước. Không có tràn ngang hoặc exception JavaScript. Kỳ 22–24/11 với `LEN-001` hiển thị còn 2 thiết bị. Thay số lượng từ 1 lên 2 cập nhật tiền tạm tính từ 300.000 ₫ lên 600.000 ₫. |
| `node --check catalog/static/catalog/site.js`, `git diff --check` | Pass. |
| GitHub Actions | Not Run. `.github/workflows/base.yml` đã có ở local và dùng cùng các lệnh Compose/Django/smoke đã đạt. `origin/main` chưa chứa workflow nên chưa có kết quả từ runner GitHub. |

Chạy Docker trong sandbox bị từ chối quyền truy cập Engine. Chạy có quyền Docker Desktop xử lý được vấn đề này. Cổng 8010 đang được sử dụng. Các lượt 18010 và 18011 phát hiện hai test định dạng tiền thất bại. Bản chạy 18012 dùng bộ định dạng VND riêng và đã chạy lại toàn bộ 22 test. Ba project xác minh trước đó được dừng và các volume được giữ.

## Tiếp tục xác minh

Môi trường đã xác minh đang phục vụ ở [cổng 18012](http://127.0.0.1:18012/). Để lặp lại, dùng `Verify` với một cổng trống theo [hướng dẫn](setup.md). GitHub Actions cần một lần chạy đạt trên nhánh chứa workflow sau khi Hải duyệt push.

Chưa tạo commit, push hoặc tag. Thay đổi hiện nằm trong working tree, gồm `README.md` đã sửa và các file triển khai Base chưa được Git theo dõi.
