# Kiến trúc Camera Rental

Django Templates phục vụ web và Django REST Framework phục vụ API. PostgreSQL lưu dữ liệu và Docker Compose dựng môi trường local. Các module nghiệp vụ chạy trong một Django app `catalog`. Model, app label và migrations tiếp tục thuộc `catalog`. `config` chứa settings và định tuyến. Xem [hướng dẫn chạy](setup.md).

| Thành phần | Trách nhiệm |
| --- | --- |
| HTTP UI/API | Xác thực người dùng, đọc input, gọi nghiệp vụ dùng chung và trả kết quả. Web dùng Django auth, API dùng tài khoản Django qua HTTP Basic trên localhost hoặc phiên Django có CSRF. |
| Điểm vào nghiệp vụ | `catalog/services.py` công bố các hàm chung cho web và API. Các module nghiệp vụ sở hữu phần thực thi. |
| PostgreSQL | Lưu thiết bị, người dùng và đơn. Sử dụng giao dịch khi tạo đơn, đổi trạng thái hoặc chỉnh tồn. Migrations quản lý thay đổi schema. |
| Dữ liệu demo và xác minh | Seed lặp được với tài khoản, danh mục và đơn mẫu. `catalog/tests.py` và `catalog/test_*.py` kiểm chứng nghiệp vụ, migration và tranh chấp tồn trên PostgreSQL. `scripts/smoke.py` kiểm tra web và API qua HTTP. |

