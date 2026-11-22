# Camera Rental Management Platform

Camera Rental phát triển phần mềm vận hành cho thuê máy ảnh, ống kính và thiết bị quay chụp. Mục tiêu v2.0 là nối đặt thuê nhiều thiết bị với giữ lịch, giao nhận theo từng tài sản, bảo trì và quyết toán cọc. [Thiết kế sản phẩm v2.0](docs/v2-product-design.md)

V2-M1 local/demo bổ sung đặt nhiều mẫu trong cùng kỳ, giữ theo mã kho và lịch giữ cho nhân viên trên nền Base v1.0. Khách vẫn có thể tra lịch và đặt một mẫu từ danh mục. Nhân viên vẫn bàn giao và nhận trả nguyên đơn. [Thiết lập local và tài khoản demo](docs/setup.md)

| Bạn cần | Đọc |
| --- | --- |
| Biết mốc đang làm | [Kế hoạch phát triển](PROJECT_PLAN.md) |
| Xem mốc v2.0 và điều kiện phát hành | [Roadmap sản phẩm](ROADMAP.md) |
| Hiểu nghiệp vụ hiện có và tiêu chí nghiệm thu | [Đặc tả Base v1.0](docs/requirements.md) |
| Tiếp quản thiết kế và hợp đồng API hiện tại | [Kiến trúc Base v1.0](docs/architecture.md) |
| Mở dự án và chuẩn bị môi trường local | [Thiết lập local](docs/setup.md) |
| Làm ticket, review và merge | [Quy trình đóng góp](CONTRIBUTING.md) |
| Giao việc cho Codex hoặc agent khác | [Hướng dẫn cho agent](AGENTS.md) |

Trong PowerShell tại thư mục repo, chạy `.\scripts\dev.ps1 -Action Start`, rồi mở [danh mục thiết bị](http://localhost:8000/). Kết quả kiểm chứng bản nền được lưu theo commit. [Bằng chứng Base v1.0](docs/verification.md)
