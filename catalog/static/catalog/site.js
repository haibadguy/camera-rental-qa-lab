const originalLabels = new WeakMap();

const catalogFilters = document.querySelector("[data-catalog-filters]");
if (catalogFilters) {
  const filterForm = catalogFilters.querySelector("form");
  const categoryLinks = document.querySelectorAll("[data-catalog-kind]");
  filterForm.addEventListener("input", () => {
    const filterValues = new FormData(filterForm);
    for (const link of categoryLinks) {
      const url = new URL(link.href);
      for (const name of ["search", "brand", "pickup_date", "return_date"]) {
        const value = filterValues.get(name);
        if (value) url.searchParams.set(name, value);
        else url.searchParams.delete(name);
      }
      link.href = url.href;
    }
  });

  const compactLayout = window.matchMedia("(max-width: 59rem)");
  if (compactLayout.matches && !catalogFilters.hasAttribute("data-filters-active")) {
    catalogFilters.open = false;
  }
  compactLayout.addEventListener("change", (event) => {
    if (!event.matches) catalogFilters.open = true;
  });
}

const bookingForm = document.querySelector("[data-daily-rate]");
if (bookingForm) {
  const estimate = bookingForm.querySelector("[data-booking-estimate]");
  const output = estimate.querySelector("output");
  const breakdown = estimate.querySelector("[data-estimate-breakdown]");
  const pickup = bookingForm.elements.pickup_date;
  const dropoff = bookingForm.elements.return_date;
  const quantity = bookingForm.elements.quantity;
  const money = new Intl.NumberFormat("vi-VN");
  const dailyRate = BigInt(bookingForm.dataset.dailyRate);
  const maxRentalDays = Number(bookingForm.dataset.maxRentalDays);

  const updateEstimate = () => {
    const days = (dropoff.valueAsNumber - pickup.valueAsNumber) / 86400000;
    const count = quantity.valueAsNumber;
    const valid = Number.isInteger(days) && days >= 1 && days <= maxRentalDays
      && pickup.validity.valid && quantity.validity.valid;
    estimate.hidden = !valid;
    breakdown.textContent = valid
      ? `${money.format(days)} ngày × ${money.format(count)} thiết bị × ${money.format(dailyRate)} ₫`
      : "";
    output.value = valid
      ? `${money.format(dailyRate * BigInt(days) * BigInt(count))} ₫`
      : "";
  };

  bookingForm.addEventListener("input", updateEstimate);
  updateEstimate();
}

document.addEventListener("submit", (event) => {
  const button = event.submitter;
  if (!button || event.defaultPrevented || button.name) return;
  originalLabels.set(button, button.textContent);
  button.textContent = "Đang xử lý…";
  button.disabled = true;
  button.form.setAttribute("aria-busy", "true");
});

window.addEventListener("pageshow", () => {
  for (const button of document.querySelectorAll("button[disabled]")) {
    if (!originalLabels.has(button)) continue;
    button.disabled = false;
    button.textContent = originalLabels.get(button);
    button.form.removeAttribute("aria-busy");
  }
});

for (const form of document.querySelectorAll("[data-scan-form]")) {
    const codes = form.querySelector("[data-scan-codes]");
    const camera = form.querySelector("[data-scan-camera]");
    const video = form.querySelector("[data-scan-preview]");
    const status = form.querySelector("[data-scan-status]");
    let stream;
    let timer;
    let detector;

    function stopCamera() {
        clearTimeout(timer);
        stream?.getTracks().forEach(track => track.stop());
        stream = undefined;
        video.srcObject = null;
        video.hidden = true;
        camera.textContent = "Mở máy ảnh";
    }

    async function scanFrame() {
        try {
            for (const result of await detector.detect(video)) {
                if (!stream) return;
                const code = result.rawValue.trim();
                const listed = codes.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
                if (code && !/[\r\n]/.test(code) && code.length <= 48 &&
                    listed.length < 30 && !listed.includes(code)) {
                    codes.value = [...listed, code].join("\n") + "\n";
                    status.textContent = `Đã đọc ${code} (${listed.length + 1}/30).`;
                }
            }
            if (stream) timer = setTimeout(scanFrame, 250);
        } catch {
            stopCamera();
            status.textContent = "Không đọc được mã qua máy ảnh. Hãy nhập mã kho.";
        }
    }

    if ("BarcodeDetector" in window && navigator.mediaDevices?.getUserMedia) {
        camera.hidden = false;
        camera.addEventListener("click", async () => {
            if (stream) {
                stopCamera();
                return;
            }
            camera.disabled = true;
            try {
                detector = new BarcodeDetector({ formats: ["qr_code", "code_128"] });
                stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: { ideal: "environment" } },
                });
                video.srcObject = stream;
                video.hidden = false;
                await video.play();
                camera.textContent = "Tắt máy ảnh";
                scanFrame();
            } catch {
                stopCamera();
                status.textContent = "Không mở được máy ảnh. Hãy nhập mã kho.";
            } finally {
                camera.disabled = false;
            }
        });
        form.addEventListener("submit", stopCamera);
        window.addEventListener("pagehide", stopCamera);
    }
}