Đăng ký tại `catalog/views.py` dùng `UserCreationForm` của Django auth. Web hiển thị điểm nhận, giờ và hỗ trợ trước khi đặt và trên đơn còn hiệu lực. [Cấu hình cửa hàng](setup.md#thông-tin-nhậntrả-cho-khách) · [Quyền sở hữu module](#kiến-trúc-mục-tiêu)

## Mô hình dữ liệu

Phần này mô tả dữ liệu Base. [V2-M1](#v2-m1--đặt-nhiều-thiết-bị) bổ sung dòng đơn và lịch giữ theo tài sản.

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

## V2-M1 · Đặt nhiều thiết bị

`Equipment` giữ mã mẫu và giá niêm yết. `AssetUnit` giữ mã kho duy nhất và serial hãng tùy chọn. `RentalLine` lưu số lượng và giá VND tại lúc đặt cho một mẫu trong đơn. `AssetReservation` giữ một thiết bị cho một dòng theo khoảng `[ngày nhận, ngày trả)`. Ràng buộc loại trừ PostgreSQL với `btree_gist` chặn hai lượt giữ có lịch chồng lấn cho cùng mã kho. Web và DRF gọi chung `catalog.services`.

Đặt thuê khóa các mẫu theo ID tăng dần, kiểm khả dụng suốt kỳ và ghi đơn, dòng và lượt giữ trong cùng một giao dịch. Hủy đơn và xử lý không đến nhận giải phóng lượt giữ. Khi đổi máy, lượt mới liên kết với lượt đã giải phóng và ghi người đổi. Bàn giao nguyên đơn kiểm thêm tài sản đang ở ngoài kho. Trả sớm giữ lịch đến mốc trả cam kết như ở Base.

| Thao tác | Hợp đồng |
| --- | --- |
| `POST /api/v2/rentals/` | Nhận `pickup_date`, `return_date` và `lines` gồm cặp `equipment_id`, `quantity`. Các mẫu phải đã bật giữ theo mã kho. Mỗi mẫu xuất hiện một lần. Trả `201` cùng các dòng đã chốt giá, hoặc `409` khi thiếu tồn. |
| `GET /api/v2/rentals/` và `GET /api/v2/rentals/{id}/` | Trả đơn của khách, gồm lịch sử đơn một dòng đã nâng dữ liệu. Mã tài sản nội bộ chỉ xuất hiện trên màn nhân viên. |
| `POST /api/v2/rentals/{id}/cancel/` | Hủy đơn của khách trước ngày nhận và giải phóng lịch cả đơn. |
| `/api/rentals/` và các route v1 | Giữ định dạng đơn một dòng. POST v1 có `lines` trả `400`. Các route xem và thao tác v1 trả `404` cho đơn nhiều dòng. POST một dòng dùng cùng nghiệp vụ và giữ tài sản cụ thể nếu mẫu đã chuyển đổi. |

Các đơn v1 đang mở vẫn xử lý qua hợp đồng cũ. Giữ theo mã kho chỉ bật theo từng mẫu sau khi đối soát. [Quy trình nâng dữ liệu](setup.md#chuyển-mẫu-v1-sang-giữ-theo-mã-kho)

## V2-M2 · Vận hành thuê

Khách mở đơn của mình để báo giá và gửi yêu cầu đổi kỳ. Nhân viên có quyền vận hành duyệt trên hàng đợi, kiểm lịch trong giao dịch và tính lại từ giá ngày đã chốt. Lượt giữ trước khi đổi kỳ và quyết định của nhân viên vẫn truy được. Gia hạn giữ nguyên mã kho đang giao và dừng khi đã nhận lại hoặc đóng ngoại lệ một món.

Giao nhận theo mã kho lưu bản chụp phụ kiện, người thao tác và các mốc chuẩn bị, giao, nhận, kiểm và xác nhận mất. Nhân viên xác nhận đủ đơn trong một lần bàn giao, sau đó nhận trả từng món. Món chờ kiểm hoặc cách ly bị chặn. Trả sớm giữ lịch đến ngày trả đã cam kết. Từ ngày hẹn trả, máy chưa sẵn sàng xuất hiện trong nhóm đơn có nguy cơ thiếu. Từ ngày sau, món chưa trả được tính quá hạn.

Bảo trì đã lên lịch dùng chung `AssetReservation` và ràng buộc chống chồng lấn với đơn thuê. Sự cố đột xuất cách ly máy và giữ lịch sử các lượt đã gán. Nhân viên đổi máy cùng mẫu nếu còn lịch, còn quản lý quyết định đưa máy về kho hoặc ngừng sử dụng. Món được xác nhận mất có dấu thời gian riêng. Khi toàn bộ món đã được xử lý và có món mất, đơn chuyển `CLOSED` với `closed_at`.

| Interface | Hợp đồng V2-M2 |
| --- | --- |
| Khách Web | `/rentals/{id}/change/` để báo giá và gửi yêu cầu. Chi tiết đơn hiển thị kết quả duyệt và số món đã về. |
| Khách API | `POST /api/v2/rentals/{id}/changes/quote/` báo giá. `GET/POST /api/v2/rentals/{id}/changes/` đọc lịch sử hoặc gửi yêu cầu với `kind`, kỳ mới và `accepted_total_vnd` khi tiền đổi. `GET /api/v2/rentals/{id}/` thêm `closed_at` và tóm tắt nhận trả. |
| Nhân viên Web | `/staff/operations/` hiển thị hàng đợi và yêu cầu đổi kỳ. Chi tiết vận hành liên kết với đơn, lịch kho và hồ sơ tại `/staff/maintenance/`. |
| Nhân viên API | `/api/v2/operations/` cung cấp hàng đợi. Các route con xử lý chuẩn bị, giao, nhận, kiểm, duyệt đổi kỳ và bảo trì. Các thao tác chuẩn bị, nhận và kiểm trả `204` khi thành công. [Route cụ thể](../config/urls.py) |
| Tương thích v1 | Giữ luồng tồn tổng, đơn đang ở ngoài kho từ M1 và định dạng đơn một dòng của v1. Bàn giao theo mã kho yêu cầu quyền vận hành và chuẩn bị đủ. Ghi nhận trả nguyên đơn v1 trả `409` kèm đường dẫn v2 nếu đơn đang dùng giao nhận theo món. Xem chi tiết `CLOSED` qua v2. |

Migration `0006_rental_operations` nối trực tiếp từ `0005`. Đơn đang được thuê từ V2-M1 tiếp tục nhận trả nguyên đơn và vẫn được tính đang ở ngoài kho. Migration bảo toàn lượt giữ, dữ liệu giá và timestamp đã ghi. Bản ghi giao nhận mới bắt đầu khi nhân viên xác nhận chuẩn bị. [Thiết lập vai trò và nâng dữ liệu](setup.md#v2-m2--vai-trò-vận-hành)

## V2-M3 · Quyết toán tại quầy

`finance.py` sở hữu nghĩa vụ phải thu, cọc, ghi nhận tiền thực tế, phí, hoàn và điều chỉnh. `RentalLine` lưu mức cọc mỗi thiết bị khi đặt. Sổ phát sinh từ `FinanceCharge` đã duyệt và các `FinanceEntry` còn hiệu lực. Bản ghi đảo giao dịch tham chiếu bản gốc. Nhật ký giữ người thao tác, thời điểm, hình thức và lý do hoặc chứng từ.

Đổi kỳ cập nhật tiền thuê đã chốt trong cùng giao dịch thay đổi lịch. Khi hủy trước giao, tiền thuê phải thu về 0 và các khoản đã nhận trở thành số phải hoàn. Khấu trừ chuyển một phần cọc đang giữ để thanh toán khoản thu đã duyệt. Hoàn và khấu trừ kiểm trạng thái giao nhận, kiểm tra, quyết định phí và sự cố còn mở. Đơn cũ đánh dấu chờ đối soát cho đến khi quản lý xác nhận chứng từ.

Thao tác tài chính khóa `Rental` trước khi đọc và ghi số dư. Thao tác bàn giao khóa `Equipment` theo ID rồi `Rental`, sau đó kiểm đã thu đủ tiền thuê và cọc cho đơn mới. Cấu hình cọc khóa riêng `Equipment`. Mã lệnh UUID chống ghi trùng theo đơn và loại tài nguyên. Gửi lại cùng mã với dữ liệu khác trả `409`.

| Điểm vào | Hợp đồng |
| --- | --- |
| Khách | Trang chi tiết đơn và `GET /api/v2/rentals/{id}/finance/` hiển thị số tổng hợp cho chủ đơn. API biểu diễn số VND tổng hợp bằng chuỗi số nguyên. |
| Nhân viên | `/staff/rentals/{id}/finance/` và `GET /api/v2/operations/rentals/{id}/finance/` mở sổ đơn. POST vào `finance/entries/` ghi thu hoặc hoàn, POST `finance/charges/` đề xuất khoản thu từ giao nhận thực tế. |
| Quản lý | POST `finance/charges/{id}/review/` duyệt hoặc từ chối. `finance/entries/` nhận thêm thao tác miễn, khấu trừ, đảo và đối soát, theo quyền. Mức cọc mỗi thiết bị chỉnh từ màn kho hoặc `POST /api/v2/operations/equipment/{id}/deposit/`. |

Yêu cầu ghi sổ dùng `kind`, `command_id` và `amount_vnd` nếu thao tác có nhập số tiền. Thu và hoàn cần `method` là `CASH` hoặc `TRANSFER`. Miễn và khấu trừ cần `charge_id` cùng lý do. Đảo lấy số tiền từ giao dịch gốc theo `entry_id`. Đối soát ghi nhận chứng từ với số tiền 0. Đề xuất khoản thu dùng `reason`, `handover_id` nếu có giao nhận từng mã, `amount_vnd`, `notes` và `command_id`. Duyệt dùng `approve` và `notes`.

Migration `0007` giữ số tiền và lịch sử đơn cũ, và khởi đầu với sổ giao dịch trống. Không tự tạo chứng từ thu tiền. [Quyền và cách chạy demo](setup.md#v2-m3--quyền-quyết-toán) · [Chính sách V2-M3](v2-product-design.md#quyết-định-trước-v2-m3)

## Kiến trúc mục tiêu

Camera Rental là modular monolith cho một cửa hàng. `catalog` giữ app label và ORM, `config` giữ settings và URL. Django Templates và JavaScript, DRF, PostgreSQL, Docker Compose và GitHub Actions phục vụ cùng ứng dụng.

| Module | Trách nhiệm hiện tại |
| --- | --- |
| `equipment.py` | SKU, danh mục, giá niêm yết, phụ kiện và đăng ký tài sản. |
| `inventory.py` | Kỳ thuê, khả dụng theo lịch, lượt giữ, tồn thực tế và truy vấn đối soát. Đặt, đổi, thay máy và bảo trì dùng chung phép kiểm khả dụng. |
| `rentals.py` | Đặt thuê, chốt giá, hủy, `NO_SHOW`, thay máy cùng mẫu và điều phối vòng đời đơn. |
| `schedule_changes.py` | Yêu cầu đổi kỳ, gia hạn, chấp thuận giá và duyệt nguyên tử. |
| `custody.py` | Khóa theo đơn, chuẩn bị, thời điểm giao nhận và kết quả kiểm từng mã kho. |
| `maintenance.py` | Giữ lịch bảo trì, cách ly, sửa, xử lý sự cố và mở lại tồn sau kiểm tra. |
| `operations.py` | Hàng đợi vận hành và giao dịch nối kết quả kiểm của Custody với Maintenance. |
| `roles.py` | Quyền vận hành và xử lý ngoại lệ bằng các nhóm Django. |
| `finance.py` | Quyết toán VND, cọc, thu/hoàn và các quyết định phí có truy vết. |
| `services.py` | Điểm vào chung cho Web và DRF, công bố hàm từ module sở hữu. |

`operations` gọi `custody` và `maintenance`. `maintenance` gọi `custody` để đóng lượt giao nhận có mất. `custody` và các module cần kiểm lịch gọi `inventory`. Các giao dịch ảnh hưởng tồn khóa `Equipment` theo ID tăng dần trước `Rental`, rồi kiểm lại điều kiện dưới khóa.

### Bố cục hiện tại

```text
catalog/
  models.py, services.py, errors.py
  equipment.py, inventory.py, rentals.py, schedule_changes.py
  custody.py, maintenance.py, operations.py, roles.py, finance.py
  views.py, forms.py, api.py, operations_web.py, operations_api.py
  finance_web.py, finance_api.py
  migrations/                 0001–0007
  templates/catalog/         màn Base/M1 và template dùng chung
    customer/                 yêu cầu đổi hoặc gia hạn
    staff/                    giao nhận, bảo trì và quyết toán
  static/catalog/             CSS, JavaScript, ảnh, phông chữ
  tests.py, test_asset_rentals.py, test_schedule_changes.py
  test_operations.py, test_maintenance.py, test_finance.py
config/                        settings và URL
docs/                          đặc tả, thiết kế, thiết lập và bằng chứng
```

Adapter vận hành và quyết toán tách theo luồng người dùng. Màn Base/M1 tiếp tục dùng đường dẫn template hiện tại. Các truy vấn báo cáo sẽ có module riêng khi V2-M4 bổ sung số liệu quản lý. [Roadmap](../ROADMAP.md#roadmap-v20)

### Kiểm chứng thay đổi

- Giữ URL, hợp đồng phản hồi và migration đã áp dụng. Mỗi ứng viên cần kiểm system check, migration drift, cài mới và nâng dữ liệu trên PostgreSQL biệt lập.
- Dùng kết nối PostgreSQL độc lập để kiểm đặt đồng thời, bàn giao, đổi kỳ và bảo trì. Mở các màn thay đổi trên desktop và mobile, và chạy smoke Web/API. [Quy trình Verify](setup.md#kiểm-tra-và-dựng-dữ-liệu-sạch)
