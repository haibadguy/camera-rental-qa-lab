# Làm việc với Camera Rental

Đọc [kế hoạch](PROJECT_PLAN.md), [yêu cầu](docs/requirements.md), [kiến trúc](docs/architecture.md) và [quy trình đóng góp](CONTRIBUTING.md) trước khi sửa. Xác định mã yêu cầu, phạm vi và tiêu chí nghiệm thu. Quy tắc nghiệp vụ mới hoặc đổi stack cần Hải duyệt.

- Giữ Django Templates, DRF, PostgreSQL và Docker Compose. Dùng `catalog/services.py` cho nghiệp vụ chung giữa web và API.
- Khóa `Equipment` trước khi khóa `Rental` khi thao tác có ảnh hưởng tồn. Phân biệt tồn theo lịch và số thiết bị đang ở ngoài kho.
- Kiểm tra từ môi trường Compose sạch theo [hướng dẫn](docs/setup.md). Ghi lệnh, dữ liệu, kết quả và phần `Blocked` hoặc `Not Run` theo bằng chứng.
- Bảo toàn thay đổi local, lịch sử đơn và volume. Push, release và tag cần Hải duyệt riêng. Git commit local làm theo phạm vi người dùng cho phép.
- Giai đoạn Base dùng automated tests và kiểm tra kỹ thuật. Manual QA Portfolio bắt đầu sau khi Hải duyệt bản nền. Liên kết requirement, test case, defect và retest khi giai đoạn đó bắt đầu.
