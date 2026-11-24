# Kế hoạch triển khai Camera Rental V3

## Mục tiêu và phạm vi

Phát triển Camera Rental cho một cửa hàng lớn, một kho và một quỹ tiền mặt dùng chung. Nhân viên tạo đơn hộ khách đã có tài khoản, quét theo lô để chuẩn bị và nhận trả, đính ảnh khi phát hiện hỏng hoặc thiếu phụ kiện, rồi đối soát cuối ca. Khách tiếp tục tự tra lịch, đặt thuê và xem đơn. Quản lý xem báo cáo và truy từ số tổng về bản ghi nguồn.

- **Quy mô nghiệm thu:** 5.000 SKU, 10.000 tài sản, 100.000 đơn trong kỳ 12 tháng và 100 người dùng đồng thời.
- **Hiệu quả tại quầy:** Giảm ít nhất 50% thời gian thao tác phần mềm cho kịch bản chuẩn bị và nhận trả đơn 10 món. Đo V2 và V3 trên cùng thiết bị, dữ liệu và kịch bản.
- **Đường cơ sở:** `main` tại `1add478` đã qua 70 test PostgreSQL và HTTP smoke với dữ liệu demo. Ở bộ dữ liệu x100, danh mục web trả 5,2 MB HTML và báo cáo năm mất trung vị 35,7 giây. Pilot thật chờ Hải duyệt cửa hàng, dữ liệu và phương án chuyển đổi. [Kế hoạch dự án](../PROJECT_PLAN.md) · [Bằng chứng V2](verification.md)

## V3-01 · Quyết định nền tảng

Giữ Django, Django Templates và JavaScript, DRF, PostgreSQL, Docker Compose và GitHub Actions. Giữ kiến trúc modular monolith, app label `catalog` và lịch sử migration.

Phép thử fork có thời hạn hai ngày kỹ thuật. Chỉ xem xét nền miễn phí có giấy phép cho phép giữ quyền đóng mã tùy biến. Một ứng viên phải hỗ trợ đơn nhiều SKU, giữ từng mã tài sản khi đặt đồng thời, trả từng món, xử lý hỏng và quyết toán cọc VND. Phép thử gồm chuyển một tập đơn đang mở và lịch sử bút toán. Chỉ đổi nền nếu chi phí triển khai và duy trì 12 tháng thấp hơn ít nhất 25%, dữ liệu cùng hợp đồng đang dùng được bảo toàn và Hải duyệt đổi stack.

