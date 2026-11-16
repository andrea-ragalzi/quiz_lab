// ESLint flat config for the small, framework-free browser scripts.
import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["app/static/js/**/*.js"],
    languageOptions: {
      ecmaVersion: 2022,
      // Loaded as classic deferred <script> elements, not ES modules.
      sourceType: "script",
      globals: globals.browser,
    },
    rules: {
      strict: ["error", "function"],
      "no-implicit-globals": "error",
      eqeqeq: ["error", "always"],
      "prefer-const": "error",
      "no-var": "error",
    },
  },
];
