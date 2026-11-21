const originalLabels = new WeakMap();

const bookingForm = document.querySelector("[data-daily-rate]");
if (bookingForm) {
  const estimate = bookingForm.querySelector("[data-booking-estimate]");
  const output = estimate.querySelector("output");
  const pickup = bookingForm.elements.pickup_date;
  const dropoff = bookingForm.elements.return_date;
  const quantity = bookingForm.elements.quantity;
  const money = new Intl.NumberFormat("vi-VN");
  const dailyRate = BigInt(bookingForm.dataset.dailyRate);

  const updateEstimate = () => {
    const days = (dropoff.valueAsNumber - pickup.valueAsNumber) / 86400000;
    const valid = Number.isInteger(days) && days >= 1 && days <= 30
      && pickup.validity.valid && quantity.validity.valid;
    estimate.hidden = !valid;
    output.value = valid
      ? `${money.format(dailyRate * BigInt(days) * BigInt(quantity.valueAsNumber))} ₫`
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
