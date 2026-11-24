# Roadmap Camera Rental Management System

Đích phát hành là một **Medium Business Application** cho một cửa hàng, dùng được từ đặt thuê đến quyết toán và báo cáo. Nền tảng v1.0 đã đóng băng ngày 22/11/2026. V2-M4 và phần hoàn thiện kỹ thuật V2-M5 đã tích hợp vào `main`. [Phạm vi sản phẩm](docs/v2-product-design.md) · [Bằng chứng kiểm chứng](docs/verification.md)

## Roadmap V3

Giữ một cửa hàng, một kho, một quỹ dùng chung. Hoàn thiện kỹ thuật và đo tải bằng dữ liệu tổng hợp trong khi chờ pilot thật. [Hàng đợi V3](PROJECT_PLAN.md#camera-rental-v3--một-cửa-hàng-lớn)

- **G1 · Nền:** đánh giá fork theo giấy phép miễn phí, tương thích nghiệp vụ và chi phí chuyển đổi. Chốt Django/PostgreSQL khi ứng viên cần thay lõi nghiệp vụ.
- **G2 · Sản phẩm:** tạo đơn hộ, quét chuẩn bị/nhận trả theo lô, ảnh sự cố 90 ngày, đối soát tiền cuối ca và truy vết theo đơn.
- **G3 · Tải và an toàn:** 100 người dùng đồng thời trong 30 phút, p95 lần lượt 300 ms tra lịch, 600 ms vận hành, 700 ms đặt, 2 giây báo cáo tổng quan. 5xx dưới 0,1%, không giữ trùng hoặc ghi tiền lặp. Mục tiêu phục hồi 60 phút và mất dữ liệu tối đa 15 phút.
- **G4 · Pilot và phát hành:** giảm 50% thời gian thao tác kịch bản 10 món so với V2. Pilot tối thiểu 5 ngày, 20 đơn, 5 ca. Kiểm luồng khách, nhân viên và quản lý, nâng/khôi phục, CI đúng SHA và Hải duyệt riêng.

## Roadmap v2.0

[Công việc hiện tại](PROJECT_PLAN.md) · [Quyết định trước V2-M4](docs/v2-product-design.md#quyết-định-trước-v2-m4)

| Mốc | Phụ thuộc | Tiêu chí nghiệm thu |
| --- | --- | --- |
| V2-M1 · Tài sản và đơn nhiều dòng | Base v1.0 và phạm vi M1 đã duyệt. | **Đã tích hợp.** Có mã kho, đặt và hủy nguyên đơn, giữ suốt kỳ, đổi cùng mẫu có lịch sử và nâng dữ liệu v1. [PR #5](https://github.com/haibadguy/camera-rental-qa-lab/pull/5) |
| V2-M2 · Rental Operations | V2-M1 trên `main`. Hải đã duyệt chính sách M2 ngày 23/11/2026. | **Đã tích hợp.** Đổi và gia hạn qua kiểm lịch, giao nhận từng món, kiểm phụ kiện, cách ly, bảo trì và quyền theo vai trò. Đã kiểm chứng tranh chấp tồn. [PR #6](https://github.com/haibadguy/camera-rental-qa-lab/pull/6) |
| V2-M3 · Pricing & Finance | V2-M2 cung cấp kỳ cam kết và hồ sơ giao nhận, sự cố. Hải duyệt ngày 24/11/2026. [Chính sách](docs/v2-product-design.md#quyết-định-trước-v2-m3) | **Đã tích hợp.** Giá và cọc chốt theo dòng, thu/hoàn, duyệt phí, khấu trừ và điều chỉnh có truy vết. Đã kiểm chứng chống ghi trùng. [PR #7](https://github.com/haibadguy/camera-rental-qa-lab/pull/7) |
| V2-M4 · Management & Reporting | V2-M2 cung cấp dữ liệu kho và vận hành. V2-M3 cung cấp bút toán. Hải duyệt chính sách ngày 24/11/2026. | Màn quản lý lấy tiền thuê và phí thực thu ròng, đơn hàng, thiết bị đang thuê và tỷ lệ sử dụng từ dữ liệu theo kỳ. Tổng đối chiếu được với bản ghi gốc. Danh mục lọc được theo thương hiệu. Kiểm kê phân biệt trong kho, đang thuê và cách ly, ghi chênh lệch cùng người xử lý. Nhật ký truy được thay đổi vận hành và tiền đã duyệt. |
| V2-M5 · Product Polish & Release | V2-M2–M4 đạt nghiệm thu, Hải duyệt pilot và chuyển đổi dữ liệu/API. | Chạy trọn luồng tại một điểm nhận–trả từ đặt nhiều món đến quyết toán và báo cáo, kể cả trả một phần và sự cố. Hoàn thiện UI responsive cho khách, nhân viên và quản lý, kiểm quyền backend, diễn tập nâng và khôi phục dữ liệu, chạy PostgreSQL và smoke, CI xanh đúng SHA, bàn giao từ checkout sạch và Hải duyệt phát hành. |

V2-M4 và phần hoàn thiện kỹ thuật V2-M5 đã vào `main` tại `1add478` qua một PR. Phần còn mở là phê duyệt pilot, nghiệm thu tại cửa hàng và phê duyệt phát hành. [PR #8](https://github.com/haibadguy/camera-rental-qa-lab/pull/8) · [Công việc hiện tại](PROJECT_PLAN.md#công-việc-hiện-tại)

## Base v1.0 milestones

The following milestones record the completed technical foundation. [Approved Base requirements](docs/requirements.md) · [Verification evidence](docs/verification.md)

### Base scope
- Existing repository: `haibadguy/camera-rental-qa-lab`; Windows local working directory commonly `D:\camera-rental-qa-lab`.
- Keep Django, Django Templates, Django REST Framework, PostgreSQL and Docker Compose. Do not introduce React or microservices.
- Preserve the existing `catalog` Django app label and applied migrations. Follow the agreed equipment, inventory and rentals module boundaries in [docs/architecture.md](docs/architecture.md). Any change to the stack or a business rule requires Hải's approval.
- Check the current branch and task diff before editing. [PROJECT_PLAN.md](PROJECT_PLAN.md) contains the approved execution queue and the conditions for reopening it.
- Scope follows [R01–R08](docs/requirements.md). It covers customer registration/login, equipment list/search/details, date/quantity availability, pricing, booking/history/cancellation, staff equipment/stock/pricing administration, pickup, return, no-show, overdue awareness and web/API consistency.
- No live payments, recommendations, chatbot, email/SMS service, loyalty or analytics dashboard.

### Base quality standards

| Standard | Required outcome |
| --- | --- |
| Product completeness | Approved customer and staff journeys work end to end. |
| No generated filler | Every control, asset, code path and document serves a purpose. |
| Architecture | Modules have clear responsibilities and dependencies. |
| Maintainability | A change stays within the modules that own the behavior. |
| UI/UX | Responsive screens use coherent controls and provide clear feedback. |
| Correctness | Dates, prices, inventory and rental transitions follow R01–R08. |
| Data integrity | Transactions protect stock and preserve rental history. |
| Security | Backend authorization, input validation and secret handling are verified. |
| Reproducibility | A new checkout can configure, build, migrate, seed and run on Docker. |
| Automated quality | Critical tests and GitHub CI execute successfully on the candidate. |
| Documentation | Instructions are concise and describe the checked implementation. |
| Handoff | A new contributor can reproduce the setup and locate domain rules using the repository. |

### S0 — Protect and measure current state
**Tasks**: Keep one writer per worktree. Inspect the branch, tracked and untracked files, and `.gitignore`. Check for exposed credentials without printing values. Record HEAD and test baseline, then take a safe local checkpoint in the workflow approved by Hải. Continue from the existing refactor.
**Evidence**: Git status, local checkpoint SHA, inventory of files, last known test outputs, known blockers.
**Exit**: Recoverable checkpoint exists. No unexplained destructive operations. If Git is blocked, resolve permissions instead of proceeding with broad refactor.

### M1 — Architecture stabilization and domain correctness (2–4 working days target)
1. Inspect dependencies across catalog/models, services, views, api and templates. Identify actual duplication and coupling.
2. Keep Django app label/migrations stable. Refactor only demonstrated pain points, with small commits and tests; inventory first if it has duplicated physical/scheduled availability.
3. Keep web and DRF on shared domain services. Keep domain logic outside templates/views and avoid circular imports.
4. Verify complete rental lifecycle, date/price rules, permissions and transactional stock behavior. Cover idempotence/invalid transitions, no-show, early/late return.
5. Run migrations check and PostgreSQL integration/concurrency tests; if blocked, log exact failing command and environment.
**Exit**: Business behavior matches approved requirements, module responsibilities documented, tests pass with evidence, no new migration/data regression.

### M2 — Product experience and operational completeness (3–5 working days target)
1. Review all seven customer/staff screens as coherent journeys: catalog, product detail, auth, booking, customer orders, staff equipment, staff orders/actions.
2. Harmonize typography/spacing/controls/mobile navigation; clear validation, loading/submitting, empty, success, error and authorization states.
3. No dead buttons, dummy success flows, broken routes, Lorem Ipsum or unlicensed photos. Seed realistic local data with stable demo accounts; do not claim fictitious testimonials.
4. Correct known catalog-filter issue when date validation fails while preserving independent search/type filters.
5. Ensure Docker Compose cold start, migrations, seed/reset, health checks, secrets hygiene; align README/setup/architecture/AGENTS.
6. Keep the GitHub Actions workflow aligned with the local PostgreSQL checks and HTTP smoke. M3 records the run on GitHub.

**Exit**: Main flows work on desktop and mobile, Hải reviews the product experience, and a separate environment can be created from the documented steps.

### M3 — Independent verification and release candidate (2–3 working days target)
1. Use a clean, separate Docker project + volumes to avoid destroying development data.
2. Verify build, database health, migrations, seed, Django checks, check of migrations against models, test suite including two real-DB concurrency cases, HTTP smoke.
3. Exercise logged-in customer and staff flows end-to-end; verify both web and API business behavior and permissions; inspect at desktop/mobile widths.
4. Check no secrets, no broken paths, no undocumented setup steps, no unresolved blocker/critical defect, no unreviewed scope deviation.
5. Record verification linked to exact commit SHA, build and environment; report PASS/FAIL/BLOCKED and limitations clearly.
6. Run GitHub Actions for the exact candidate commit after Hải separately approves push. Record the workflow result with the candidate evidence.

**Exit**: The reproducible candidate has verified migrations, working main journeys, a green GitHub run and no known unresolved release blocker.

### M4 — Release approval and Base v1.0 freeze

Complete independent handoff from repository files. Hải reviews the candidate and its evidence and separately approves merge, release and the `v1.0.0-qa-baseline` tag. G4 passes once the approved baseline is frozen, reproducible and ready for handoff.

## Work cadence
- Single writer per worktree. Do not use terminal Codex and IDE Sidebar as concurrent modifying agents in same directory.
- Each task identifies expected behavior, inspects existing implementation, makes the smallest coherent change, runs relevant checks, reviews the diff and records limitations. Commit locally at a meaningful checkpoint in the workflow authorized by Hải.
- Record proposed changes with their impact on the current milestone and obtain approval before expanding scope.
- Targets are planning assumptions, not promises. Quality gates determine completion, not elapsed days or file counts.

## Release gates
- G0: Git recovery checkpoint and clean scope
- G1: Domain behavior correct, transaction/concurrency checks verified
- G2: End-to-end customer/staff UI reviewed with Hải, Docker repeatable, docs accurate
- G3: PostgreSQL suite and HTTP smoke pass, CI green on commit, security checks pass
- G4: Independent handoff verified and Hải has approved and frozen the release
