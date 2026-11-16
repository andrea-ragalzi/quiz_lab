// Reveal the server-rendered show/hide buttons for password fields.
(() => {
  "use strict";

  document.querySelectorAll(".password-toggle").forEach((button) => {
    const targetId = button.getAttribute("aria-controls");
    const input = targetId ? document.getElementById(targetId) : null;
    if (!(input instanceof HTMLInputElement) || input.type !== "password") {
      return;
    }

    button.hidden = false;
    button.addEventListener("click", () => {
      const visible = input.type === "password";
      const action = visible
        ? button.dataset.hideAction
        : button.dataset.showAction;
      input.type = visible ? "text" : "password";
      button.setAttribute("aria-pressed", String(visible));
      button.setAttribute(
        "aria-label",
        `${action} ${button.dataset.passwordLabel}`,
      );
      button.textContent = action;
    });
  });
})();
