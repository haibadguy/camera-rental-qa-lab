# Kiến trúc MVP

Django Templates phục vụ web và Django REST Framework phục vụ API. PostgreSQL lưu dữ liệu và Docker Compose dựng môi trường local. Các module nghiệp vụ chạy trong một Django app `catalog`. Model, app label và migrations tiếp tục thuộc `catalog`. `config` chứa settings và định tuyến. Xem [hướng dẫn chạy](setup.md).

| Thành phần | Trách nhiệm |
| --- | --- |
| HTTP UI/API | Xác thực người dùng, đọc input, gọi nghiệp vụ dùng chung và trả kết quả. Web dùng Django auth, API dùng tài khoản Django qua HTTP Basic trên localhost hoặc phiên Django có CSRF. |
| Điểm vào nghiệp vụ | `catalog/services.py` cung cấp các hàm chung cho web, API và các lệnh dùng nghiệp vụ. |
| PostgreSQL | Lưu thiết bị, người dùng và đơn. Sử dụng giao dịch khi tạo đơn, đổi trạng thái hoặc chỉnh tồn. Migrations quản lý thay đổi schema. |
| Dữ liệu demo và xác minh | Seed lặp được với tài khoản, danh mục và đơn mẫu. `catalog/tests.py` chạy các test Django và PostgreSQL. `scripts/smoke.py` kiểm tra web và API qua HTTP. |

## Module nghiệp vụ

| Phần | Nơi sửa | Trách nhiệm |
| --- | --- | --- |
| Tài khoản · R08 | `catalog/views.py`, `config/urls.py` | View đăng ký dùng `UserCreationForm`. Django auth xử lý đăng nhập, đăng xuất và cung cấp thuộc tính `is_staff`. |
| Danh mục · R01 | `catalog/equipment.py` | Tìm kiếm, lọc, thêm và sửa thiết bị. Giá niêm yết và trạng thái nhận đơn thuộc thiết bị. Khi chỉnh tổng tồn, module hỏi `inventory` về mức tồn tối thiểu sau khi khóa thiết bị. |
| Tồn kho và kỳ thuê · R02/R05/R07 | `catalog/inventory.py` | Kiểm tra ngày, tính đỉnh giữ lịch, tính lượng đang ở ngoài kho và cung cấp dữ liệu cho màn kho. Form và JS nhận mức tối đa của kỳ thuê từ cùng quy tắc Python. |
| Đơn thuê · R03/R04/R06/R07 | `catalog/rentals.py` | Đặt đơn, chốt giá, truy vấn đơn của khách, nhóm đơn cho nhân viên và chuyển trạng thái. Màn chi tiết dùng chung quy tắc trạng thái và ngày với các thao tác ghi. Khi bàn giao, giao dịch kiểm tra thêm tồn vật lý. |

Thông tin công khai về điểm nhận, giờ và hỗ trợ lấy từ [cấu hình cửa hàng](setup.md#thông-tin-nhậntrả-cho-khách). Web hiển thị thông tin này trước khi đặt và trên đơn còn hiệu lực.

```text
Web, API, form và seed → services
services → equipment, inventory, rentals
equipment, rentals → inventory
equipment, inventory, rentals → models, errors
Đăng ký web → Django auth
```

`equipment`, `rentals` và `inventory` dùng chung models và `RentalError` từ `catalog/errors.py`. `inventory` đọc dữ liệu qua ORM. Các module thiết bị và đơn thuê sở hữu giao dịch ghi của mình.

## Mô hình dữ liệu

- `Equipment` biểu diễn một mẫu thiết bị: mã duy nhất, tên, loại, thông số, giá thuê ngày, tổng tồn và trạng thái nhận đơn. Ngừng nhận đơn chỉ ảnh hưởng truy cập công khai và đặt mới. Lịch sử và xử lý đơn cũ vẫn dựa trên khóa ngoại đã lưu.
- `Rental` liên kết với một `Equipment` và khách thuê. Lưu ngày nhận/trả theo lịch, số lượng, giá lúc đặt, trạng thái, thời điểm bàn giao/trả thực tế và lý do `NO_SHOW` nếu có. Khách tự đăng ký trên web. Nhân viên dùng tài khoản Django có `is_staff`.
- Mỗi giao dịch ảnh hưởng tồn khóa bản ghi mẫu thiết bị trước khi đọc lại các đơn và ghi thay đổi. Nếu thao tác cần khóa cả đơn, giữ thứ tự mẫu thiết bị trước, đơn sau. Đây là điểm cần kiểm chứng bằng test hai request trên hai kết nối PostgreSQL độc lập.
- Lịch giữ tồn tính theo khoảng từ ngày nhận đến trước ngày trả, kể cả đơn trả sớm. Bàn giao kiểm tra tồn thực tế bằng cách trừ các đơn `PICKED_UP` khỏi tổng tồn, kể cả khi đã quá ngày trả. Giảm tổng tồn phải tôn trọng cả lịch giữ và số thiết bị đang ở ngoài kho.

## Hợp đồng API

| Thao tác | Đường dẫn | Kết quả thành công |
| --- | --- | --- |
| Xem danh mục/tra cứu lịch | `GET /api/equipment/` | `200` và danh sách mẫu, kèm tồn theo kỳ khi có ngày nhận và ngày trả |
| Xem chi tiết thiết bị | `GET /api/equipment/{id}/` | `200` cùng loại, thông số và giá thiết bị đang nhận đơn |
| Tạo, xem đơn của mình | `POST /api/rentals/`, `GET /api/rentals/`, `GET /api/rentals/{id}/` | `201` khi tạo, `200` khi đọc |
| Hủy đơn | `POST /api/rentals/{id}/cancel/` | `200` và trạng thái `CANCELLED` |
| Bàn giao | `POST /api/rentals/{id}/pick-up/` | `200` và trạng thái `PICKED_UP` |
| Hủy vì khách không đến nhận | `POST /api/rentals/{id}/no-show/` | `200`, trạng thái `CANCELLED` và lý do `NO_SHOW` |
| Ghi nhận trả | `POST /api/rentals/{id}/return/` | `200` và trạng thái `RETURNED` |

Danh mục nhận `search` theo tên/mã và `kind` là `CAMERA` hoặc `LENS`. Tra cứu tồn nhận cặp `pickup_date` và `return_date` dạng `YYYY-MM-DD` và trả thêm `available_stock`. Đặt thuê nhận JSON gồm `equipment_id`, `pickup_date`, `return_date` và `quantity`. Phản hồi đơn chứa `id`, số lượng, giá ngày lúc đặt, `total_vnd` dưới dạng chuỗi số nguyên, `status`, `picked_up_at`, `returned_at`, `cancellation_reason`, `is_overdue` và `was_returned_late`. Thời điểm chưa ghi nhận dùng `null`, lý do hủy mặc định dùng chuỗi rỗng.

API trả `400` cho dữ liệu sai, `401` khi thiếu hoặc sai thông tin xác thực, `403` khi khách gọi thao tác dành cho nhân viên, `404` khi đối tượng không tồn tại hoặc đơn thuộc khách khác, và `409` khi thiếu tồn hoặc sai trạng thái/thời điểm. Khách xem và hủy đơn của mình. Bàn giao, `NO_SHOW` và ghi nhận trả yêu cầu tài khoản nhân viên.
