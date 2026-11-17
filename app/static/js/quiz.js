// Quiz play enhancements: announce answer feedback and prevent double submits.
(() => {
  "use strict";

  // After an answer the server renders the feedback panel. Move focus to its
  // heading so screen readers announce the verdict, and bring the whole panel
  // (verdict, explanation, "next" button) into view on short screens.
  const heading = document.getElementById("feedback-title");
  if (heading) {
    const panel = heading.closest(".feedback") || heading;
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    heading.focus({ preventScroll: true });
    const tallerThanView = panel.offsetHeight > window.innerHeight - 32;
    panel.scrollIntoView({
      block: tallerThanView ? "start" : "nearest",
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }

  // A fast double tap would post the same answer twice; the second request is
  // rejected by the server and would replace the feedback with an error page.
  const form = document.querySelector(".answer-form");
  if (form) {
    form.addEventListener("submit", (event) => {
      if (form.dataset.sent === "true") {
        event.preventDefault();
        return;
      }
      form.dataset.sent = "true";
      if (event.submitter) event.submitter.classList.add("is-picked");
    });
  }
})();
