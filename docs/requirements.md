# Đặc tả MVP

Tên và mã thiết bị trong ví dụ là dữ liệu demo. Ngày nghiệp vụ tính theo `Asia/Ho_Chi_Minh`. Mỗi đơn chứa một mẫu thiết bị và số lượng nguyên dương. Các ngày ví dụ ở tương lai, trừ khi ghi rõ.

| Mã | Nghiệp vụ | Acceptance criteria |
| --- | --- | --- |
| R01 | Danh mục và tồn kho | Khách tìm theo tên hoặc mã, lọc theo máy ảnh hoặc ống kính và xem thông số, giá. Nhân viên thêm, sửa và ngừng nhận đơn mới cho thiết bị. Đơn cũ vẫn xử lý được. Tổng tồn mới phải đủ cho lượng giữ theo lịch và lượng đang ở ngoài kho. |
| R02 | Kiểm tra ngày và số lượng | Ngày nhận từ hôm nay trở đi. Kỳ thuê từ 1 đến 30 ngày. Số lượng là số nguyên dương. Dữ liệu sai bị từ chối trước khi tạo đơn. |
| R03 | Tính giá | Tổng tiền VND = số ngày thuê × số lượng × đơn giá ngày. Ngày trả là mốc kết thúc. Đơn ngày 10–12, số lượng 2, giá 300.000 ₫/ngày có tổng 1.200.000 ₫. Đơn giá và tổng tiền được lưu lúc đặt. |
| R04 | Đặt thuê | Khách đăng nhập tạo đơn `CONFIRMED` khi đủ tồn cho toàn bộ kỳ thuê. Ứng dụng trả mã đơn và ghi đúng số lượng. Với đơn bị từ chối, số đơn và lượng đã giữ giữ nguyên. |
| R05 | Tồn kho theo lịch và đặt đồng thời | Tồn trống cho kỳ thuê là tổng tồn trừ lượng đang giữ cao nhất trong một ngày thuộc kỳ đó. Đơn `CONFIRMED`, `PICKED_UP` và `RETURNED` giữ lịch từ ngày nhận đến trước ngày trả theo lịch. Nếu còn 1 sản phẩm và hai khách đồng thời đặt 1 cho cùng kỳ, đúng một đơn được tạo. |
| R06 | Xem và hủy | Khách xem và hủy đơn của mình. Khách hủy đơn `CONFIRMED` trước ngày nhận. Nhân viên có thể hủy đơn `CONFIRMED` với lý do `NO_SHOW` từ ngày sau ngày nhận. Đơn `CANCELLED` giải phóng lịch. Thao tác lặp hoặc sai quyền bị từ chối. |
| R07 | Bàn giao và ghi nhận trả | Nhân viên bàn giao đơn `CONFIRMED` từ ngày nhận đến trước ngày trả nếu còn đủ số lượng thực tế, lưu thời điểm bàn giao và chuyển sang `PICKED_UP`. Nhân viên ghi nhận trả đơn `PICKED_UP` bất kỳ lúc nào, lưu thời điểm trả và chuyển sang `RETURNED`. Trả sớm giữ nguyên lịch cam kết. Đơn chưa trả được cảnh báo từ ngày tiếp theo ngày trả. Thao tác lặp hoặc sai trạng thái bị từ chối. |
| R08 | Tài khoản khách hàng | Khách đăng ký bằng tên đăng nhập và mật khẩu, sau đó đăng nhập để đặt thuê. Tên trùng và mật khẩu không hợp lệ bị từ chối. Tài khoản tự đăng ký chỉ có quyền khách. |

## Ví dụ biên cho QA

- Tồn 2, đơn đã giữ 1 chiếc ngày 10–12. Khách đặt thêm 1 chiếc ngày 11–13 được chấp nhận. Nếu khách yêu cầu 2 chiếc ngay từ trạng thái ban đầu, ứng dụng từ chối và giữ nguyên số đơn.
- Tồn 1, đơn đã giữ 1 chiếc ngày 10–12. Ngày 11–13 hết chỗ. Ngày 12–14 còn chỗ vì ngày 12 là ngày kết thúc của đơn trước.
- Tồn 2, có hai đơn mỗi đơn 1 chiếc, một đơn ngày 10–11 và một đơn ngày 11–12. Kỳ 10–12 còn 1 chiếc vì hai đơn đang giữ vào hai ngày khác nhau.
- Một đơn sắp đến ngày nhận được hủy. Sau khi hủy, kiểm tra số lượng tương ứng xuất hiện lại trong kết quả tra cứu cùng kỳ.

## Vòng đời đơn

| Từ trạng thái | Thao tác | Trạng thái sau |
| --- | --- | --- |
| Đơn mới | Khách đặt thành công | `CONFIRMED` |
| `CONFIRMED` | Khách hủy đúng hạn | `CANCELLED` |
| `CONFIRMED` | Nhân viên xác nhận khách không đến nhận từ ngày sau ngày nhận | `CANCELLED` với `NO_SHOW` |
| `CONFIRMED` | Nhân viên bàn giao đúng kỳ và đủ thiết bị trong kho | `PICKED_UP` |
| `PICKED_UP` | Nhân viên xác nhận đã nhận lại thiết bị | `RETURNED` |

Số lượng thực tế còn trong kho bằng tổng tồn trừ tất cả thiết bị thuộc đơn `PICKED_UP`, kể cả đơn đã qua ngày trả. Đặt thuê theo lịch cam kết. Khi bàn giao, kiểm tra lại tồn thực tế trong cùng giao dịch đổi trạng thái. Ví dụ nếu máy cuối cùng chưa được trả, đơn tiếp theo vẫn có thể đã được xác nhận theo lịch nhưng chỉ được bàn giao sau khi máy thực tế về kho.
