const js = require("@eslint/js");
const globals = require("globals");

module.exports = [
  { ignores: ["node_modules/"] },
  js.configs.recommended,
  {
    files: ["moonlight-voice/moonlight_voice/static/js/**/*.js"],
    languageOptions: {
      globals: globals.browser,
      sourceType: "module",
    },
  },
];
