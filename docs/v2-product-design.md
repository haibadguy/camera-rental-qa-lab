# Camera Rental v2.0 Complete Rental Operations

**Đề xuất ngày 22/11/2026 · Chờ Hải duyệt quy tắc nghiệp vụ.** v2 phục vụ một cửa hàng cho thuê máy ảnh, ống kính và thiết bị quay chụp. Khách có thể đặt nhiều món cho cùng kỳ thuê. Nhân viên theo dõi được từng thiết bị từ lúc giữ lịch đến khi đã kiểm tra sau trả. Quản lý có thể giải thích từng khoản thu, khấu trừ và hoàn cọc từ lịch sử đơn.

Hải đã duyệt V2-M1. Hợp đồng đã triển khai và cách đối soát mẫu v1 nằm trong [kiến trúc](architecture.md) và [thiết lập](setup.md#chuyển-mẫu-v1-sang-giữ-theo-mã-kho). Các quyết định theo mốc sau tiếp tục được duyệt riêng.

Pilot đề xuất dùng một điểm nhận–trả trực tiếp, giá ngày bằng VND và thanh toán do nhân viên ghi nhận tại quầy. Giữ kỳ `[ngày nhận, ngày trả)`, 1–30 ngày và múi giờ `Asia/Ho_Chi_Minh` theo Base. [Đặc tả Base](requirements.md) · [Roadmap sản phẩm](../ROADMAP.md)

## Quy trình thực tế và đối chiếu sản phẩm

| Nguồn | Quy trình công bố | Hàm ý cho v2 |
| --- | --- | --- |
| Đà Thành Camera · Đà Nẵng | Cửa hàng xác nhận gia hạn sau khi xét lịch đơn tiếp. Khi giao và nhận lại, hai bên đối chiếu tình trạng, số lượng và phụ kiện. Cửa hàng ghi nhận phát sinh và hoàn cọc sau kiểm tra. [Chính sách cửa hàng](https://dathanhcamera.com/chinh-sach) | Ghi hạn đã cam kết, kiểm tra cuối kỳ và phụ kiện theo thiết bị. Gia hạn cần kiểm xung đột. |
| Camera House và Tikin Camera | Camera House tách khoản trả trước tiền thuê để giữ lịch và cọc bảo đảm khi giao thiết bị. Tikin có quy tắc riêng theo kênh đặt, thời hạn hoàn cọc và phí trễ. [Camera House](https://camerahouse.vn/pages/quy-trinh-thue-thiet-bi-tai-camera-house) · [Tikin](https://tikincamera.com/chinh-sach) | Tách giữ lịch, tiền thuê và cọc bảo đảm. Mức thu, thời điểm thu và chính sách hoàn cần xác nhận với cửa hàng pilot. |
| Lensrentals | Kiểm tra ngoại quan và chức năng trước và sau mỗi lượt thuê ống kính. Thiết bị có vấn đề ảnh hưởng chất lượng được đưa ra khỏi vòng cho thuê để xử lý. [Quy trình kiểm tra](https://help.lensrentals.com/26466-first-time-renters/204100-is-the-equipment-in-good-condition) | Việc nhận máy về và việc máy đủ điều kiện cho thuê tiếp là hai sự kiện. |
| Booqable | Một đơn có nhiều mẫu, có thể gán thiết bị cụ thể lúc chuẩn bị hoặc bàn giao. Hỗ trợ gia hạn sau khi kiểm lịch và hoàn hoặc giữ một phần cọc. [Thêm thiết bị vào đơn](https://help.booqable.com/en/articles/99552-how-to-add-products-to-an-order) · [Vòng đời đơn](https://help.booqable.com/en/articles/3845244-the-booqable-order-workflow) · [Cọc bảo đảm](https://help.booqable.com/en/articles/101604-how-to-set-up-refundable-security-deposits) | Khách chọn mẫu và số lượng. Việc chọn máy cụ thể, bàn giao và quyết toán do nhân viên xử lý. |
| Rentman và OnRent Events | Rentman ghi nhận thiếu hụt do trả trễ và chuyển thiết bị lỗi theo serial sang luồng sửa chữa. OnRent Events hỗ trợ nhận lại từng món, theo dõi món còn thiếu và cách ly món hỏng. [Lịch kho Rentman](https://support.rentman.io/hc/en-us/articles/360012699859-Equipment-Availability-Based-on-Warehouse-Movements) · [Thiết bị lỗi Rentman](https://support.rentman.io/hc/en-us/articles/17531415206418-How-to-Handle-Lost-or-Defective-Equipment-in-the-Warehouse) · [Nhận trả OnRent Events](https://help.current-rms.com/en/articles/385106-check-in-return-products) | Nhân viên cần thấy đơn sắp giao bị ảnh hưởng, ghi nhận từng món khi trả và cách ly máy hỏng ngay. |

Đây là chính sách và tài liệu tính năng công khai. Điều kiện của cửa hàng mục tiêu và tần suất các ngoại lệ chưa được xác minh qua phỏng vấn hay quan sát tại quầy.

## Hành trình khách và nhân viên

1. **Đặt thuê.** Khách tìm mẫu, chọn một kỳ, thêm thân máy, ống kính và phụ kiện cho thuê vào giỏ. Giỏ hiển thị tiền thuê và cọc dự kiến theo từng dòng. Sau khi xác nhận, cả đơn giữ được lịch hoặc khách nhận thông báo món thiếu và giữ được giỏ để sửa. Chi tiết đơn hiển thị giá đã chốt, nơi nhận, ngày trả và các yêu cầu đổi lịch.
2. **Chuẩn bị và bàn giao.** Nhân viên mở hàng đợi nhận hôm nay, xác nhận mã tài sản, đối chiếu checklist tình trạng và phụ kiện đi kèm, đổi máy cùng mẫu nếu cần và kiểm lại tồn vật lý trước khi thu tiền. Với đơn mới theo chính sách pilot, nhân viên ghi tiền thuê và cọc đã nhận tại quầy trước khi xác nhận bàn giao đủ đơn. Nếu đã thu tiền mà việc giao thất bại, đơn vào hàng đợi xử lý khoản đã thu.
3. **Đổi lịch và gia hạn.** Khách gửi yêu cầu từ đơn của mình và thấy giá chênh lệch dự kiến. Nhân viên đối chiếu kỳ mới và các đơn tiếp theo, ghi xác nhận của khách nếu tổng tiền đổi. Khi duyệt, lịch và giá mới được cập nhật cùng lúc và có lịch sử. Nếu thiếu tồn, điều kiện cũ vẫn có hiệu lực. Khách tự hủy trước ngày nhận và nhân viên xử lý `NO_SHOW` theo quy tắc Base.
4. **Nhận trả và xử lý sự cố.** Nhân viên ghi giờ nhận thực tế từng món, đối chiếu phụ kiện và kết quả kiểm tra. Món chưa trả vẫn ở ngoài kho. Món đã nhận chờ kiểm tra hoặc hỏng được giữ lại trong kho chờ xử lý. Nếu đơn sau thiếu máy, nhân viên thấy nguyên nhân, tìm máy thay thế cùng mẫu hoặc chuyển quản lý liên hệ khách. Khách xem tình trạng cập nhật trên đơn. Pilot đề xuất một số liên hệ riêng trên đơn để nhân viên được phân quyền gọi khi cần.
5. **Quyết toán và bảo trì.** Quản lý duyệt khoản phát sinh có lý do và căn cứ. Nhân viên ghi nhận tiền hoàn, cọc dùng để bù khoản phải thu hoặc phần khách trả thêm. Thiết bị bị cách ly chỉ trở lại danh mục có thể giao sau khi có kết quả kiểm tra đạt. Khách xem được các khoản của đơn mình và số cọc còn chờ xử lý.

## Nghiệp vụ và kết quả nghiệm thu đề xuất

| Mã | Phạm vi v2.0 | Kết quả bắt buộc |
| --- | --- | --- |
| V2-01 | Danh mục và tài sản | Giữ SKU để khách tìm mẫu. Mỗi tài sản có mã kho duy nhất, serial hãng nếu có và lịch sử sử dụng. Pilot có danh mục đủ để đặt một bộ quay gồm nhiều loại thiết bị, với ít nhất hai tài sản cùng mẫu để đổi máy. Pin, nắp và dây đi kèm nằm trong checklist của từng món. |
| V2-02 | Lịch và đơn nhiều dòng | Một đơn có nhiều SKU, cùng kỳ. Mỗi món khả dụng suốt kỳ. Giỏ bỏ dở không chiếm kho. Đặt, đổi lịch, gia hạn và hủy cập nhật toàn bộ dòng liên quan trong một giao dịch. Lịch cũ, snapshot giá và quyết định được truy vết. |
| V2-03 | Giao, nhận và xử lý quá hạn | Giao đủ đơn bằng mã từng tài sản. Nhận trả từng phần có giờ nhận và người thao tác. Ghi riêng món còn thiếu, món chờ kiểm và món đã đạt. Đơn bị ảnh hưởng bởi trả trễ hoặc tài sản hỏng xuất hiện trong hàng đợi của nhân viên. |
| V2-04 | Sự cố và bảo trì | Ghi sự cố theo tài sản, phân biệt hỏng, mất và thiếu phụ kiện. Bảo trì định kỳ theo khoảng lịch, cách ly ngay sự cố phát sinh. Quản lý duyệt kết quả sửa, trả về kho hoặc loại khỏi vòng thuê. Xử lý món mất ghi quyết định và thời điểm riêng, không tạo giờ nhận trả giả. |
| V2-05 | Tiền thuê, cọc và phát sinh | Giá ngày và cọc cam kết được lưu lúc xác nhận. Đơn VND đối soát được tiền thuê, cọc, khoản phát sinh, tiền hoàn và số còn phải thu. Khoản khấu trừ, sửa bút toán hoặc miễn phí có người duyệt và lý do. Gửi lại thao tác không ghi thu hoặc hoàn lần hai. |
| V2-06 | Quyền, lịch sử và màn vận hành | Khách chỉ thấy đơn, yêu cầu thay đổi và số tiền của mình. Nhân viên xử lý giao nhận, thu và hoàn theo quyền. Quản lý duyệt phí, khấu trừ, điều chỉnh và đóng sự cố. Dùng nhóm và quyền Django, kiểm tra tại backend. Hàng đợi gồm nhận, trả, quá hạn, thiếu thiết bị, chờ kiểm và chờ đối soát. |

**Sau v2.0.** Đa chi nhánh, giao hàng, giá theo giờ/gói/cuối tuần, khuyến mãi, bộ kit có quy tắc thay thế, QR/barcode, ảnh tình trạng, lưu giấy tờ định danh, cổng thanh toán, email/SMS, CRM và báo cáo tài chính nằm ngoài pilot. v3 chỉ mở khi vận hành v2 cho thấy nhu cầu cụ thể. [Roadmap sản phẩm](../ROADMAP.md)

## Kiến trúc và dữ liệu

Tiếp tục Django, Django Templates, DRF, PostgreSQL và Docker Compose. Giữ app label `catalog`, auth Django, các migration `0001`–`0004` và `catalog/services.py` làm điểm vào chung cho web/API. Tận dụng danh mục, xác thực, kiểm kỳ thuê, snapshot VND, hàng đợi nhân viên và quy trình Verify. Phần nghiệp vụ mới thay đổi cách tính tồn tổng và cấu trúc đơn một mẫu. [Kiến trúc Base](architecture.md) · [Mô hình](../catalog/models.py) · [Tồn kho](../catalog/inventory.py) · [Đơn thuê](../catalog/rentals.py) · [Facade](../catalog/services.py)

| Dữ liệu đề xuất | Quan hệ và trách nhiệm |
| --- | --- |
| `Equipment`, `AssetUnit` | `Equipment` giữ mẫu, giá ngày và thông tin công khai. Một mẫu có nhiều `AssetUnit`, mỗi món có mã kho duy nhất, serial hãng tùy chọn và trạng thái kỹ thuật. Tồn vận hành được suy ra từ tài sản sau chuyển đổi. Chỉnh số lượng tồn bằng thao tác nhập hoặc ngừng sử dụng tài sản có lịch sử. |
| `Rental`, `RentalLine`, `RentalChangeRequest` | `Rental` giữ mã đơn, khách, thông tin liên hệ pilot và kỳ cam kết. Mỗi mẫu có một `RentalLine` lưu số lượng, đơn giá, cọc cam kết và thành tiền đã chốt. Yêu cầu đổi lịch ghi kỳ đề xuất, người xử lý và kết quả. Lịch và giá trước khi đổi nằm trong lịch sử nghiệp vụ. |
| `AssetCalendarBlock` | Một khóa lịch gắn một tài sản, khoảng ngày và nguồn là dòng thuê hoặc đợt bảo trì đã lên lịch. Trạng thái của khóa phân biệt đang cam kết và đã giải phóng. |
| `AssetHandover`, `AssetInspection`, `MaintenanceCase` | Lưu lúc giao, người giữ, lúc nhận thực tế hoặc quyết định xử lý mất, cùng checklist và kết quả kiểm tra. Phiếu bảo trì giữ lý do cách ly, diễn biến và kết quả cho thuê lại hoặc ngừng sử dụng. |
| `RentalLedgerEntry`, `RentalEvent` | Bút toán VND theo đơn, loại khoản, người thao tác, thời điểm và tham chiếu. Sự kiện lưu thay đổi lịch, thay máy, duyệt phí, xử lý ngoại lệ và liên kết đến bản ghi gốc. Mã thao tác duy nhất trong phạm vi đơn hỗ trợ gửi lại an toàn. |

`equipment.py` sở hữu mẫu và giá niêm yết. `inventory.py` sở hữu khoảng lịch, khả năng đáp ứng theo tài sản và kiểm kho thực tế. `rentals.py` điều phối đơn, giao nhận và gọi nghiệp vụ tồn. Chỉ tách module bảo trì hoặc tiền khi triển khai mốc tương ứng. Mỗi quy tắc có một nơi thực thi, cả API lẫn giao diện gọi qua service. [Hướng dẫn agent](../AGENTS.md)

### Lịch, kho thực tế và giao dịch

- **Giữ thiết bị suốt kỳ.** Giữ lịch cho thiết bị cụ thể ngay khi xác nhận. Khách thấy mẫu và số lượng. Tồn khách thấy là số tài sản có thể phục vụ toàn khoảng. Nếu hai máy cùng mẫu lần lượt bảo trì thứ Hai và thứ Ba, mỗi ngày còn một máy nhưng kỳ từ thứ Hai đến thứ Tư vẫn không có máy nào rảnh trọn kỳ. Gán máy sớm có thể tạo các khoảng trống rời rạc. Nhân viên có thể đổi máy có kiểm tra xung đột và lưu lịch sử.
- **Bàn giao theo tình trạng thực tế.** Một máy đang ở ngoài kho vẫn có thể có lịch hợp lệ cho lượt sau ngày dự kiến về. Kiểm lại khi bàn giao. Nếu đã đến ngày dự kiến về và máy vẫn chưa sẵn sàng, báo rủi ro cho đơn sắp giao, kể cả khi chưa tính phí trễ, và ngừng dùng máy đó cho đặt mới tới khi xác minh được khả dụng. Trả sớm giữ lịch gốc theo đề xuất bảo toàn R07. Ghi cách ly đột xuất ngay cả khi có đơn tương lai, rồi đưa các đơn đó vào hàng đợi đổi máy hoặc xử lý với khách.
- **Bảo toàn giao dịch.** Khóa các hàng `Equipment` theo ID tăng dần, rồi `Rental`, tài sản và hàng liên quan theo thứ tự nhất quán. Đọc lại trạng thái và tập SKU dưới khóa. Nếu tập SKU đã đổi, hủy giao dịch và lấy lại khóa theo thứ tự từ đầu. Thử dùng `daterange` với ràng buộc loại trừ chồng lấn lịch đang giữ theo tài sản, gồm cả lịch bảo trì đã lên lịch. Mỗi tài sản có tối đa một lượt giao đang mở. Kiểm quyền cài `btree_gist` trên PostgreSQL dự kiến dùng. Xác nhận đơn chạy lại kiểm tra trong giao dịch. [Django `ExclusionConstraint`](https://docs.djangoproject.com/en/5.2/ref/contrib/postgres/constraints/#exclusionconstraint) · [PostgreSQL range constraints](https://www.postgresql.org/docs/17/rangetypes.html#RANGETYPES-CONSTRAINT)

### Giá, giao nhận và đối soát

- **Hạn và số tiền cam kết.** Máy chủ tính tiền thuê theo số ngày × số lượng × đơn giá đã chốt từng dòng. Đề xuất giữ đơn giá khi duyệt đổi lịch hoặc gia hạn, tính lại số ngày và lưu thay đổi. Đổi lịch trước giao kiểm ngày nhận mới như lúc đặt. Gia hạn khi đang thuê giữ ngày nhận gốc và kiểm tổng kỳ sau gia hạn. Ngày trả trong đơn là hạn cam kết. Các lần giao và nhận lưu timestamp thực tế theo từng món để tính quá hạn theo chính sách đã duyệt.
- **Trạng thái vận hành.** Giữ vòng đời `CONFIRMED → PICKED_UP → RETURNED` hoặc `CONFIRMED → CANCELLED` cho trường hợp tương ứng. Đơn chỉ chuyển `RETURNED` khi đã nhận đủ. Nếu còn món chưa về, hiển thị đã trả một phần hoặc số món còn thiếu và giữ trạng thái đang thuê. Khi quản lý xử lý xong trường hợp mất, ghi kết quả đóng có ngoại lệ và giữ giờ nhận chỉ cho món đã về. Trạng thái đóng có ngoại lệ cần ràng buộc mới trong schema v2. Hoàn tất giao nhận, kiểm tra và đối soát là các mốc riêng.
- **Sổ thu và hoàn.** Cọc đang giữ bằng cọc thực nhận trừ cọc đã hoàn và cọc dùng bù. Số dư tiền thuê và phí bằng khoản phải trả đã duyệt trừ tiền thu ròng cho khoản đó và cọc đã dùng bù. Số dư âm là khoản cần hoàn cho khách. Nếu giao thất bại, hủy đơn hoặc kỳ mới giảm giá sau khi đã thu, quản lý duyệt xử lý khoản phải hoàn. Mỗi lần bù xuất hiện ở hai số dư từ cùng bút toán. Hoàn và khấu trừ giới hạn trong cọc còn giữ. Bút toán sai được đảo bằng bản ghi mới. Chỉ đóng quyết toán khi cả hai số dư về 0. Nhân viên ghi nhận thu hoặc hoàn sau khi xác minh giao dịch tại quầy.

## Nâng dữ liệu và chuyển đổi API

1. **Chọn nền triển khai.** Tag `v1.0.0-qa-baseline` trỏ đến `31ca8a0`. GitHub `main` tại thời điểm khảo sát là `b334418`, đã có sửa thông báo mật khẩu R08. Khi triển khai, kiểm lại SHA `main` và lấy bản có bản sửa từ nhánh sản phẩm riêng. Kết quả 32/32 trên baseline là bằng chứng của bản nền. [Bằng chứng Base](verification.md) · [PR sửa R08](https://github.com/haibadguy/camera-rental-qa-lab/pull/3)
2. **Bổ sung schema, chạy backfill lặp được.** Từ `0004` thêm bảng mới và tạo một `RentalLine` từ mỗi đơn cũ. Giữ nguyên ID, khách, mẫu, kỳ, số lượng, đơn giá, tổng, trạng thái, lý do hủy và dấu thời gian đã có. Giữ `NULL` khi lịch sử chưa có giờ giao, kết quả kiểm hoặc serial. Không suy ra bút toán từ giá thuê. Khóa mới chỉ bắt buộc sau khi đối chiếu xong. [Migrations Base](../catalog/migrations/) · [Kiểm thử nâng dữ liệu hiện tại](../catalog/tests.py)
3. **Đối soát tồn đang vận hành.** Nhập mã kho và serial đã kiểm kê. Đối chiếu từng món của đơn đang `PICKED_UP` trước. Sau đó gán tồn cho `CONFIRMED` theo kỳ còn hiệu lực, gồm đơn đã qua ngày nhận nhưng chưa qua kỳ. Đơn trả sớm còn kỳ giữ chỗ cần khóa lịch riêng cho phần kỳ còn lại mà không điền serial vào lịch sử đã diễn ra. Đối soát cả mẫu đã ngừng nhận đơn. Hoãn chuyển đổi nếu còn đơn hoạt động chưa khớp hoặc không bảo toàn được cam kết.
4. **Chuyển luồng ghi một lần.** Dùng `/api/v2/` cho đơn nhiều dòng, yêu cầu đổi lịch, giao nhận và sổ tiền. Đề xuất giữ API cũ để đọc đơn một dòng biểu diễn được bằng hợp đồng Base. Dừng thao tác ghi qua API cũ tại cutover sau khi xác định người dùng API, thông báo và được Hải duyệt. Web và API v2 vẫn cho khách đọc lịch sử và xử lý các đơn đang mở đã đối soát. Một nguồn ghi giúp áp dụng thống nhất các kiểm tra lịch, tình trạng và cọc. [Hợp đồng Base](architecture.md#hợp-đồng-api) · [Serializer hiện tại](../catalog/api.py)
5. **Tập dượt bằng PostgreSQL biệt lập.** Diễn tập migration và phục hồi từ backup. Khi chuyển đổi thật, dừng luồng ghi và chờ giao dịch đang chạy hoàn tất, rồi chụp bản sao làm điểm khôi phục. Đối chiếu số đơn, giá đã chốt, số lượng và lịch còn hiệu lực trước khi mở ghi v2. Sau khi có ghi mới nhiều dòng hoặc bút toán, phương án khôi phục phải giữ được các giao dịch đó. Chốt cách sửa tiến hoặc phục hồi và đối soát giao dịch trước cutover. [Thiết lập Verify](setup.md#kiểm-tra-và-dựng-dữ-liệu-sạch)

## Mốc đầu tiên và tiêu chí phát hành

Mốc đầu tiên là **V2-M1 · Một đơn nhiều thiết bị có lịch giữ đúng**. Sau khi Hải duyệt mô hình giữ thiết bị và phần dữ liệu cần bảo toàn, triển khai luồng chọn nhiều mẫu từ danh mục, xác nhận và hủy đơn, cùng màn lịch cho nhân viên. Dùng dữ liệu demo trên DB riêng, tạo một dòng cho mỗi đơn cũ và kiểm chứng đặt đồng thời. Đổi lịch và gia hạn ở V2-M2, tiền cọc ở V2-M3. [Roadmap](../ROADMAP.md#roadmap-v20)

Điều kiện phát hành v2.0 là cửa hàng pilot hoặc Hải có thể đi trọn một hành trình có thân máy và ống kính, cọc tại quầy, ghi nhận trả một phần, một món trả trễ có lỗi, bảo trì, khoản phát sinh và hoàn phần cọc còn lại. Nhân viên truy ra thiết bị và phụ kiện đã giao, giải thích đơn bị ảnh hưởng và đối soát từng bút toán. Ghi các ngoại lệ phát sinh trong pilot để quyết định phạm vi sau v2.

Trước phát hành, cần kiểm chứng nâng dữ liệu và phục hồi trên PostgreSQL, tuần tự hóa tranh chấp đặt/gia hạn/bảo trì và bàn giao bằng các kết nối độc lập, bảo toàn tồn khi một dòng thất bại, quyền khách/staff/quản lý, và tính nhất quán khi gửi lại thao tác thu/hoàn. Chạy Verify biệt lập, smoke web/API, duyệt giao diện khách và nhân viên trên desktop/mobile, ghi bằng chứng theo SHA và chạy CI ứng viên trước khi xin duyệt phát hành. [Quy trình Verify](setup.md#kiểm-tra-và-dựng-dữ-liệu-sạch) · [Quy tắc phát hành](../ROADMAP.md#release-gates)

## Quyết định của chủ sản phẩm

| Khi cần | Hải cần duyệt |
| --- | --- |
| Trước V2-M1 | Pilot một điểm nhận, một kỳ dùng chung, giữ thiết bị cụ thể nội bộ ngay khi xác nhận, cách đổi máy và tiêu chí đối soát dữ liệu Base. |
| Trước V2-M2 | Mốc xác định trả trễ và cách áp dụng cho đơn cũ, lịch khi trả sớm, quyền và đơn giá khi đổi/gia hạn, xử lý thiếu phụ kiện và mất máy, kênh liên hệ khách khi có ngoại lệ. Base báo quá hạn từ ngày sau ngày trả. |
| Trước V2-M3 | Mức cọc và chính sách thu tiền, phí trễ/hỏng, quyền và thời hạn hoàn/khấu trừ, xử lý khoản thu dư hoặc đã thu khi đơn chưa giao được. Đề xuất ban đầu là cọc VND theo mẫu, thu tại quầy và ghi phí theo chính sách đã duyệt, có căn cứ trên đơn. |
| Trước pilot | Đối tượng pilot, dữ liệu và giá được phép dùng, chính sách API cũ, kế hoạch dừng ghi, thời điểm phát hành và phương án khôi phục. |
