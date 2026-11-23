# Kiến trúc Camera Rental

Django Templates phục vụ web và Django REST Framework phục vụ API. PostgreSQL lưu dữ liệu và Docker Compose dựng môi trường local. Các module nghiệp vụ chạy trong một Django app `catalog`. Model, app label và migrations tiếp tục thuộc `catalog`. `config` chứa settings và định tuyến. Xem [hướng dẫn chạy](setup.md).

| Thành phần | Trách nhiệm |
| --- | --- |
| HTTP UI/API | Xác thực người dùng, đọc input, gọi nghiệp vụ dùng chung và trả kết quả. Web dùng Django auth, API dùng tài khoản Django qua HTTP Basic trên localhost hoặc phiên Django có CSRF. |
| Điểm vào nghiệp vụ | `catalog/services.py` công bố các hàm chung cho web và API. Các module nghiệp vụ sở hữu phần thực thi. |
| PostgreSQL | Lưu thiết bị, người dùng và đơn. Sử dụng giao dịch khi tạo đơn, đổi trạng thái hoặc chỉnh tồn. Migrations quản lý thay đổi schema. |
| Dữ liệu demo và xác minh | Seed lặp được với tài khoản, danh mục và đơn mẫu. `catalog/tests.py` và `catalog/test_asset_rentals.py` kiểm chứng nghiệp vụ, migration và tranh chấp tồn trên PostgreSQL. `scripts/smoke.py` kiểm tra web và API qua HTTP. |

## Module nghiệp vụ

| Phần | Nơi sửa | Trách nhiệm |
| --- | --- | --- |
| Tài khoản · R08 | `catalog/views.py`, `config/urls.py` | View đăng ký dùng `UserCreationForm`. Django auth xử lý đăng nhập, đăng xuất và cung cấp thuộc tính `is_staff`. |
| Danh mục và đăng ký tài sản | `catalog/equipment.py` | Quản lý SKU, giá niêm yết, thông số, mã kho và bật giữ theo tài sản sau đối soát. Khi chỉnh tồn v1, hỏi `inventory` về mức tồn tối thiểu sau khi khóa thiết bị. |
| Tồn kho và kỳ thuê | `catalog/inventory.py` | Kiểm tra kỳ, tính tồn tổng cho SKU v1 và tìm tài sản rảnh cho SKU đã chuyển đổi. Cung cấp lịch giữ, tồn thực tế và danh sách đơn chưa đối soát cho màn kho. |
| Đơn thuê và giao nhận | `catalog/rentals.py` | Tạo đơn và dòng, chốt giá, giữ và giải phóng lịch, đổi tài sản cùng SKU, bàn giao và nhận trả nguyên đơn. Màn chi tiết dùng chung quy tắc trạng thái và ngày với các thao tác ghi. |

