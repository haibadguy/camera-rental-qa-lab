# Trạng thái xác minh Camera Rental Base v1.0

**Bản Base đang chạy local ở cổng 8000 · Chờ GitHub Actions và duyệt Base**

## Luồng từ đặt đến nhận máy ngày 22/11/2026

Phạm vi R01/R02/R04/R06/R07. Đổi loại thiết bị trong danh mục giữ từ khóa và ngày vừa nhập. Trang thiết bị, form đặt và đơn đang hiệu lực hiển thị cấu hình nhận–trả. Màn nhân viên có mục nhận hôm nay, trả hôm nay và quá hạn.

| Kiểm tra | Bằng chứng |
| --- | --- |
| Compose sạch | Pass, exit 0 với `.\scripts\dev.ps1 -Action Verify -Port 18031`, project `camera-rental-qa-lab-46880132` và volume mới. Django check, kiểm tra migration drift, 31/31 test PostgreSQL và HTTP smoke đều đạt. Hai test mới kiểm tra nội dung nhận–trả, ẩn nội dung với đơn đã hủy, phân nhóm đúng ngày và quyền nhân viên. |
| Trình duyệt | Pass khi chạy `node "$env:TEMP\camera-rental-browser-5fe17aed\handoff-review.cjs"` ở 1440 × 1000, 390 × 844 và 320 × 780. Nhập từ khóa `LEN-001` và kỳ 27–29/11/2026 rồi đổi loại trước khi bấm Áp dụng. Đơn giữ ngày khi đăng ký/đăng nhập, tạm tính 600.000 ₫, đặt và hủy được. Đơn `demo-a` xuất hiện ở nhóm trả hôm nay, nhóm quá hạn hiển thị trạng thái trống đúng dữ liệu. |
| Cấu hình nhận–trả | Pass với địa chỉ, giờ, điện thoại và URL HTTPS kiểm thử chỉ trên Compose biệt lập. Chrome thấy đúng nội dung trên ba màn, liên kết gọi có số đã chuẩn hóa. Test khi cấu hình trống xác nhận ứng dụng báo thông tin chưa được công bố. |
| Bản chạy mặc định | Pass. `Start` cập nhật cổng 8000 và trang chi tiết có khối nhận–trả, HTTP 200. Bản mặc định không chứa dữ liệu cửa hàng kiểm thử. Dữ liệu hai bảng đơn thuê và thiết bị khớp toàn bộ trước/sau cập nhật. Project thử đã dừng và volume được giữ. |

Thông tin cửa hàng thật thuộc mốc vận hành. Base local/demo cho phép cấu hình trống hoặc nội dung mẫu theo [kế hoạch đã duyệt](../PROJECT_PLAN.md). GitHub Actions ở lượt này là `Not Run`.

## Hoàn tất bản local ngày 22/11/2026

Phạm vi R01–R08. Danh mục có lối lọc theo loại, kỳ thuê được giữ khi đổi loại, khách có thể vào thẳng form đặt từ kết quả còn hàng. Form hiển thị phép tính tạm tính bên cạnh tổng. Django trả `X-Frame-Options: DENY` cho trang web.

| Kiểm tra | Kết quả trên working tree `refactor/modular-structure`, HEAD `0d81fac` |
| --- | --- |
| Compose sạch | Pass, exit 0. `.\scripts\dev.ps1 -Action Verify -Port 18029` dùng project `camera-rental-qa-lab-e0e0cbe9` với volume mới. PostgreSQL 17.11 và Django 5.2.19. Migration `catalog.0001`–`0004`, seed ba thiết bị và tài khoản demo, Django check, kiểm tra migration drift, 29/29 test và HTTP smoke đều đạt. Hai bài kiểm tra PostgreSQL đồng thời có trong lượt chạy. |
| Khách và nhân viên | Pass qua Chrome 1440 × 1000, 390 × 844 và 320 × 780. Chạy `node "$env:TEMP\camera-rental-browser-5fe17aed\release-review.cjs"` với `LEN-001`, kỳ 27–29/11/2026. Đổi loại, lọc ngày, vào form qua lối đặt nhanh, đăng ký, kiểm tra tổng 600.000 ₫ cho hai thiết bị, đặt và hủy. Kỳ hết hàng ẩn nút đặt nhanh. Đã mở danh mục, chi tiết, đơn khách, kho, sửa thiết bị và danh sách đơn nhân viên. Axe không báo vi phạm trong các quy tắc đã quét. |
| Vòng đời qua HTTP | Pass trên volume biệt lập. Thiết bị `QA-E954B0ED` kỳ 22–24/11/2026 đi qua thêm, sửa giá, từ chối giảm tồn, ngừng nhận, bàn giao rồi trả. Đơn cũ giữ giá 1.200.000 ₫. Đơn `CAM-002` quá ngày nhận được xử lý `NO_SHOW`, giải phóng lịch và từ chối thao tác lặp. |
| Quyền và an toàn local | Pass với Django client bật kiểm tra CSRF. Thiếu xác thực API trả 401, khách vào kho bị 403, đơn của người khác trả 404, yêu cầu thiếu CSRF bị 403 và GET đăng xuất bị 405. `X-Frame-Options` và `nosniff` có trong phản hồi. `.env` được Git bỏ qua, Compose chỉ xuất web ra loopback. |
| Bản chạy mặc định | Pass. `.\scripts\dev.ps1 -Action Start` cập nhật bản cổng 8000, trang chủ trả HTTP 200. Hash CSS, JS và ảnh mới khớp source, dữ liệu trong cả hai bảng đơn và thiết bị khớp trước/sau cập nhật. Chrome kiểm tra lại điều hướng và đăng nhập khách/nhân viên ở 390 × 844 và 1440 × 1000. Project xác minh đã dừng và volume được giữ. |

