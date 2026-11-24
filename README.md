# Camera Rental Management System

Camera Rental là ứng dụng quản lý cho thuê máy ảnh, ống kính và thiết bị quay chụp cho một cửa hàng chuyên nghiệp. Quy mô mục tiêu là **Medium Business Application**, bao phủ từ đặt thuê, giao nhận và bảo trì đến quyết toán tại quầy và báo cáo cho quản lý. [Phạm vi sản phẩm](docs/v2-product-design.md)

V2-M2 đã tích hợp vào `main`. Khách có thể đặt nhiều mẫu cùng kỳ, yêu cầu đổi lịch và gia hạn. Nhân viên chuẩn bị, giao nhận theo mã kho, kiểm tra và xử lý sự cố. Quản lý duyệt ngoại lệ và mở lại tồn sau bảo trì. [Thiết lập local và tài khoản demo](docs/setup.md) · [Trạng thái trong kế hoạch](PROJECT_PLAN.md#công-việc-hiện-tại-của-v2)

V2-M3 đã tích hợp vào `main`, bổ sung cọc bảo đảm, sổ giao dịch tại quầy và quyết toán theo đơn. [Thiết lập quyền quyết toán](docs/setup.md#v2-m3--quyền-quyết-toán)

V2-M4 và phần kỹ thuật của V2-M5 đã tích hợp vào `main`, bổ sung báo cáo quản lý, lọc thương hiệu, kiểm kê và kiểm chứng trên dữ liệu demo. Pilot và phát hành v2.0 chờ Hải duyệt riêng. [Trạng thái trong kế hoạch](PROJECT_PLAN.md#công-việc-hiện-tại-của-v2)

Nhánh V3 bổ sung vận hành một cửa hàng lớn với ca thu ngân, ảnh sự cố và phân trang cho danh mục lớn. Xem điều kiện triển khai staging và bằng chứng từng mốc trước khi pilot. [Kế hoạch V3](docs/v3-implementation-plan.md) · [Dựng staging](docs/setup.md#v3--staging-và-xác-minh)

| Bạn cần | Đọc |
| --- | --- |
| Biết mốc đang làm | [Kế hoạch phát triển](PROJECT_PLAN.md) |
| Xem mốc v2.0 và điều kiện phát hành | [Roadmap sản phẩm](ROADMAP.md) |
| Hiểu nghiệp vụ hiện có và tiêu chí nghiệm thu | [Đặc tả Base v1.0](docs/requirements.md) |
| Tiếp quản kiến trúc và hợp đồng API | [Kiến trúc Camera Rental](docs/architecture.md) |
| Mở dự án và chuẩn bị môi trường local | [Thiết lập local](docs/setup.md) |
| Làm ticket, review và merge | [Quy trình đóng góp](CONTRIBUTING.md) |
| Giao việc cho Codex hoặc agent khác | [Hướng dẫn cho agent](AGENTS.md) |

Trong PowerShell tại thư mục repo, chạy `.\scripts\dev.ps1 -Action Start`, rồi mở [danh mục thiết bị](http://localhost:8000/). Kết quả kiểm chứng được lưu theo commit. [Bằng chứng kiểm chứng](docs/verification.md)
