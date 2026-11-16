// Progressive enhancement for the collapsible mobile navigation.
(() => {
  "use strict";

  const toggle = document.querySelector(".mobile-toggle");
  const links = document.querySelector("#nav-links");
  if (!toggle || !links) return;

  document.documentElement.classList.add("has-js");

  const setExpanded = (expanded) => {
    toggle.setAttribute("aria-expanded", String(expanded));
    links.classList.toggle("open", expanded);
  };

  toggle.addEventListener("click", () => {
    setExpanded(toggle.getAttribute("aria-expanded") !== "true");
  });

  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      toggle.getAttribute("aria-expanded") === "true"
    ) {
      setExpanded(false);
      toggle.focus();
    }
  });
})();
