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
