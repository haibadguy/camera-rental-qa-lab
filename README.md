# Camera Rental QA Lab

Ứng dụng cho thuê máy ảnh và ống kính. Khách có thể tra lịch ngay trên trang thiết bị, xem tiền thuê tạm tính và quản lý đơn của mình. Nhân viên quản lý kho và xử lý các đơn đã đặt.

Base MVP gồm đăng ký và đăng nhập khách, danh mục, tra cứu theo ngày, đặt và hủy đơn, bàn giao, ghi nhận trả và quản lý tồn kho. Web và API dùng chung nghiệp vụ. Thông tin tài khoản demo và trạng thái chạy nằm trong [thiết lập local](docs/setup.md).

| Bạn cần | Đọc |
| --- | --- |
| Biết mốc đang làm | [Kế hoạch Base v1.0](PROJECT_PLAN.md) |
| Xem roadmap và điều kiện phát hành | [Roadmap và G0–G4](ROADMAP.md) |
| Hiểu nghiệp vụ và tiêu chí nghiệm thu | [Đặc tả MVP](docs/requirements.md) |
| Tiếp quản thiết kế và hợp đồng API | [Kiến trúc](docs/architecture.md) |
| Mở dự án và chuẩn bị môi trường local | [Thiết lập local](docs/setup.md) |
| Làm ticket, review và merge | [Quy trình đóng góp](CONTRIBUTING.md) |
| Giao việc cho Codex hoặc agent khác | [Hướng dẫn cho agent](AGENTS.md) |

Trong PowerShell tại thư mục repo, chạy `.\scripts\dev.ps1 -Action Start`, rồi mở [danh mục thiết bị](http://localhost:8000/). Xem [trạng thái xác minh](docs/verification.md) trước khi chốt bản nền.
