# Chạy Camera Rental trên máy

Cần Git và Docker Desktop chạy Linux containers. Từ PowerShell trong thư mục repo, chạy các lệnh dưới đây.

```powershell
docker version
docker compose version
.\scripts\dev.ps1 -Action Start
```

`docker version` cần có cả Client và Server. Script tạo `.env` nếu chưa có, sinh riêng khóa Django và mật khẩu PostgreSQL, rồi chạy Compose. Container web chạy migration, nạp demo và phục vụ ứng dụng. Compose chờ PostgreSQL và trang danh mục sẵn sàng. Mở [Camera Rental](http://localhost:8000/).

Trên shell khác, dùng các biến trong `.env.example` để tạo `.env` với khóa Django và mật khẩu PostgreSQL ngẫu nhiên, rồi chạy `docker compose up --build --wait`. Giữ `DJANGO_DEBUG=0` để xem trang lỗi của bản demo. Máy chủ Django trong Compose chỉ phục vụ demo ở loopback.

## Dữ liệu demo

| Tài khoản | Vai trò | Mật khẩu công khai cho demo |
| --- | --- | --- |
| `demo-a` | Khách có đơn đã bàn giao đến hạn trả | `camera-demo-2026` |
| `demo-b` | Khách | `camera-demo-2026` |
| `demo-staff` | Nhân viên | `camera-demo-2026` |

Danh mục gồm ba mẫu thiết bị. Ngày của đơn demo tính theo giờ Việt Nam ở lần seed đầu. Chạy lại seed vẫn giữ tài khoản, thiết bị và trạng thái đơn đã thay đổi. Đơn cũ chưa từng lưu thời điểm bàn giao sẽ giữ giá trị trống sau migration.

Danh mục demo mới có mã kho cho cả ba mẫu. Mở **Đặt nhiều thiết bị** để chọn Sony A6400 và Sigma 30mm Sony E trong cùng kỳ. Nhân viên xem lịch theo mã kho tại **Kho thiết bị → Mã kho và lịch giữ**, hoặc đổi máy cùng mẫu trên chi tiết đơn đã đặt.

Trên V2-M2, `demo-staff` được cấp quyền vận hành khi tạo mới. Vào **Vận hành thuê** để duyệt đổi kỳ, chuẩn bị, bàn giao và nhận trả từng món. Hồ sơ mẫu đã bàn giao từ trước dùng thao tác nhận trả nguyên đơn.

Ảnh WebP trong [thư mục ảnh giao diện](../catalog/static/catalog/images/) được tạo bằng ImageGen. Trang danh mục dùng `editorial.webp`, ảnh người cầm máy cạnh ống kính trên bờ tường bê tông trong ánh nắng cam. Màn đăng nhập dùng `hero.webp`, ảnh máy mirrorless trên đá tối. Ba ảnh minh họa thiết bị `sony.webp`, `canon.webp` và `lens.webp` lần lượt mô phỏng Sony A6400, Canon EOS R50 và Sigma 30mm f/1.4 trong studio. Phông Geist và giấy phép đi kèm nằm trong [thư mục phông chữ](../catalog/static/catalog/fonts/).

Thông số demo dựa trên tài liệu hãng của [Sony A6400](https://www.sony.com/electronics/support/e-mount-body/ilce-6400/specifications), [Canon EOS R50](https://www.usa.canon.com/support/p/eos-r50) và [Sigma 30mm F1.4](https://www.sigma-global.com/en/lenses/c016_30_14/).

## Thông tin nhận–trả cho khách

Điền các giá trị công khai trong `.env`, dựa theo `.env.example`, rồi chạy lại `Start`. Nội dung xuất hiện ở trang thiết bị, form đặt và đơn khách đang có hiệu lực.

| Biến | Nội dung |
| --- | --- |
| `RENTAL_STORE_NAME` | Tên cửa hàng hoặc điểm nhận |
| `RENTAL_PICKUP_ADDRESS` | Địa chỉ nhận và trả |
| `RENTAL_PICKUP_HOURS` | Khung giờ nhận và trả áp dụng |
| `RENTAL_SUPPORT_PHONE` | Số điện thoại công khai |
| `RENTAL_SUPPORT_URL` | Liên kết HTTPS đến kênh hỗ trợ, nếu có |
| `RENTAL_PICKUP_NOTES` | Hướng dẫn nhận máy và các điều kiện đã được cửa hàng xác nhận |

Khi địa chỉ hoặc giờ còn trống, ứng dụng báo phần nào chưa được công bố. Điền phụ kiện thật của từng mẫu trong mục **Thông số và phụ kiện đi kèm** tại màn sửa thiết bị. Nhân viên có lối lọc đơn nhận hôm nay, trả hôm nay và quá hạn trong **Quản lý đơn thuê**.

## Kiểm tra và dựng dữ liệu sạch

```powershell
.\scripts\dev.ps1 -Action Verify -Port 8010
```

`Verify` tạo project Compose và volume mới, chạy system check, kiểm tra thiếu migration, bộ test PostgreSQL và smoke qua HTTP thật. Suite kiểm tranh chấp đặt đơn, bàn giao, đổi kỳ, bảo trì, ghi sổ tiền và mở phiên kiểm kê. Kiểm thử nâng dữ liệu dùng các mốc `catalog.0002`, `catalog.0004`, `catalog.0005`, `catalog.0006` và `catalog.0007`. Nhật ký in tên project và đường dẫn file cấu hình. Chọn cổng trống cho lượt chạy. Smoke ghi dữ liệu mẫu trên project riêng.

Để xác minh ứng viên, dùng checkout sạch của SHA đã chọn và chạy từ thư mục gốc của checkout đó. Ghi SHA vào kết quả. Có thể thêm `-Project camera-base-rc` để phân biệt nhóm kiểm tra, script vẫn tự thêm hậu tố riêng vào tên project.

Nếu Docker báo hết dải subnet mặc định, đối chiếu `docker network inspect` và tuyến mạng của máy. Chọn subnet trống rồi tạo file Compose override ngoài repo với `networks.default.ipam.config` và `subnet` tương ứng. Đặt `COMPOSE_FILE` là `compose.yaml;<đường-dẫn-override>` trong phiên PowerShell chạy Verify. Giữ cấu hình đó khi gọi lại project.

Khi duyệt Base local/demo, mở cổng của project biệt lập. Từ danh mục, tìm `LEN-001`, chọn kỳ tương lai, thử đăng ký, đặt đơn và hủy từ **Đơn của tôi**. Đăng nhập bằng tài khoản staff để xem **Kho thiết bị**, **Quản lý đơn thuê** và đơn demo ở nhóm **Trả hôm nay**. Dùng địa chỉ, giờ và kênh hỗ trợ mẫu nếu cần xem trạng thái cấu hình có nội dung.

`Reset` tạo một project mới có dữ liệu demo sạch và giữ nguyên dữ liệu của project cũ. Chọn cổng khác nếu bản đang chạy vẫn dùng cổng mặc định.

```powershell
.\scripts\dev.ps1 -Action Reset -Port 8011
.\scripts\dev.ps1 -Action Stop
```

`Stop` dừng project mặc định và giữ dữ liệu. Để dừng project biệt lập, dùng đúng tên project và file môi trường đã in khi khởi động.

```powershell
docker compose --env-file <path-to-env> -p <project-name> logs web db
docker compose --env-file <path-to-env> -p <project-name> stop
```

Nếu dùng volume từ bản cũ, đặt `POSTGRES_PASSWORD` trong `.env` bằng mật khẩu đã dùng để khởi tạo volume đó. PostgreSQL chỉ áp dụng mật khẩu từ môi trường khi tạo volume mới. Nếu phiên Codex báo `permission denied` nhưng terminal Windows hiện cả Client và Server, chạy lệnh `Verify` trong terminal Windows đó.

## Chuyển mẫu v1 sang giữ theo mã kho

Migration `catalog.0005` yêu cầu PostgreSQL có extension `btree_gist` hoặc tài khoản migration được phép tạo extension. Migration tạo một dòng theo snapshot của mỗi đơn v1. ID, trạng thái, ngày, giá và timestamp đã lưu vẫn giữ nguyên. Các trường chưa từng được ghi vẫn để trống.

1. Diễn tập trên bản sao PostgreSQL biệt lập trước khi duyệt chuyển đổi môi trường có dữ liệu thật.
2. Trong **Kho thiết bị → Mã kho và lịch giữ**, đăng ký mã kho thực tế cho từng món của mẫu cần chuyển. Nhập serial nếu đã kiểm kê được.
3. Xem danh sách đơn v1 chưa đối soát. Mẫu tiếp tục chạy theo tồn tổng cho đến khi các đơn chưa bàn giao, đang ở ngoài kho hoặc trả sớm còn giữ kỳ đã được xử lý theo vòng đời Base. Màn kho chặn bật giữ theo mã kho khi còn một trong các đơn đó.
4. Khi số lượng đăng ký khớp tổng tồn v1 và danh sách đã hết, bật giữ theo mã kho. Từ đó đơn một dòng và đơn nhiều dòng giữ cùng một nguồn tài sản. Mẫu xuất hiện trong luồng đặt nhiều thiết bị.

Sau khi đã ghi mã kho hoặc đơn nhiều dòng, rollback migration `0005` bị chặn. Với chuyển đổi thật, dùng phương án khôi phục đã diễn tập và giữ các giao dịch phát sinh.

## V2-M2 · Vai trò vận hành

Migration `catalog.0006` giữ lịch và timestamp đã có. Đơn đã bàn giao nguyên đơn trước khi nâng tiếp tục nhận trả ở **Quản lý đơn thuê**. Đơn mới theo mã kho cần xác nhận chuẩn bị đủ món trước khi giao và kiểm tra sau khi nhận. Migration chặn rollback khi đã có lịch sử vận hành hoặc dữ liệu kiểm tra và tình trạng tài sản.

`migrate` tạo nhóm `Rental Operators` và `Rental Managers`. Đối chiếu tài khoản nhân viên hiện có rồi cấp quyền riêng cho từng người. Ví dụ trên project demo mới hoặc project biệt lập, dùng file môi trường và tên project tương ứng.

```powershell
docker compose exec web python manage.py set_rental_role demo-staff operator
docker compose exec web python manage.py set_rental_role <staff-username> manager
```

Quản lý có quyền vận hành và thêm quyền kết thúc hồ sơ bảo trì, mở lại tồn hoặc xác nhận mất. Quyền thao tác cũ trên đơn Base vẫn dùng `is_staff`. [Hợp đồng Web/API](architecture.md#v2-m2--vận-hành-thuê)

## V2-M3 · Quyền quyết toán

`migrate` tạo nhóm `Rental Finance Clerks` và `Rental Finance Managers`. Cấp quyền tài chính cho tài khoản nhân viên theo phân công. Có thể gán cả vai trò vận hành và vai trò quyết toán cho cùng tài khoản.

```powershell
docker compose exec web python manage.py set_rental_role demo-staff finance-clerk
docker compose exec web python manage.py set_rental_role '<ten-quan-ly>' finance-manager
```

Tài khoản `demo-staff` mới đã có quyền ghi thu và hoàn. Với tài khoản demo đã tồn tại từ trước, dùng lệnh cấp quyền ở trên. Quản lý chỉnh cọc ở **Kho thiết bị** và duyệt phí, miễn hoặc khấu trừ tại **Quyết toán tại quầy** trên đơn. Nhân viên ghi tiền mặt hoặc chuyển khoản khi thực thu hoặc thực hoàn. Khoản thu cũ cần chứng từ và quản lý xác nhận trước khi đối soát.

Migration `0007` chặn hạ cấp khi có sổ tiền, đơn mới theo V2-M3 hoặc cấu hình cọc. Diễn tập phương án khôi phục trên bản sao trước khi nâng dữ liệu thật. [Hợp đồng Web/API](architecture.md#v2-m3--quyết-toán-tại-quầy)

## V2-M4 · Quyền báo cáo và kiểm kê

Nhóm `Rental Stock Counters` mở phiên và ghi đối chiếu. Nhóm `Rental Reporting Managers` xem báo cáo, truy vết nguồn và chốt chênh lệch. Tài khoản đã có cần được cấp quyền theo phân công. Tài khoản demo mới `demo-staff` có quyền kiểm kê.

```powershell
docker compose exec web python manage.py set_rental_role demo-staff stock-counter
docker compose exec web python manage.py set_rental_role '<ten-quan-ly>' reporting-manager
```

Lệnh cấp quyền yêu cầu tài khoản nhân viên đang hoạt động. Trong project demo biệt lập, dùng file môi trường và tên project đã in ở Verify. Có thể dùng `demo-staff` để thử quyền báo cáo trên dữ liệu demo.

```powershell
$verifyEnvFile = '<duong-dan-env-tu-Verify>'
$verifyProject = '<ten-project-tu-Verify>'
docker compose --env-file $verifyEnvFile -p $verifyProject exec -T web python manage.py set_rental_role demo-staff reporting-manager
```

Mở phiên từ **Kiểm kê** hoặc màn **Mã kho và lịch giữ** của mẫu đã chuyển đổi. Ghi kết quả từng mã, chọn lượt giao nhận khi có phát sinh, rồi quản lý chốt các dòng khác kỳ vọng. Quản lý vào **Báo cáo**, chọn kỳ và mở liên kết đơn hoặc giao dịch để đối chiếu.

Migration `0008` bảo toàn dữ liệu cũ, ghi mốc theo dõi khi nâng và bảo vệ lịch sử báo cáo khi hạ cấp. [Định nghĩa số liệu](v2-product-design.md#quyết-định-trước-v2-m4) · [Hợp đồng Web/API](architecture.md#v2-m4--báo-cáo-và-kiểm-kê)

## V2-M5 · Diễn tập khôi phục local

Dùng tên project và file môi trường in trong lượt `Verify`, cùng tên database khôi phục chưa tồn tại. Sau khi chạy luồng demo, dừng ghi vào dữ liệu kiểm thử trước khi so sánh.

```powershell
$verifyProject = '<ten-project-tu-Verify>'
$verifyEnvFile = '<duong-dan-env-tu-Verify>'
$composeVerify = @('--env-file', $verifyEnvFile, '-p', $verifyProject)
docker compose @composeVerify exec -T db pg_dump -U camera_rental -d camera_rental -Fc -f /tmp/camera-rental-m5-demo.dump
docker compose @composeVerify exec -T db createdb -U camera_rental camera_m5_restore
docker compose @composeVerify exec -T db pg_restore -U camera_rental -d camera_m5_restore --exit-on-error --no-owner --no-privileges /tmp/camera-rental-m5-demo.dump
docker compose @composeVerify exec -T -e POSTGRES_DB=camera_m5_restore web python manage.py check --database default
```

Đối chiếu schema và bản ghi ở hai database, gồm đơn, giao nhận, sự cố, sổ tiền và phiên kiểm kê. Khi diễn tập nâng từ bản trước, khôi phục dump bản trước vào database mới rồi chạy `migrate --noinput` với `POSTGRES_DB` trỏ đến database đó. Bản sao demo phục vụ nghiệm thu kỹ thuật. Việc dùng dữ liệu cửa hàng và chuyển đổi pilot cần Hải duyệt. [Bằng chứng kiểm chứng](verification.md)


## V3 · Staging và xác minh

Staging dùng image đã ghi SHA hoặc digest, PostgreSQL riêng và tên host có DNS trỏ đến Caddy. Tạo file môi trường ngoài repo với `CAMERA_IMAGE`, `CAMERA_HOST`, `DJANGO_SECRET_KEY`, `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` và `CASH_SHIFT_REQUIRED`. Host và cổng HTTPS phải thông đến Caddy để cấp chứng thư. Chỉ proxy nhận kết nối ngoài. Gunicorn, lệnh quản trị và worker dọn ảnh dùng chung volume ảnh riêng tư.

```powershell
$staging = @('--env-file', '<file-moi-truong>', '-f', 'compose.staging.yaml', '-p', 'camera-staging')
docker compose @staging config --quiet
docker compose @staging run --rm manage check --deploy
docker compose @staging run --rm manage migrate --noinput
docker compose @staging run --rm manage rebuild_finance_snapshots
docker compose @staging run --rm manage rebuild_finance_snapshots --verify
docker compose @staging --profile serve up -d --wait
```

Bật `CASH_SHIFT_REQUIRED=1` từ lúc bắt đầu thu/hoàn có đối soát. Thu, hoàn hoặc đảo giao dịch tiền thật cần ca mở. API lặp đúng mã bút toán cũ vẫn trả kết quả đã ghi. Cấp quyền tạo hộ thêm vào quyền vận hành bằng `python manage.py set_rental_role <nhan-vien> counter-booker`. Trang vận hành hiển thị máy ảnh trên trình duyệt hỗ trợ Barcode Detection API. Nhập tay và máy quét hoạt động như bàn phím dùng cùng form mã kho.

Khi nâng dữ liệu, sao lưu và chạy restore thử ở database mới theo quy trình V2-M5. Chạy `rebuild_finance_snapshots --verify` sau backfill. Đối chiếu đơn, lịch đang giữ, trạng thái tài sản, tổng theo phương thức và các bút toán nguồn trước khi mở ghi. Lưu bản sao PostgreSQL mã hóa và bật lưu WAL ngoài máy chủ qua hạ tầng database. Kiểm tra restore theo thời điểm trước pilot. Kiểm độ trễ bản sao, job dọn ảnh, lỗi 5xx và các ca đã nộp đang chờ duyệt. Đặt thời hạn ảnh trong lưu trữ theo 90 ngày từ ngày tải, kể cả bản sao nếu có.

### Dữ liệu và tải V3

Tạo database biệt lập, dùng mật khẩu giả qua biến môi trường `CAMERA_SCALE_PASSWORD`. Seed trong application container nối database này, rồi chạy tải từ container kết nối cùng database để tạo session tổng hợp và bắn HTTP qua proxy. `--host` phải khớp host của proxy. Với CA thử nghiệm riêng, đặt `SSL_CERT_FILE` trỏ đến CA đó.

```powershell
docker compose @staging exec -T -e CAMERA_SCALE_PASSWORD web python manage.py seed_scale
docker compose @staging exec -T web python -m scripts.v3_load --url https://camera-staging.example.test --host camera-staging.example.test
```

Fixture tạo 5.000 SKU, 10.000 mã và 100.000 đơn lịch sử có bút toán, không sửa dữ liệu cũ. Dùng `--skus 50` trên database mới để thử lệnh nhanh. Mỗi user ảo nghỉ 2,5 giây giữa tương tác. Kết quả ghi p95 qua HTTP, tỷ lệ lỗi, timeout và xung đột giữ lịch. Dùng `--users 10 --warmup 5 --duration 30` để kiểm đường chạy trước phép đo 30 phút. Không chạy trên hệ đang phục vụ người dùng.