Lượt đầu bị `Blocked` vì Docker Engine chưa sẵn sàng. `docker desktop start --timeout 60` khôi phục kết nối, sau đó chạy lại toàn bộ Verify trên project mới.

| Gate | Trạng thái |
| --- | --- |
| G0 | Có bản sao khôi phục local đã kiểm tra hash. Checkpoint Git cho diff hiện tại chờ Hải review. |
| G1 | Đạt trên working tree theo các test PostgreSQL và HTTP ở trên. |
| G2 | Luồng khách và nhân viên đã kiểm chứng local. Chờ Hải xem trải nghiệm trên cổng mặc định. |
| G3 | Kiểm chứng local đạt. GitHub Actions cho đúng commit ứng viên ở trạng thái `Not Run`, chờ Hải duyệt push. |
| G4 | Đang chờ commit ứng viên, bàn giao độc lập và phê duyệt đóng băng. |

## Lượt xác minh giao diện trước đó

Phạm vi giao diện bao gồm danh mục và kho (R01), chọn kỳ và tạm tính (R02–R05), đơn khách và đơn nhân viên (R06/R07) và xác thực (R08). Trang danh mục dùng ảnh minh họa WebP và phông tiếng Việt lưu trong ứng dụng. Giao diện đặt thuê hiển thị giá tạm tính trước nút xác nhận.

| Kiểm tra | Bằng chứng |
| --- | --- |
| Compose sạch | Pass. `.\scripts\dev.ps1 -Action Verify -Port 18028` dùng project và volume mới `camera-rental-qa-lab-a8b9ea7e`. Web và PostgreSQL healthy, Django check và migration drift đạt, 28/28 test đạt, HTTP smoke đạt. |
| Trình duyệt | Pass với Chrome tại 1440 × 1000, 390 × 844 và 320 × 780. Chạy `node "$env:TEMP\camera-rental-browser-5fe17aed\redesign-final.cjs"` trên cổng kiểm thử. Tìm `LEN-001`, chọn kỳ 27–29/11/2026, giữ ngày qua đăng ký, đổi số lượng từ 1 lên 2 và kiểm tra tạm tính 600.000 ₫, đặt rồi hủy đơn. Đăng nhập nhân viên, mở kho, sửa thiết bị và danh sách đơn. |
| Hiển thị | Đã xem ảnh chụp danh mục, chi tiết, đăng ký, đặt thuê và màn nhân viên. Các màn đã chạy không tràn ngang, lỗi JavaScript hoặc lỗi tải ảnh/phông. Axe không phát hiện vi phạm trong các quy tắc WCAG A/AA đã quét. |
| Bản chạy mặc định | Pass. `.\scripts\dev.ps1 -Action Start` cập nhật web ở cổng 8000. CSS, bốn ảnh và phông tiếng Việt phục vụ với hash khớp mã local. Đăng nhập khách và nhân viên, xem danh mục, đơn và kho qua Chrome ở desktop và mobile. Volume mặc định vẫn có 1 đơn và 3 thiết bị sau cập nhật. Các project kiểm thử giao diện được dừng và giữ volume. |

## Xác minh nghiệp vụ trước khi cập nhật giao diện

Phạm vi là R01–R08 trong [đặc tả](requirements.md). Bản này giữ bộ lọc tên hoặc mã và loại thiết bị khi ngày nhập sai (R01/R02), đồng thời giữ kỳ thuê qua đăng ký và đăng nhập (R02/R04/R08). Sáu test bổ sung kiểm tra các luồng này, chuyển hướng về ứng dụng, quyền xem/hủy đơn (R06) và tính nhất quán khi từ chối đặt thuê hoặc giảm tồn (R01/R04/R05).