RentInfra tại `4f18a66` có giấy phép MIT. Schema bắt buộc mỗi đơn tham chiếu một xe chính và ràng buộc lịch đặt dựa trên xe. Ứng viên dừng ở sàng lọc vì cần sửa lõi đơn và giữ tồn để đáp ứng đơn nhiều SKU. Kết quả là đánh giá mã nguồn. Phạm vi tái sử dụng tiếp theo là thư viện có giấy phép phù hợp và tham chiếu quy trình vận hành công khai. [Giấy phép RentInfra](https://github.com/j4b3r/rentinfra/blob/4f18a663182e16936c791d0b0ba70f0acef0c52f/LICENSE) · [Schema RentInfra](https://github.com/j4b3r/rentinfra/blob/4f18a663182e16936c791d0b0ba70f0acef0c52f/supabase/migrations/001_schema.sql)

## Hàng đợi triển khai

| Mốc | Công việc | Điều kiện kết thúc |
| --- | --- | --- |
| **V3-02 · Staging và pilot V2** | Dựng staging từ image gắn SHA hoặc digest. Dùng WSGI, HTTPS, migration riêng, giám sát và sao lưu. Diễn tập cài mới, nâng từ V2 và khôi phục PostgreSQL. | Có ứng viên tái dựng được và phương án chuyển dữ liệu. Hải duyệt cửa hàng, dữ liệu và lịch trước pilot thật. Các mốc kỹ thuật tiếp tục trên dữ liệu tổng hợp trong thời gian chờ. |
| **V3-03 · Danh mục và báo cáo** | Phân trang trước khi tính khả dụng. Tìm và thêm mẫu vào đơn nhiều SKU, giữ lựa chọn khi đổi bộ lọc. Phân trang lịch sử đơn và chi tiết báo cáo. Tách số tổng khỏi các dòng truy vết. | Danh mục và báo cáo đáp ứng mục tiêu tải. Số tiền khớp sổ nguồn đến từng đồng và mở được bản ghi chi tiết. |
| **V3-04 · Vận hành tại quầy** | Tạo đơn hộ khách đang hoạt động bằng cùng dịch vụ đặt thuê. Quét mã theo lô để chuẩn bị hoặc nhận trả. Hỗ trợ nhập tay. Dùng checklist khi kiểm đạt và đính ảnh vào hồ sơ hỏng hoặc thiếu phụ kiện. | Truy được khách sở hữu và nhân viên thao tác. Mã sai đơn, trùng hoặc sai trạng thái báo lỗi rõ. Quy trình 10 món đạt mục tiêu thời gian. |
| **V3-05 · Đối soát ca** | Mở một ca cho quỹ chung. Ghi quỹ đầu ca và bút toán thu, hoàn, đảo phát sinh. Nộp số tiền đếm được và số chuyển khoản đã đối chiếu. Quản lý chốt chênh lệch kèm cách xử lý. | Số kỳ vọng và số thực tế truy được về ca và bút toán. Retry giữ nguyên kết quả đã ghi. Có thể mở ca mới sau khi nộp ca trước. |
| **V3-06 · Nghiệm thu và phát hành** | Chạy kiểm thử kỹ thuật, đo tải, diễn tập chuyển đổi, kiểm tại quầy và pilot V3. Theo dõi hệ thống và ghi bằng chứng theo SHA. | Đạt các điều kiện nghiệm thu bên dưới và được Hải duyệt phát hành. |

Ước tính sơ bộ 4–6 tuần kỹ thuật cho một người, cộng thời gian pilot và phê duyệt. Làm trên worktree `feature/v3-single-store` từ `main` đã xác minh. Push, PR, merge, release và tag theo các phê duyệt riêng.

## Hợp đồng và quy tắc nghiệp vụ

### Danh mục và báo cáo

- `GET /api/v3/catalog/` nhận bộ lọc hiện hành, cặp ngày thuê tùy chọn, `page` và `page_size`. Mặc định 24 mẫu mỗi trang, tối đa 60. Sắp xếp ổn định theo tên và ID. Chỉ tính lịch cho SKU trong trang.
- `GET /api/v3/management/reports/summary/` trả số tổng và thời điểm tính. Kỳ tối đa 366 ngày theo giờ Việt Nam. Chi tiết phân trang tại `/api/v3/management/reports/{section}/`. Các URL và dạng phản hồi API v1/v2 giữ tương thích.
- Giữ `Ledger` là nơi sở hữu quy tắc số dư. Cập nhật số dư tổng hợp theo đơn trong cùng giao dịch khi nghiệp vụ làm thay đổi giá, phí, trạng thái hủy hoặc sổ tiền. Backfill theo lô và đối chiếu với phép tính gốc trước khi chuyển đường đọc.

### Đặt hộ, quét và bằng chứng sự cố

- Cấp quyền tạo hộ riêng cho nhân viên vận hành. Tra tài khoản khách đang hoạt động bằng tên đăng nhập chính xác. Ghi khách sở hữu và nhân viên tạo. Dùng quy tắc giá, cọc, kỳ thuê và giữ lịch hiện tại.
- Một lượt quét nhận 1–30 mã của một đơn, áp dụng nguyên tử. Có thể nhận trả một phần, còn bàn giao toàn đơn đi qua bước xác nhận hiện hành. Tạo đơn hộ và quét dùng mã yêu cầu. Gửi lại cùng dữ liệu trả kết quả cũ. Cùng mã với dữ liệu khác báo xung đột. Thao tác ảnh hưởng tồn khóa `Equipment` trước `Rental`.
- Hồ sơ hỏng hoặc thiếu phụ kiện có tối đa ba ảnh JPEG, PNG hoặc WebP, mỗi ảnh tối đa 5 MB. Kiểm nội dung tệp, bỏ EXIF và lưu riêng tư. Nhân viên có quyền với hồ sơ và quản lý được xem theo quyền. Tải ảnh là thao tác riêng để thử lại khi lỗi lưu trữ. Xóa ảnh sau 90 ngày kể từ lúc tải và giữ nhật ký.

### Quỹ tiền mặt và chốt ca

- Ca đi theo `OPEN → SUBMITTED → CLOSED`. Một ca mở tại một thời điểm. Nộp ca cố định số liệu. Ca đã nộp có thể chờ quản lý duyệt song song với ca mới.
- Tiền mặt kỳ vọng bằng quỹ đầu ca cộng thu, trừ hoàn, có tính bút toán đảo theo phương thức gốc. Chuyển khoản đối chiếu riêng theo số ròng. Miễn phí và khấu trừ cọc nội bộ không tạo dòng tiền tại quầy.
- Khi có chênh lệch, nhân viên ghi lý do và quản lý ghi cách xử lý. Điều chỉnh sau khi nộp dùng bút toán truy vết ở ca đang mở. Lịch sử trước V3 giữ trạng thái chưa gắn ca. Web và API áp dụng cùng quy tắc ca khi bật tại pilot.

[Kiến trúc và hợp đồng API](architecture.md) · [Thiết lập staging](setup.md)

## Chuyển dữ liệu và vận hành

1. Nâng schema theo hướng cộng thêm. Giữ ID, kỳ cam kết, giá chốt, người thao tác và liên kết giao dịch. Nâng bản sao V2 trên PostgreSQL biệt lập, đối chiếu số hàng, số dư từng đơn, tổng tiền theo phương thức, lịch giữ và lịch sử giao nhận.
2. Khi chuyển chính thức, tạm dừng ghi, sao lưu, chạy chuyển đổi, đối chiếu rồi chỉ mở một hệ thống ghi. Sau khi V3 nhận giao dịch thật, dùng bản sửa tương thích hoặc tạm dừng để xử lý và bảo toàn phát sinh.
3. Sao lưu PostgreSQL mã hóa, lưu WAL ngoài máy chủ và diễn tập khôi phục. Mục tiêu mất dữ liệu tối đa 15 phút, phục hồi trong 60 phút. Giám sát 5xx, độ trễ, thời gian chờ khóa, sao lưu, dọn ảnh và ca chờ duyệt. Ghi môi trường, lệnh, phiên bản, SHA và kết quả.

## Điều kiện nghiệm thu

- **Nghiệp vụ:** Chạy PostgreSQL, HTTP smoke và kiểm quyền cả web lẫn API. Bao phủ tranh máy cuối, đơn nhiều SKU thất bại nguyên tử, quét sai đơn, trả một phần, máy cách ly, ảnh lỗi hoặc hết hạn, hoàn cọc, đảo bút toán, giao dịch tranh khóa với lúc nộp ca và retry sau khi đổi ca. Đối chiếu báo cáo và ca với sổ nguồn.
- **Tải:** 100 người dùng đồng thời trong 30 phút sau khởi động nóng. Tỷ trọng 60% danh mục và tra lịch, 25% vận hành, 10% đặt, 5% báo cáo. p95 phía máy chủ tương ứng dưới 300 ms, 600 ms, 700 ms và 2 giây. 5xx dưới 0,1%. Yêu cầu 0 giữ trùng và 0 ghi tiền lặp. Báo riêng phản hồi 409 hợp lệ do hết tồn.
- **Pilot:** Kiểm giao diện desktop và mobile, quét trên thiết bị tại quầy và đo kịch bản 10 món. Pilot ít nhất 5 ngày hoạt động, 20 đơn và 5 ca. Xử lý hết lỗi chặn giao nhận, tiền và quyền.
- **Phát hành:** Kiểm suite, smoke, khôi phục và CI đúng SHA ứng viên. QA độc lập thực hiện sau khi phạm vi sản phẩm hoàn tất. Hải duyệt phát hành và gắn tag theo quy trình dự án.
