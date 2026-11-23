# Trạng thái thực thi Camera Rental

## V2-M3 · Quyết toán tại quầy

`feature/v2-m3` có cấu hình cọc theo mẫu, chốt cọc theo dòng, sổ thu/hoàn, duyệt và khấu trừ phí, liên kết giao dịch đảo và đối soát chứng từ cũ. Đơn mới kiểm đủ tiền trước khi bàn giao trên Web và API. [Chính sách đã duyệt](v2-product-design.md#quyết-định-trước-v2-m3) · [Kiến trúc](architecture.md#v2-m3--quyết-toán-tại-quầy)

Runtime `be0a617` đã đạt Verify trên Compose biệt lập, 62 test PostgreSQL và kiểm tra Chrome desktop/mobile. CI của V2-M3 chờ duyệt push. [Bằng chứng V2-M3](verification.md#v2-m3--24112026)

## V2-M2 · Đã tích hợp

PR #6 đưa giao nhận theo mã kho, đổi kỳ, bảo trì và phân quyền vận hành vào `main` tại `277f5c0`. CI sau merge đạt. [PR #6](https://github.com/haibadguy/camera-rental-qa-lab/pull/6) · [Bằng chứng theo SHA](verification.md#ci-v2-m2-trên-github)

| Nguồn | Phần hợp nhất |
| --- | --- |
| Worktree chính, ban đầu ở `04a50b3` | Giữ model, migration `0006`, quyền vận hành, giao nhận và Schedule dùng khóa chung. |
| Maintenance, detached `00a2c65` | Tích hợp domain, kiểm thử cách ly và tranh chấp bảo trì. Kết quả kiểm tra khi nhận trả đi qua Maintenance trong cùng giao dịch. |
| Schedule, detached `5e95e3e` | Đối chiếu với bản chính. Giữ bản dùng `custody.lock_rental` và lấy ca từ chối gia hạn sau nhận trả một món qua service thật. |
| Web, detached `04a50b3` | Tích hợp hai adapter, sáu template và nối quyền, route, điều hướng, lịch kho. Template mới nằm trong `customer/` và `staff/`. |

Các điểm khôi phục local nằm dưới `refs/checkpoints/v2-m2/`: `original-index` (`bf4bee6`), `original-main` (`32383fb`) và `original-web` (`9115b49`). Worktree gốc của Maintenance và Schedule giữ các commit đã đối chiếu. Đọc tài liệu QA lịch sử bằng `git show 04a50b3:docs/qa/r01-catalog.md`.

## Các mốc đã lên main

V2-M1 đã tích hợp tại `9f7e3f5` với giữ lịch theo mã kho và đơn nhiều dòng. [Bằng chứng V2-M1](verification.md#ci-v2-m1-trên-github)

Base v1.0 đã đóng băng sau khi đạt G0–G4. Tag `v1.0.0-qa-baseline` trỏ đến `31ca8a0d282ae1e29017d7f3e6ab0f7973d27fee`. [Bằng chứng phát hành](verification.md) · [GitHub Release](https://github.com/haibadguy/camera-rental-qa-lab/releases/tag/v1.0.0-qa-baseline)

Bản sửa thông báo mật khẩu R08 sau đóng băng đã vào `main` ở `b334418` và có CI xanh. [PR #3](https://github.com/haibadguy/camera-rental-qa-lab/pull/3) · [CI sau bản sửa](https://github.com/haibadguy/camera-rental-qa-lab/actions/runs/45027902369)