| Kiểm tra | Bằng chứng |
| --- | --- |
| Compose sạch | Pass. `.\scripts\dev.ps1 -Action Verify -Port 18024` tạo project `camera-rental-qa-lab-84f82660` và volume mới `camera-rental-qa-lab-84f82660_postgres_data`. PostgreSQL 17.11 và web healthy. Django 5.2.19 áp dụng migration `catalog.0001`–`0004`, seed 3 thiết bị và tài khoản demo. Trang chủ trả HTTP 200. |
| Django và PostgreSQL | Pass. `manage.py check` thành công, `manage.py makemigrations --check --dry-run` không phát hiện migration thiếu. `manage.py test` đạt 28/28, không skip. Hai test đồng thời tiếp tục xác nhận chỉ một yêu cầu thành công khi đặt món cuối hoặc bàn giao món cuối còn trong kho. |
| HTTP smoke | Pass. `python scripts/smoke.py` chạy qua HTTP với khách tạo mới, nhân viên `demo-staff` và ống kính `LEN-001` cho hai kỳ 22–23/11 và 23–24/11/2026. Luồng đăng ký, đăng nhập, phân quyền, danh mục, tra lịch, đặt, bàn giao, trả sớm và hủy đều đạt. |
| Coverage Python | **92,90%** theo Coverage.py 7.17.2, tính cả dòng lệnh và nhánh trong `catalog` và `config`, trừ test và migrations. Đo trên PostgreSQL của project xác minh và đạt ngưỡng trên 90%. |
| Trình duyệt | Pass với Chrome headless 157, ở 1440 × 1000 và 390 × 844. Script kỹ thuật chạy bằng `node "$env:TEMP\camera-rental-browser-5fe17aed\verify.cjs"`. Hai lượt dùng `LEN-001` kỳ 24–26/11/2026, xác nhận giữ ngày qua hai lối đăng ký, tạm tính từ 300.000 ₫ lên 600.000 ₫ khi tăng số lượng lên 2, đặt và hủy đơn, truy cập kho và danh sách đơn nhân viên. Không có tràn ngang, lỗi JavaScript hoặc HTTP 5xx trong các luồng đã chạy. |
| Kiểm tra mã | Pass với `node --check catalog/static/catalog/site.js`, `git diff --check` và `ruff check catalog/tests.py catalog/views.py`. Lượt Ruff mặc định trên toàn bộ `catalog`, `config` và smoke còn 20 mục về khai báo thuộc tính lớp Django và sắp xếp import ở các tệp khác. |

Hai lệnh dưới đây chạy trong container web với Coverage.py cài riêng cho lượt xác minh.

```sh
python -m coverage run --branch --source=catalog,config manage.py test
python -m coverage report --precision=2 --omit='*/tests.py,*/migrations/*' --fail-under=90.01
```

- **Not Run · GitHub Actions.** Workflow đã được chạy theo các bước tương đương trên Compose local. Kết quả trên runner GitHub chờ Hải duyệt push.
- **Not Run · Manual QA Portfolio.** Giai đoạn này bắt đầu sau khi Hải duyệt và chốt bản Base.

Project cổng 18024 được giữ chạy để xem bản demo. Hai project xác minh trong lượt này ở cổng 18022 và 18023 được dừng, volume của cả hai vẫn tồn tại.

## Kiểm tra bản chạy ở cổng mặc định

