# Kế hoạch phát triển Camera Rental

## Công việc hiện tại

Định hướng đã duyệt là **Camera Rental Management System**, một Medium Business Application cho một cửa hàng. Mục tiêu phát hành gồm giao nhận, xử lý sự cố, quyết toán tại quầy và báo cáo vận hành. [Phạm vi sản phẩm](docs/v2-product-design.md) · [Roadmap v2.0](ROADMAP.md#roadmap-v20)

| Công việc | Trạng thái | Kết quả cần đạt |
| --- | --- | --- |
| V2-M1 · Tài sản và đơn nhiều dòng | Đã tích hợp và xác minh | PR #5 đã vào `main` tại `9f7e3f5`. Đặt và hủy nguyên đơn, giữ tài sản suốt kỳ, đổi cùng mẫu có lịch sử, backfill dữ liệu Base. [Hợp đồng hiện tại](docs/architecture.md#v2-m1--đặt-nhiều-thiết-bị) · [Bằng chứng V2-M1](docs/verification.md#ci-v2-m1-trên-github) |
| Chính sách V2-M2 | Hải đã duyệt ngày 23/11/2026 | Hạn trả, đổi/gia hạn, giao nhận từng món, sự cố và quyền vận hành. [Năm chính sách](docs/v2-product-design.md#quyết-định-trước-v2-m2) |
| V2-M2 · Rental Operations | Đã tích hợp, CI xanh trên `main` | PR #6 đã vào `main` tại `277f5c0`. Đổi/gia hạn, giao nhận theo mã kho, kiểm tra, cách ly và bảo trì. [Bằng chứng sau merge](docs/verification.md#ci-v2-m2-trên-github) |
| V2-M3 · Pricing & Finance | Đã tích hợp, CI xanh trên `main` | PR #7 đã vào `main` tại `7148810`. Cọc, sổ thu/hoàn, duyệt ngoại lệ, điều chỉnh và đối soát dữ liệu cũ. [Bằng chứng sau merge](docs/verification.md#ci-v2-m3-trên-github) |
| V2-M4 · Management & Reporting | Hải duyệt ngày 24/11/2026 | Báo cáo quản lý, thương hiệu, kiểm kê và truy vết trên `integration/v2-m4-m5`. [Chỉ số và kiểm kê](docs/v2-product-design.md#quyết-định-trước-v2-m4) |
| V2-M5 · Hoàn thiện kỹ thuật | Cùng PR với V2-M4 | Kiểm chứng end-to-end, nâng và phục hồi dữ liệu kiểm thử, UI và bàn giao từ checkout sạch trên cùng ứng viên. Hải duyệt riêng cửa hàng pilot, dữ liệu thật và phát hành. [Điều kiện kiểm chứng](docs/v2-product-design.md#quyết-định-trước-v2-m5) |

Đợt kế tiếp dùng một PR từ `integration/v2-m4-m5` vào `main`, với các commit nhỏ theo từng tính năng để dễ review.

## Base v1.0 · Technical Foundation

Hải duyệt thực thi kế hoạch ngày 22/11/2026. Base là bản **local/demo** theo [R01–R08](docs/requirements.md). Thông tin nhận–trả có cấu hình tùy chọn, xác minh với dữ liệu mẫu hoặc để trống. Công bố thông tin cửa hàng thật và hosting công khai thuộc vận hành. Thanh toán, giao hàng, đặt cọc, phí trả muộn, email/SMS, analytics, đổi frontend framework và tách service nằm ngoài Base. Hải phê duyệt riêng mọi thay đổi nghiệp vụ hoặc stack.

### Điểm xuất phát

Cuối M2, đã có bằng chứng kỹ thuật local cho một phần M3. Audit nhánh `refactor/modular-structure` tại HEAD `0d81fac` ghi 29 file sửa và 20 file untracked, staging trống. Compose biệt lập cổng 18032 pass 31 test PostgreSQL, gồm hai ca đồng thời, và HTTP smoke. Chrome headless đã chạy luồng khách ở 1440 × 1000, 390 × 844 và 320 × 780. Đây là bằng chứng working tree. GitHub Actions cho ứng viên chưa chạy. DRF 3.16.1 có advisory áp dụng cho API, pip 25.0.1 có advisory ở khâu cài package. [Bằng chứng](docs/verification.md) · [DRF security fixes](https://www.django-rest-framework.org/community/release-notes/#3182)

### Hàng đợi đã hoàn tất

[ROADMAP.md](ROADMAP.md) sở hữu milestones và G0–G4. Bảng này sở hữu task, phụ thuộc và trạng thái. Nỗ lực S là một lượt kiểm tra tập trung, M là một phiên triển khai và xác minh.

| Task | Ưu tiên / nỗ lực | Phụ thuộc | Trạng thái | Tiêu chí kết thúc |
| --- | --- | --- | --- | --- |
| T01 · S0 · Khóa kế hoạch | P0 / S | Hải duyệt | DONE | Kế hoạch, scope và hàng đợi ở đây. Roadmap và đặc tả liên kết về đúng nguồn. |
| T02 · S0 · Checkpoint local | P0 / S | T01 | DONE · `8e0a4d9` | Kiểm kê diff, tệp mới, assets và secrets. Review staged diff, tạo commit checkpoint và đọc lại từ bản sao checkout độc lập. |
| T03 · M1/M3 · Vá dependency | P0 / M | T02 | DONE · `40a2a8b` | Nâng DRF lên 3.18.3 và pip lên 26.2. Cold build, `pip check`, quét package cài thực tế, PostgreSQL suite và HTTP smoke đạt với hợp đồng API cũ. |
| T04 · M1 · Kiểm tra hợp đồng và dữ liệu | P0 / M | T03 | DONE · `329d945` | Django check và drift đạt. Trên DB riêng, nâng fixture `catalog.0002` lên `0004`, đối chiếu ID/FK, giá, ngày, trạng thái, timestamp cũ và phân loại `LEN-*`. Hai ca đồng thời phải cho `201/409` và `200/409` cùng số hàng đúng. |
| T05 · M2 · Duyệt UX | P0 / M | T03, dữ liệu từ T04 | DONE · Hải duyệt G2 | Kiểm tra danh mục, xác thực, kỳ thuê, giá, đặt/hủy, kho, đơn staff và trang lỗi. Xác minh desktop/mobile, bàn phím, thông báo lỗi và cấu hình nhận–trả trống/mẫu. Hải duyệt trải nghiệm để G2 pass. |
| T06 · M3 · Xác minh ứng viên local | P0 / M | T04, kiểm tra kỹ thuật T05 | DONE · `d9b052e` | Dựng từ SHA sạch bằng `Verify` trên cổng trống. Ghi SHA, project, phiên bản, images, migrations, seed lặp, PostgreSQL, HTTP smoke, auth/ownership/CSRF và exit code. |
| T07 · M3 · GitHub CI | P0 / S | T06, Hải duyệt push và mở PR | DONE · CI xanh trên `d9b052e` | Ghi link và kết luận CI xanh đúng SHA ứng viên. Chạy lại kiểm chứng liên quan nếu SHA thay đổi. |
| T08 · M4 · Handoff độc lập | P0 / S | T06 | DONE · `329d945` | Reviewer hoặc agent có ngữ cảnh mới dùng tài liệu repo dựng và chạy Verify, rồi chỉ đúng module, test, tác động migration và rollback cho một thay đổi giả định. |
| T09 · M4 · Đóng băng Base | P0 / S | G0–G3 và T08 | DONE · `v1.0.0-qa-baseline` | Hải duyệt ứng viên, merge, release và tag riêng. Nếu SHA sau merge đổi, kiểm chứng đúng commit định gắn tag. `v1.0.0-qa-baseline` trỏ SHA đã duyệt. |

G0–G4 của Base đã đạt. Baseline `v1.0.0-qa-baseline` trỏ commit `31ca8a0` đã qua CI trên `main`. Tag là mốc đối chiếu cho thay đổi sau phát hành. [GitHub Release](https://github.com/haibadguy/camera-rental-qa-lab/releases/tag/v1.0.0-qa-baseline) · [Bằng chứng theo commit](docs/verification.md)

Sau khi đóng băng, bản sửa R08 đã vào `main` tại `b334418`. Form báo lỗi mật khẩu quá ngắn bằng tiếng Việt, giữ ngưỡng tám ký tự và các kiểm tra hiện có. Luồng đăng ký và quay lại trang đặt thuê đã được kiểm chứng. [Trạng thái Base và R08](docs/implementation-status.md) · [Kiểm chứng kỹ thuật](docs/verification.md)

### Biên thay đổi và kiểm chứng của Base

- Web và DRF gọi `catalog.services`. Giữ module nghiệp vụ, hợp đồng URL/JSON, app label và lịch sử migration theo [kiến trúc](docs/architecture.md). PostgreSQL kiểm chứng giữ lịch, tồn vật lý, snapshot giá và thứ tự khóa `Equipment` trước `Rental`.
- Dùng Compose, cổng và PostgreSQL riêng cho kiểm chứng. Giữ volume hiện có. Khi Git hoặc Docker gặp lỗi, ghi lệnh và lỗi cụ thể, giữ checkpoint và retry trên môi trường riêng. Gắn bằng chứng với SHA source và phiên bản image. Xem [setup](docs/setup.md) và [nhật ký kiểm chứng](docs/verification.md).
- Mỗi task theo Spec → Task → Code → Verify → Review → Commit. Mỗi worktree có một người sửa. Nạp skill trong [`.agents/skills`](.agents/skills/) theo task. Review theo diff và yêu cầu liên quan. Khi cần sửa, dùng commit nhỏ có thể hoàn tác.
- Mỗi phiên lấy task đầu tiên còn mở, cập nhật trạng thái, bằng chứng và blocker. Audit toàn dự án ở ứng viên release hoặc khi có sự cố nghiêm trọng. Chỉ mở lại kế hoạch nếu có bằng chứng về sai sót quan trọng, rủi ro mới hoặc quyết định của Hải, rồi ghi mục và gate bị ảnh hưởng tại đây.
- GitHub push, PR, merge, release và tag cần Hải duyệt theo từng hành động.
