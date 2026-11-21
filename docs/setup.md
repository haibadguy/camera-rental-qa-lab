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

Hình trên danh mục và trang chi tiết là minh họa CSS theo loại thiết bị, dùng chung cho các mẫu cùng loại. Thông số demo dựa trên tài liệu hãng của [Sony A6400](https://www.sony.com/electronics/support/e-mount-body/ilce-6400/specifications), [Canon EOS R50](https://www.usa.canon.com/support/p/eos-r50) và [Sigma 30mm F1.4](https://www.sigma-global.com/en/lenses/c016_30_14/).

## Kiểm tra và dựng dữ liệu sạch

```powershell
.\scripts\dev.ps1 -Action Verify -Port 8010
```

`Verify` tạo project Compose và volume mới, chạy system check, kiểm tra thiếu migration, bộ test PostgreSQL và smoke qua HTTP thật. Nhật ký in tên project và đường dẫn file cấu hình để có thể xem log hoặc giữ môi trường kiểm tra. Smoke tạo tài khoản và đơn mới trên dữ liệu dùng riêng cho lần kiểm tra.

`Reset` tạo một project mới có dữ liệu demo sạch và giữ nguyên dữ liệu của project cũ. Chọn cổng khác nếu bản đang chạy vẫn dùng cổng mặc định.

```powershell
.\scripts\dev.ps1 -Action Reset -Port 8011
.\scripts\dev.ps1 -Action Stop
```

`Stop` dừng project mặc định và giữ dữ liệu. Để dừng project biệt lập, dùng đúng tên project và file môi trường đã in khi khởi động.

```powershell
docker compose --env-file <path-to-env> -p <project-name> down
```

Nếu dùng volume từ bản cũ, đặt `POSTGRES_PASSWORD` trong `.env` bằng mật khẩu đã dùng để khởi tạo volume đó. PostgreSQL chỉ áp dụng mật khẩu từ môi trường khi tạo volume mới. Khi gặp lỗi, xem `docker compose logs web db`. Nếu phiên Codex báo `permission denied` nhưng terminal Windows hiện cả Client và Server, chạy lệnh `Verify` trong terminal Windows đó.