Ngày 22/11/2026, khôi phục `.env` local từ cấu hình container mặc định đã dừng để tiếp tục dùng volume `camera-rental-qa-lab_postgres_data`. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action Start` thành công. Web và PostgreSQL healthy, `GET /` trả HTTP 200, danh mục API trả `CAM-001`, `CAM-002` và `LEN-001`. `python manage.py check` và `python manage.py migrate --check` đều đạt. Chrome headless xác nhận đăng nhập khách và nhân viên, xem danh mục, chi tiết thiết bị, đơn khách, kho và danh sách đơn nhân viên ở 390 × 844 và 1440 × 1000. Không tạo đơn kiểm thử trên volume mặc định.

Kiểm chứng nghiệp vụ dùng `.\scripts\dev.ps1 -Action Verify -Port 18025` trên project `camera-rental-qa-lab-f0aeb4a7` với volume mới. Đối chiếu SHA-256 của tám file nghiệp vụ và giao diện giữa hai container web cho kết quả khớp. Migration, seed, 28/28 test PostgreSQL và HTTP smoke đều đạt. Một lượt bổ sung qua HTTP dùng tài khoản thử và thiết bị `QA-639308C1`, kỳ 22–24/11/2026. Nhân viên thêm, sửa giá, từ chối giảm tồn dưới lượng giữ và ngừng nhận đơn. Đơn đã đặt vẫn bàn giao và trả được với giá gốc 1.200.000 ₫ cho hai thiết bị trong hai ngày. Một đơn `CAM-002` được tạo trong dữ liệu kiểm thử với ngày nhận 21/11 và trả 23/11. Nhân viên xác nhận `NO_SHOW`, tồn theo lịch trở về 1, và lần xác nhận lặp nhận HTTP 409. Chỉ project xác minh bị dừng sau kiểm tra và volume được giữ.

## Kết quả Base trước refactor

Các kết quả dưới đây ghi nhận bản làm việc Windows ngày 21/11/2026 trước refactor, dựa trên `0e9139e`.

| Mốc | Kết quả trên bản làm việc |
| --- | --- |
| M1 | Đã xác minh đăng ký, vòng đời đơn, kỳ thuê 1–30 ngày, `NO_SHOW` sau ngày nhận, tồn thực tế khi bàn giao và bảo toàn lịch khi trả sớm. Hai bài kiểm tra đồng thời trên PostgreSQL đạt. |
| M2 | Hoàn tất tra lịch tại trang chi tiết, giữ ngày sang form đặt, tiền tạm tính theo số lượng và định dạng VND dùng chung trên web. Có script dựng môi trường sạch, workflow và tài liệu bàn giao. Danh mục dùng minh họa CSS theo loại thiết bị. |
| M3 | Build, migration, seed, 22 test Django, HTTP smoke và kiểm tra giao diện đều đạt local. Đã rà phân quyền, thứ tự khóa, dữ liệu chuyển trạng thái và đường đi từ web/API tới service. GitHub Actions chưa chạy trên GitHub. |

## Kết quả đã quan sát

| Kiểm tra | Kết quả |
| --- | --- |
| `.\scripts\dev.ps1 -Action Verify -Port 18012` | Pass với Docker Desktop trên Windows. Project `camera-rental-qa-lab-1a33c12d` dùng volume mới và PostgreSQL 17.11. Compose config hợp lệ, image web build thành công, `db` và `web` healthy. |
| Migration, seed và khởi động web | Pass. Log ghi migration `catalog.0001`–`0004` đã áp dụng, seed 3 mẫu thiết bị và tài khoản demo, `GET /` trả 200. |
| `manage.py check`, `manage.py makemigrations --check --dry-run` | Pass. Không có lỗi Django hoặc thay đổi schema chưa có migration. |
| `manage.py test` | 22/22 pass, không skip. Hai kết nối đặt món cuối nhận `201` và `409` với đúng một đơn mới. Hai bàn giao đồng thời khi còn một món thực tế nhận `200` và `409`. Các bài khác kiểm tra hủy, `NO_SHOW`, trả sớm, trả muộn, quyền, tồn và dữ liệu demo. |
| `python scripts/smoke.py` | Pass qua HTTP trên Compose. Dữ liệu gồm khách mới, nhân viên demo và ống kính `LEN-001`. Đã kiểm tra đăng ký, đăng nhập, quyền, danh mục, tra lịch, đặt, bàn giao, trả sớm và hủy qua web/API. |
| Chrome headless, 1440 × 1000 và 390 × 844 | Pass. Đã xem ảnh danh mục, chi tiết, đặt thuê, kho và danh sách đơn nhân viên ở cả hai kích thước. Không có tràn ngang hoặc exception JavaScript. Kỳ 22–24/11 với `LEN-001` hiển thị còn 2 thiết bị. Thay số lượng từ 1 lên 2 cập nhật tiền tạm tính từ 300.000 ₫ lên 600.000 ₫. |
| `node --check catalog/static/catalog/site.js`, `git diff --check` | Pass. |
| GitHub Actions | Not Run. `.github/workflows/base.yml` đã có ở local và dùng cùng các lệnh Compose/Django/smoke đã đạt. `origin/main` chưa chứa workflow nên chưa có kết quả từ runner GitHub. |

Chạy Docker trong sandbox bị từ chối quyền truy cập Engine. Chạy có quyền Docker Desktop xử lý được vấn đề này. Cổng 8010 đang được sử dụng. Các lượt 18010 và 18011 phát hiện hai test định dạng tiền thất bại. Bản chạy 18012 dùng bộ định dạng VND riêng và đã chạy lại toàn bộ 22 test. Ba project xác minh trước đó được dừng và các volume được giữ.

## Tiếp tục xác minh

Lượt xác minh Base trước refactor dùng cổng 18012. Để lặp lại, dùng `Verify` với một cổng trống theo [hướng dẫn](setup.md). GitHub Actions cần một lần chạy đạt trên nhánh chứa workflow sau khi Hải duyệt push.

## Kiểm chứng refactor

Nhánh `refactor/modular-structure` bắt đầu từ checkpoint `0d81fac`. Kiểm tra so sánh dùng mã trong checkpoint và mã trên nhánh refactor.

| Kiểm tra | Kết quả |
| --- | --- |
| Mã và hợp đồng | Pass. AST của 27 file Python hợp lệ. Kiểm tra import nội bộ không thấy vòng phụ thuộc. Chữ ký hàm service, 22 phương thức test, models, migrations, URL, seed, Compose và workflow CI đối chiếu khớp checkpoint. |
| Tồn và ngày thuê | Pass trong bộ nhớ. 216 ca ngày thuê và 182.700 phép tính tồn theo kỳ trùng kết quả checkpoint. |
| Vòng đời đơn | Pass với phụ thuộc mô phỏng. 1.280 ca so sánh kết quả chuyển trạng thái, mã và thông báo lỗi, trường được ghi và cờ hiển thị nút. Hàm khóa đơn và truy vấn theo chủ đơn giữ nguyên. |
| Giá tạm tính | Pass. `node --check catalog/static/catalog/site.js` và 432 ca so sánh JS bằng form mô phỏng. JS nhận giới hạn kỳ thuê từ form. |
| Compose sạch, 21/11/2026 | Pass. `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Action Verify -Port 18020` thoát với mã 0. Project `camera-rental-qa-lab-3163c59c` build image web và tạo volume `camera-rental-qa-lab-3163c59c_postgres_data`. `db` và `web` healthy sau khi web chạy migration và seed demo. `GET /` qua cổng 18020 trả 200. |
| Django system check và migration drift | Pass. `python manage.py check` không báo lỗi. `python manage.py makemigrations --check --dry-run` không phát hiện thay đổi. |
| Test Django trên PostgreSQL | Pass. `python manage.py test` đạt 22/22 trong 2,275 giây, gồm đặt món cuối và bàn giao đồng thời. Django tạo và dọn cơ sở dữ liệu test trong project biệt lập. |
| HTTP smoke | Pass. `python scripts/smoke.py` dùng khách tạo mới, nhân viên `demo-staff` và thiết bị `LEN-001`, đặt một chiếc trong từng kỳ 21–22/11 và 22–23/11/2026. Đã kiểm tra đăng ký, đăng nhập, phân quyền, danh mục, tồn theo lịch, đặt, bàn giao, trả sớm và hủy qua web/API. |
| Checkpoint `0d81fac` trên PostgreSQL sạch | Pass. Xuất mã bằng `git archive` và chạy project `camera-rental-checkpoint-f20e5caf` trên cổng 18021 với volume mới. Build ban đầu bị timeout khi tải Django. Lượt chạy đạt dùng thư viện đã cài trong image refactor, với mã checkpoint được nạp từ `/checkpoint` và kiểm tra bằng SHA-256. Migration 0001–0004, seed 3 thiết bị và tài khoản demo, Django check, kiểm tra migration drift, 22/22 test gồm hai test đồng thời và HTTP smoke đều đạt. |
| Đối chiếu trước và sau | Pass. Hai bản cùng dùng PostgreSQL 17.11 và Django 5.2.19, cùng đạt 22/22 test PostgreSQL. Đã chạy lại bản refactor ở chế độ verbose sau khi đối chiếu SHA-256 của 12 file `catalog/` thay đổi với image đang phục vụ. Mã phản hồi và nội dung khớp ở 7 ca GET, gồm danh mục, chi tiết, tra lịch `LEN-001` kỳ 24–26/11/2026, ngày sai và danh sách đơn khi chưa xác thực. |
| GitHub Actions | Not Run cho refactor. |

Lượt đầu ngày 21/11 bị chặn vì chưa có endpoint `dockerDesktopLinuxEngine`. `docker desktop start --timeout 60` chạy ngoài sandbox đã khởi động Docker Desktop, sau đó lượt Verify tiếp theo đạt. Project Verify tiếp tục chạy trên cổng 18020. Các volume có sẵn được giữ nguyên.

Project checkpoint đã được dừng bằng `docker compose stop`. Đã xác nhận volume checkpoint và volume refactor vẫn tồn tại và trang chủ ở cổng 18020 tiếp tục trả HTTP 200.
