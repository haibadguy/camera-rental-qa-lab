# Master Plan · Camera Rental Base v1.0

Hải duyệt thực thi kế hoạch ngày 22/11/2026. Base là bản **local/demo** theo [R01–R08](docs/requirements.md). Thông tin nhận–trả có cấu hình tùy chọn, xác minh với dữ liệu mẫu hoặc để trống. Công bố thông tin cửa hàng thật và hosting công khai thuộc vận hành. Thanh toán, giao hàng, đặt cọc, phí trả muộn, email/SMS, analytics, đổi frontend framework và tách service nằm ngoài Base. Hải phê duyệt riêng mọi thay đổi nghiệp vụ hoặc stack.

## Điểm xuất phát

Cuối M2, đã có bằng chứng kỹ thuật local cho một phần M3. Audit nhánh `refactor/modular-structure` tại HEAD `0d81fac` ghi 29 file sửa và 20 file untracked, staging trống. Compose biệt lập cổng 18032 pass 31 test PostgreSQL, gồm hai ca đồng thời, và HTTP smoke. Chrome headless đã chạy luồng khách ở 1440 × 1000, 390 × 844 và 320 × 780. Đây là bằng chứng working tree. GitHub Actions cho ứng viên chưa chạy. DRF 3.16.1 có advisory áp dụng cho API, pip 25.0.1 có advisory ở khâu cài package. [Bằng chứng](docs/verification.md) · [DRF security fixes](https://www.django-rest-framework.org/community/release-notes/#3182)

## Hàng đợi thực thi

[ROADMAP.md](ROADMAP.md) sở hữu milestones và G0–G4. Bảng này sở hữu task, phụ thuộc và trạng thái. Nỗ lực S là một lượt kiểm tra tập trung, M là một phiên triển khai và xác minh.

| Task | Ưu tiên / nỗ lực | Phụ thuộc | Trạng thái | Tiêu chí kết thúc |
| --- | --- | --- | --- | --- |
| T01 · S0 · Khóa kế hoạch | P0 / S | Hải duyệt | DONE | Kế hoạch, scope và hàng đợi ở đây. Roadmap và đặc tả liên kết về đúng nguồn. |
| T02 · S0 · Checkpoint local | P0 / S | T01 | Đang làm | Kiểm kê diff, tệp mới, assets và secrets. Review staged diff, tạo commit checkpoint và đọc lại từ bản sao checkout độc lập. |
| T03 · M1/M3 · Vá dependency | P0 / M | T02 | Chờ | Nâng DRF lên 3.18.3 và pip lên 26.2. Cold build, `pip check`, quét package cài thực tế, PostgreSQL suite và HTTP smoke đạt với hợp đồng API cũ. |
| T04 · M1 · Kiểm tra hợp đồng và dữ liệu | P0 / M | T03 | Chờ | Django check và drift đạt. Trên DB riêng, nâng fixture `catalog.0002` lên `0004`, đối chiếu ID/FK, giá, ngày, trạng thái, timestamp cũ và phân loại `LEN-*`. Hai ca đồng thời phải cho `201/409` và `200/409` cùng số hàng đúng. |
| T05 · M2 · Duyệt UX | P0 / M | T03, dữ liệu từ T04 | Chờ | Kiểm tra danh mục, xác thực, kỳ thuê, giá, đặt/hủy, kho, đơn staff và trang lỗi. Xác minh desktop/mobile, bàn phím, thông báo lỗi và cấu hình nhận–trả trống/mẫu. Hải duyệt trải nghiệm để G2 pass. |
| T06 · M3 · Xác minh ứng viên local | P0 / M | T04, kiểm tra kỹ thuật T05 | Chờ | Dựng từ SHA sạch bằng `Verify` trên cổng trống. Ghi SHA, project, phiên bản, images, migrations, seed lặp, PostgreSQL, HTTP smoke, auth/ownership/CSRF và exit code. |
| T07 · M3 · GitHub CI | P0 / S | T06, Hải duyệt push và mở PR | Chờ | Ghi link và kết luận CI xanh đúng SHA ứng viên. Chạy lại kiểm chứng liên quan nếu SHA thay đổi. |
| T08 · M4 · Handoff độc lập | P0 / S | T06 | Chờ | Reviewer hoặc agent có ngữ cảnh mới dùng tài liệu repo dựng và chạy Verify, rồi chỉ đúng module, test, tác động migration và rollback cho một thay đổi giả định. |
| T09 · M4 · Đóng băng Base | P0 / S | G0–G3 và T08 | Chờ | Hải duyệt ứng viên, merge, release và tag riêng. Nếu SHA sau merge đổi, kiểm chứng đúng commit định gắn tag. `v1.0.0-qa-baseline` trỏ SHA đã duyệt. |

## Biên thay đổi và kiểm chứng

- Web và DRF gọi `catalog.services`. Giữ module nghiệp vụ, hợp đồng URL/JSON, app label và lịch sử migration theo [kiến trúc](docs/architecture.md). PostgreSQL kiểm chứng giữ lịch, tồn vật lý, snapshot giá và thứ tự khóa `Equipment` trước `Rental`.
- Dùng Compose, cổng và PostgreSQL riêng cho kiểm chứng. Giữ volume hiện có. Khi Git hoặc Docker gặp lỗi, ghi lệnh và lỗi cụ thể, giữ checkpoint và retry trên môi trường riêng. Gắn bằng chứng với SHA source và phiên bản image. Xem [setup](docs/setup.md) và [nhật ký kiểm chứng](docs/verification.md).
- Mỗi task theo Spec → Task → Code → Verify → Review → Commit. Mỗi worktree có một người sửa. Nạp skill trong [`.agents/skills`](.agents/skills/) theo task. Review theo diff và yêu cầu liên quan. Khi cần sửa, dùng commit nhỏ có thể hoàn tác.
- Mỗi phiên lấy task đầu tiên còn mở, cập nhật trạng thái, bằng chứng và blocker. Audit toàn dự án ở ứng viên release hoặc khi có sự cố nghiêm trọng. Chỉ mở lại kế hoạch nếu có bằng chứng về sai sót quan trọng, rủi ro mới hoặc quyết định của Hải, rồi ghi mục và gate bị ảnh hưởng tại đây.
- GitHub push, PR, merge, release và tag cần Hải duyệt theo từng hành động. Phase 2 chỉ bắt đầu sau khi baseline đóng băng và Hải xác nhận mở Phase 2.