Thông tin công khai về điểm nhận, giờ và hỗ trợ lấy từ [cấu hình cửa hàng](setup.md#thông-tin-nhậntrả-cho-khách). Web hiển thị thông tin này trước khi đặt và trên đơn còn hiệu lực.

```text
Web, API và form → services
services → equipment, inventory, rentals
equipment, rentals → inventory
equipment, inventory, rentals → models, errors
Đăng ký web → Django auth
```

`equipment`, `rentals` và `inventory` dùng chung models và `RentalError` từ `catalog/errors.py`. `inventory` đọc dữ liệu qua ORM. Các module thiết bị và đơn thuê sở hữu giao dịch ghi của mình.

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

## Kiến trúc mục tiêu

Một Django project và một PostgreSQL database phục vụ một cửa hàng. Giữ app label `catalog`, các migrations đã áp dụng và dữ liệu lịch sử. Giữ Django Templates và JavaScript cho giao diện, DRF cho API, Docker Compose cho môi trường chạy và GitHub Actions cho kiểm chứng.

| Lớp | Trách nhiệm |
| --- | --- |
| Giao diện | Customer Portal phục vụ chọn thiết bị, đặt và theo dõi đơn. Staff Workspace ưu tiên hàng đợi công việc, lịch kho và thao tác tại quầy. Manager Dashboard ưu tiên ngoại lệ cần duyệt, số dư, kiểm kê và báo cáo theo kỳ. Cả ba dùng chung thành phần giao diện và có bố cục theo công việc của từng vai trò. |
| Adapter | Django Views, Forms, DRF và Django auth nhận đầu vào, xác thực, kiểm quyền, gọi service và trả kết quả. Service vẫn kiểm quyền và bất biến khi ghi dữ liệu. |
| Nghiệp vụ | `catalog/services.py` giữ điểm vào tương thích cho web/API. Các domain sở hữu quy tắc, gọi nhau qua hàm nghiệp vụ rõ trách nhiệm và giữ một chiều phụ thuộc. |
| Dữ liệu và hạ tầng | Django ORM và PostgreSQL lưu trạng thái, giao dịch và lịch sử. Constraints bảo vệ các bất biến dữ liệu. Docker Compose và GitHub Actions dùng cùng luồng kiểm chứng. |

### Quyền sở hữu nghiệp vụ

| Domain | Trách nhiệm |
| --- | --- |
| Accounts & Roles | Tài khoản Django, vai trò khách/nhân viên/quản lý và quyền theo thao tác. |
| Equipment | SKU, danh mục, thông số, phụ kiện và giá niêm yết. |
| Inventory | Tài sản vật lý, trạng thái khả dụng, lịch giữ và tồn thực tế. Cung cấp cùng một kiểm tra khả dụng cho đặt đơn, đổi lịch, thay máy và bảo trì. |
| Rentals | Đơn, dòng đơn, vòng đời, đổi kỳ và giao nhận. Điều phối giao dịch và gọi Inventory khi cần giữ lịch hoặc giao thiết bị. |
| Maintenance | Ghi sự cố, kiểm tra, cách ly, sửa chữa và quyết định đưa máy về kho. Gọi Inventory khi thay đổi khả dụng. |
| Finance | Snapshot giá, cọc, thu/hoàn, phí, bút toán và quyết toán. Giữ quy tắc tiền theo chính sách đã duyệt. |
| Reporting | Đọc dữ liệu nghiệp vụ và tổng hợp chỉ số cho quản lý. |
| Audit & History | Ghi người thao tác, thời điểm và lý do vào cùng giao dịch của domain sở hữu thay đổi. Reporting đọc lịch sử để truy vết. |

### Điểm tách đã xác định từ code

| Hiện trạng | Thay đổi có lý do |
| --- | --- |
| Tồn vật lý theo mã kho suy ra từ trạng thái `PICKED_UP` của cả đơn. [Inventory](../catalog/inventory.py#L149-L166) · [Giao nhận hiện tại](../catalog/rentals.py#L200-L261) | **M2** cần nguồn ghi theo từng tài sản để phân biệt đã về, chưa về và chờ kiểm. Giữ lịch cam kết và thời điểm thực tế riêng để nhận trả từng phần không làm sai tồn. |
| Inventory truy khả dụng, còn Rentals ghi lượt giữ, giải phóng, thay máy và kiểm khả năng giao. [Kiểm lịch](../catalog/inventory.py#L149-L166) · [Tạo lượt giữ](../catalog/rentals.py#L117-L136) · [Giải phóng và thay máy](../catalog/rentals.py#L264-L303) | **M2** đưa thao tác lịch dùng chung vào Inventory khi đổi kỳ và bảo trì cần cùng quy tắc. Rentals giữ giao dịch của đơn. Chỉ tách file giao nhận khi phần xử lý theo mã kho có trách nhiệm và kiểm thử riêng. |
| Web và DRF dựa vào `is_staff` cho các thao tác nhân viên. `views.py` chứa cả hai luồng khách và nhân viên, `api.py` chứa serializer và các route v1/v2. [Web](../catalog/views.py#L273-L305) · [DRF](../catalog/api.py#L154-L240) | **M2** kiểm quyền theo thao tác sau khi duyệt vai trò. Chỉ tách adapter theo luồng khi có thay đổi thực tế, như màn duyệt quyết toán M3 hoặc màn quản lý M4. |

### Bố cục tham chiếu

V2-M2 bắt đầu trên cấu trúc hiện có. Các đường dẫn dưới đây là nơi phù hợp khi có nghiệp vụ thực tế và điểm tách rõ. Giữ các module đang phục vụ tính năng cho đến khi một thay đổi cần di chuyển chúng.

```text
catalog/
  models.py, services.py, errors.py
  domains/
    equipment/           danh mục và giá niêm yết
    inventory/           khả dụng và giữ lịch theo tài sản
    rentals/             đặt thuê, vòng đời và giao nhận
    maintenance/         khi có quy trình bảo trì trong M2
    finance/             khi có giá và sổ tiền trong M3
    reporting/           khi có truy vấn báo cáo trong M4
  web/                   khi các luồng khách, nhân viên và quản lý cần tách
  api/                   khi cần tách route, serializer hoặc quyền
  migrations/
  templates/catalog/     customer, staff, manager, components khi có nội dung
  static/catalog/        CSS, JavaScript, ảnh và font theo nhu cầu giao diện
  tests/                 khi cách tổ chức suite hiện tại gây khó tìm hoặc chạy test
```

Models và migrations tiếp tục thuộc app `catalog`. Tài khoản dùng Django auth. Lịch sử nghiệp vụ nằm tại giao dịch tạo thay đổi. ORM phục vụ truy vấn dữ liệu trực tiếp qua các module sở hữu nghiệp vụ.

### Schema và tương thích theo mốc

| Mốc | Ảnh hưởng dự kiến |
| --- | --- |
| V2-M2 | Bổ sung yêu cầu đổi kỳ có kết quả phê duyệt, bản ghi giao nhận và kiểm tra theo mã kho, hiện trạng kỹ thuật, sự cố và lịch sử bảo trì. Đảm bảo mỗi tài sản có tối đa một lượt bàn giao đang mở. Dùng cùng kiểm tra lịch theo tài sản cho đặt, đổi và bảo trì đã lên lịch. Cách ly đột xuất cần chặn giao máy và báo các đơn bị ảnh hưởng dù đã có giữ chỗ. Nếu có trạng thái đóng do mất, migration phải bảo toàn timestamp thật và lịch sử đơn v1. Dùng Django Groups và quyền nghiệp vụ để chuyển vai trò nhân viên theo danh sách đã xác minh. |
| V2-M3 | Đặt sổ giao dịch VND, quy tắc giá và quyết toán đã duyệt trong Finance. Dùng khóa thao tác để tránh ghi trùng. Lưu điều chỉnh bằng bút toán có lý do và liên kết bản ghi gốc. |
| V2-M4 | Đặt truy vấn từ đơn, giao nhận, bảo trì và sổ tiền trong Reporting. Thêm phiên kiểm kê và lịch sử chênh lệch nếu cần để truy người xử lý. Chỉ thêm index khi truy vấn thực tế cho thấy cần. |
| V2-M5 | Kiểm chứng cài mới, nâng dữ liệu từ v1 và M1, phục hồi và tương thích API trên PostgreSQL biệt lập. Hoàn thiện việc tách adapter, giao diện hoặc test nếu có vấn đề bảo trì đã xác định và bước thay đổi có thể hoàn tác. Chủ sản phẩm duyệt cách chuyển tiếp trước khi đổi hợp đồng ở pilot. |

Tiếp tục khóa `Equipment` theo ID tăng dần trước `Rental` trong giao dịch ảnh hưởng tồn. Khi mở rộng từ giữ chỗ sang bảo trì, kiểm chứng va chạm giữa hai loại lịch trên PostgreSQL và giữ ràng buộc loại trừ chồng lấn đã có. Sau khi khóa, kiểm lại trạng thái, kỳ và khả năng giao. Sự kiện nhận vật lý, kết quả kiểm và quyết toán là các dấu mốc riêng. [Quyết định trước V2-M2](v2-product-design.md#quyết-định-trước-v2-m2)

Trong V2-M2, kiểm từng route ghi v1 với chính sách mới. Với đơn một dòng vẫn biểu diễn đúng, gọi cùng nghiệp vụ và giữ hợp đồng Base. Nếu thao tác cần dữ liệu theo mã kho mà v1 không gửi được, thiết kế lỗi rõ và đường dẫn chuyển sang v2 trước khi thay đổi hợp đồng. Đơn cũ chưa đối soát tiếp tục được báo tại màn kho. Migration tương lai giữ ID, snapshot, trạng thái và dấu thời gian đã ghi.

Trước chuyển đổi trên dữ liệu thật, dừng ghi, chờ giao dịch đang chạy kết thúc, chụp điểm khôi phục rồi đối chiếu đơn, giá và lịch. Diễn tập phục hồi trên bản sao. Phương án khôi phục phải tính cả các giao dịch phát sinh sau khi mở ghi. [Quy trình V2-M1 hiện tại](setup.md#chuyển-mẫu-v1-sang-giữ-theo-mã-kho)

### Kiểm chứng mỗi bước tách

- Giữ các route, tên URL, mã lỗi, kiểu phản hồi, tên template và API Python đang có người gọi. Khi chuyển `api.py` hoặc `tests.py` thành package cùng tên, chuyển điểm import và test discovery trong cùng thay đổi để Python không nạp nhầm module. Khi tách static, kiểm cả đường dẫn tương đối từ CSS đến font. [URL hiện tại](../config/urls.py) · [Template gốc](../catalog/templates/catalog/base.html) · [CSS](../catalog/static/catalog/site.css)
- Giữ nguyên migration `0001`–`0005`. Một lần di chuyển nội bộ thuần cấu trúc cần đạt `manage.py check` và `makemigrations --check --dry-run`. Với schema mới, kiểm nâng dữ liệu v1/M1 gồm ID, giá, trạng thái và timestamp. Migration `0005` chặn hạ cấp khi đã tạo tài sản, bật giữ theo tài sản hoặc tạo đơn nhiều dòng. [Migration `0005`](../catalog/migrations/0005_asset_units_and_rental_lines.py#L39-L51)
- Chạy test hành vi cho quyền, vòng đời, giá và tồn. Kiểm tranh chấp bằng kết nối PostgreSQL độc lập. Với thay đổi web/API, chạy smoke hai phiên bản và mở lại các màn bị ảnh hưởng để kiểm template và static. [Verify biệt lập](setup.md#kiểm-tra-và-dựng-dữ-liệu-sạch) · [Workflow hiện tại](../.github/workflows/base.yml)
