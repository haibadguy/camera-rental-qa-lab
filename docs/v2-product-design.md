# Thiết kế Camera Rental Management System

**Định hướng đã duyệt.** Camera Rental là Medium Business Application cho một cửa hàng chuyên nghiệp, một điểm nhận–trả. Khách đặt máy ảnh, ống kính và thiết bị quay chụp. Nhân viên chuẩn bị, giao nhận, kiểm tra và xử lý sự cố. Quản lý đối soát giao dịch tại quầy và xem kết quả kinh doanh từ dữ liệu vận hành.

Giữ đơn nhiều SKU cùng kỳ, khoảng `[ngày nhận, ngày trả)` từ 1–30 ngày, giá VND theo ngày và múi giờ `Asia/Ho_Chi_Minh`. V2-M1 đã tích hợp mã kho duy nhất, serial hãng tùy chọn, giữ thiết bị cụ thể, hủy nguyên đơn, đổi cùng SKU có lịch sử và bảo toàn đơn v1. [Hợp đồng hiện tại](architecture.md#v2-m1--đặt-nhiều-thiết-bị) · [Bằng chứng](verification.md#ci-v2-m1-trên-github)

## Quy trình thực tế và đối chiếu sản phẩm

| Nguồn | Quy trình công bố | Hàm ý cho v2 |
| --- | --- | --- |
| Đà Thành Camera · Đà Nẵng | Cửa hàng xác nhận gia hạn sau khi xét lịch đơn tiếp. Khi giao và nhận lại, hai bên đối chiếu tình trạng, số lượng và phụ kiện. Cửa hàng ghi nhận phát sinh và hoàn cọc sau kiểm tra. [Chính sách cửa hàng](https://dathanhcamera.com/chinh-sach) | Ghi hạn đã cam kết, kiểm tra cuối kỳ và phụ kiện theo thiết bị. Gia hạn cần kiểm xung đột. |
| Camera House và Tikin Camera | Camera House tách khoản trả trước tiền thuê để giữ lịch và cọc bảo đảm khi giao thiết bị. Tikin có quy tắc riêng theo kênh đặt, thời hạn hoàn cọc và phí trễ. [Camera House](https://camerahouse.vn/pages/quy-trinh-thue-thiet-bi-tai-camera-house) · [Tikin](https://tikincamera.com/chinh-sach) | Tách giữ lịch, tiền thuê và cọc bảo đảm. Mức thu, thời điểm thu và chính sách hoàn cần xác nhận với cửa hàng pilot. |
| Lensrentals | Kiểm tra ngoại quan và chức năng trước và sau mỗi lượt thuê ống kính. Thiết bị có vấn đề ảnh hưởng chất lượng được đưa ra khỏi vòng cho thuê để xử lý. [Quy trình kiểm tra](https://help.lensrentals.com/26466-first-time-renters/204100-is-the-equipment-in-good-condition) | Việc nhận máy về và việc máy đủ điều kiện cho thuê tiếp là hai sự kiện. |
| Booqable | Một đơn có nhiều mẫu, có thể gán thiết bị cụ thể lúc chuẩn bị hoặc bàn giao. Hỗ trợ gia hạn sau khi kiểm lịch và hoàn hoặc giữ một phần cọc. [Thêm thiết bị vào đơn](https://help.booqable.com/en/articles/99552-how-to-add-products-to-an-order) · [Vòng đời đơn](https://help.booqable.com/en/articles/3845244-the-booqable-order-workflow) · [Cọc bảo đảm](https://help.booqable.com/en/articles/101604-how-to-set-up-refundable-security-deposits) | Khách chọn mẫu và số lượng. Việc chọn máy cụ thể, bàn giao và quyết toán do nhân viên xử lý. |
| Rentman và OnRent Events | Rentman ghi nhận thiếu hụt do trả trễ và chuyển thiết bị lỗi theo serial sang luồng sửa chữa. OnRent Events hỗ trợ nhận lại từng món, theo dõi món còn thiếu và cách ly món hỏng. [Lịch kho Rentman](https://support.rentman.io/hc/en-us/articles/360012699859-Equipment-Availability-Based-on-Warehouse-Movements) · [Thiết bị lỗi Rentman](https://support.rentman.io/hc/en-us/articles/17531415206418-How-to-Handle-Lost-or-Defective-Equipment-in-the-Warehouse) · [Nhận trả OnRent Events](https://help.current-rms.com/en/articles/385106-check-in-return-products) | Nhân viên cần thấy đơn sắp giao bị ảnh hưởng, ghi nhận từng món khi trả và cách ly máy hỏng ngay. |

Đây là chính sách và tài liệu tính năng công khai. Điều kiện của cửa hàng mục tiêu và tần suất các ngoại lệ chưa được xác minh qua phỏng vấn hay quan sát tại quầy.

## Tám phân hệ và phần còn thiếu

| Phân hệ | Đã có trên V2-M1 | Phần cần hoàn thành |
| --- | --- | --- |
| Accounts & RBAC | Django auth, khách sở hữu đơn, quyền nhân viên bằng `is_staff`. | V2-M2 phân quyền nghiệp vụ cho khách, nhân viên và quản lý. V2-M3 và V2-M4 bổ sung quyền tiền và báo cáo. |
| Equipment Catalog | Tìm theo tên hoặc mã, lọc loại, giá ngày, thông số và nội dung phụ kiện. | V2-M2 chuẩn hóa danh sách phụ kiện cần kiểm theo mẫu. V2-M4 bổ sung thương hiệu và bộ lọc cần cho danh mục, kiểm kê. |
| Asset & Inventory | Mã kho duy nhất, serial tùy chọn, giữ toàn kỳ, lịch, đổi máy cùng SKU và phân biệt tồn theo lịch với tồn thực tế. | V2-M2 xác định hiện trạng từng tài sản có thể giao. V2-M4 đối chiếu kiểm kê, lịch sử chênh lệch và người xử lý. |
| Rental Booking | Khách đặt và hủy nhiều SKU chung kỳ. Lưu giá theo dòng và giữ chỗ nguyên tử. | V2-M2 thêm yêu cầu đổi lịch hoặc gia hạn, xử lý xung đột và lưu lịch sử quyết định. |
| Rental Operations | Bàn giao và nhận trả nguyên đơn, không đến nhận, quá hạn theo Base. | V2-M2 chuẩn bị, xác nhận từng mã kho, nhận trả một phần, ghi món còn thiếu, trễ, mất hoặc hỏng và đơn sau bị ảnh hưởng. |
| Pricing & Financial Settlement | Báo giá ngày bằng VND và snapshot tiền thuê. | V2-M3 ghi tiền tại quầy, tách tiền thuê và cọc, xử lý thu thêm, hoàn, khấu trừ và điều chỉnh có phê duyệt. |
| Equipment Maintenance | Lịch giữ theo tài sản và khả năng đổi máy cùng mẫu. | V2-M2 kiểm tra, cách ly, sửa và xác nhận đủ điều kiện đưa về kho. |
| Dashboard & Reporting | Hàng đợi đơn cho nhân viên. | V2-M4 báo cáo doanh thu, đơn, tài sản đang thuê và tỷ lệ sử dụng từ bản ghi thật. |

Tám phân hệ là ranh giới nghiệp vụ trong cùng một modular monolith. Giữ một kho, một cửa hàng và một bộ quy tắc. Phạm vi phát hành gồm thu và hoàn nội bộ tại quầy. Đa chi nhánh, marketplace, cổng thanh toán online, API đối tác, CRM phức tạp, chatbot hoặc gợi ý AI, microservices và kiến trúc phân tán nằm ngoài phạm vi đã duyệt. Yêu cầu mới phải phục vụ được một tiêu chí nghiệm thu ở [mốc hiện có](../ROADMAP.md#roadmap-v20) hoặc chờ Hải duyệt thay đổi phạm vi.

## Hành trình phát hành

1. **Khách đặt thuê.** Chọn mẫu và số lượng, kiểm cả kỳ, xác nhận khi đủ tất cả dòng. Khách thấy lịch và giá đã chốt. Giỏ bỏ dở không chiếm kho.
2. **Nhân viên chuẩn bị và giao.** Đối chiếu từng mã kho, phụ kiện và tình trạng, xử lý thiếu bằng đổi máy cùng SKU nếu còn lịch phù hợp, rồi ghi bàn giao. Thao tác đổi hoặc gia hạn dùng chung quy tắc tồn.
3. **Nhân viên nhận trả và kiểm tra.** Ghi thời điểm thực tế cho từng món, kể cả khi trả một phần. Tách món còn ở ngoài kho, chờ kiểm và được phép giao tiếp. Sự cố phải nêu rõ đơn hoặc tài sản bị ảnh hưởng, ai đang xử lý và hành động tiếp theo.
4. **Quản lý xử lý ngoại lệ và quyết toán.** Phê duyệt đóng sự cố hoặc cho máy trở lại kho sau kiểm tra. Ghi khoản phải thu, miễn, hoàn hoặc khấu trừ theo chính sách M3 đã duyệt. Truy lại từng thay đổi và chứng từ ghi nhận tại quầy.
5. **Quản lý xem kết quả.** Đối chiếu doanh thu và số dư với sổ tiền, tỷ lệ sử dụng với dữ liệu thuê theo tài sản và kiểm kê với tình trạng thực tế. M5 xác minh hành trình đầy đủ bằng dữ liệu pilot đã được duyệt.

## Quyết định trước V2-M2

Các mặc định dưới đây chờ Hải duyệt. Bộ quyết định được duyệt sẽ là căn cứ triển khai V2-M2.

| Quyết định | Mặc định đề xuất | Đánh đổi |
| --- | --- | --- |
| **1. Hạn trả và trả sớm** | Giữ quy tắc Base theo ngày Việt Nam. Từ ngày sau ngày trả, món chưa về bị đánh dấu trễ. Ngay ngày hẹn trả, món chưa sẵn sàng đã hiện rủi ro cho đơn sắp giao. Trả sớm kết thúc việc giữ tài sản ngoài kho, còn lịch giữ đến hết kỳ đã cam kết. Giữ cách hiểu này với đơn v1. | Hạn theo giờ và thời gian ân hạn sát ca làm hơn nhưng cần giờ cam kết tin cậy và quy tắc riêng cho đơn cũ. Giữ lịch khi trả sớm có thể làm giảm lượt thuê mới trong phần kỳ còn lại. |
| **2. Đổi lịch và gia hạn** | Khách gửi yêu cầu, nhân viên kiểm lịch rồi phê duyệt. Đổi trước bàn giao áp dụng cho cả đơn, giữ các SKU và số lượng. Gia hạn trước khi quá hạn, khi chưa có món nào trả hay đóng ngoại lệ. Giữ ngày nhận và giới hạn tổng kỳ 30 ngày. Tính lại tiền thuê theo đơn giá đã chốt, ghi chấp thuận của khách nếu tổng thay đổi. Tranh chấp tồn giữ nguyên lịch và giá trước đó. | Gia hạn từng món hoặc sau khi đã trả một phần linh hoạt hơn nhưng tạo nhiều hạn trả và nhiều lần đối soát trong một đơn. |
| **3. Bàn giao và trả từng món** | Nhân viên ghi kiểm tra theo mã kho khi chuẩn bị và xác nhận bàn giao một lần sau khi đủ đơn. Nhận trả từng món với timestamp và người thao tác. Món đã về nhưng chờ kiểm vẫn bị chặn sử dụng. Giữ lịch sử giao nhận nguyên đơn của v1 và duy trì luồng Base cho SKU chưa đối soát. | Giao từng phần và nhiều đợt cần thêm quy tắc giữ chỗ, xử lý món chưa giao và tính tiền, nên cần duyệt riêng nếu phát sinh nhu cầu. |
| **4. Mất, hỏng, thiếu phụ kiện và bảo trì** | Nhân viên ghi sự cố và cách ly ngay món chưa đủ điều kiện cho thuê. Hiển thị các đơn kế tiếp bị ảnh hưởng và cho đổi cùng SKU khi đủ lịch. Bảo trì đã lên lịch phải kiểm xung đột trước khi lưu. Quản lý duyệt đóng sự cố, đưa máy đã kiểm tra đạt về kho hoặc loại khỏi vòng thuê. Đơn có món được xác nhận mất được đóng có ngoại lệ với dấu thời gian quyết định riêng. | Quản lý có thêm bước duyệt nhưng truy được ai cho máy vào lại kho hoặc đóng món mất. Hồ sơ sự cố cung cấp dữ liệu cho M3. Quy tắc bồi thường, phí và khấu trừ cần duyệt riêng. |
| **5. Quyền vận hành và liên hệ** | Dùng nhóm và quyền Django. Khách xem đơn của mình. Nhân viên chuẩn bị, đổi lịch, giao nhận và ghi sự cố. Quản lý xử lý mất, duyệt ngoại lệ và mở lại tồn sau bảo trì. Hiển thị trạng thái trên đơn và dùng kênh liên hệ hiện có của cửa hàng. | Nếu cần lưu số liên hệ riêng trên đơn, chốt mục đích, quyền đọc và thời hạn giữ thông tin. Đối chiếu quyền hiện tại trước khi gán nhóm cho tài khoản nhân viên cũ. |

**Trước V2-M3**, Hải duyệt đơn giá áp dụng cho các trường hợp ngoài kỳ gốc, mức cọc, thời điểm thu, điều kiện và thời hạn hoàn, phí hoặc trách nhiệm bồi thường, quyền miễn hay khấu trừ và xử lý tiền đã thu khi giao thất bại. **Trước V2-M4**, chốt định nghĩa doanh thu, tỷ lệ sử dụng và cách xử lý chênh lệch kiểm kê. **Trước V2-M5**, chốt cửa hàng pilot, dữ liệu được phép dùng, phương án chuyển dữ liệu và hợp đồng API cũ. [Kiến trúc và điểm chuyển dữ liệu](architecture.md#kiến-trúc-mục-tiêu) · [Điều kiện phát hành](../ROADMAP.md#roadmap-v20)
