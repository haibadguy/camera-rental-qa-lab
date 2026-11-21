# Camera Rental Base v1.0

Mục tiêu hiện tại là bàn giao ứng dụng Camera Rental hoạt động độc lập theo [R01–R08](docs/requirements.md). QA Portfolio bắt đầu sau khi Hải duyệt bản nền và xác nhận phiên bản kiểm thử cố định.

| Mốc | Điều kiện qua mốc |
| --- | --- |
| M1 · Nghiệp vụ | Đăng ký, danh mục, đặt, hủy, bàn giao, trả và `NO_SHOW` hoạt động. Kiểm tra quyền, lịch giữ, tồn thực tế và đồng thời trên PostgreSQL. |
| M2 · Sản phẩm | Luồng khách và nhân viên rõ ràng trên màn hình nhỏ và lớn. Dựng môi trường một lệnh, có workflow CI và tài liệu bàn giao. |
| M3 · Xác minh | Dựng từ dữ liệu sạch, migration và seed thành công, test Django và HTTP smoke đạt, UI được xem ở hai kích thước và GitHub Actions chạy thành công. |

[Kết quả xác minh và phần còn vướng](docs/verification.md) là nguồn cập nhật tiến độ. Quyết định đóng băng Base và tag `v1.0.0-qa-baseline` thuộc Hải.
