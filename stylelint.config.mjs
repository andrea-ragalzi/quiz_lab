/** Stylelint configuration for the Silver Forest Flame stylesheet. */
export default {
  extends: ["stylelint-config-standard"],
  rules: {
    // Keep the prefix syntax (`max-width: 760px`); the range syntax requires
    // Safari 16.4+, and both are equivalent for this stylesheet.
    "media-feature-range-notation": "prefix",
    // Gradient text needs `-webkit-background-clip` in Chromium < 120 and older
    // Safari; without it the transparent text would become invisible.
    "property-no-vendor-prefix": [
      true,
      { ignoreProperties: ["-webkit-background-clip"] },
    ],
    // This heuristic cannot tell whether two selectors match the same element.
    // Every reported pair was reviewed: they target different elements or
    // mutually exclusive states, set unrelated properties, or rely on higher
    // specificity deliberately (no-JS navigation, form-field focus ring), so
    // reordering rules would add risk without changing behaviour.
    "no-descending-specificity": null,
  },
};
