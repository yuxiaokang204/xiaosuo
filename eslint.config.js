// ESLint 9 扁平配置（最小集）。安装依赖后可用：
//   npm i -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks
//   npm run lint
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default tseslint.config(
  { ignores: ["dist/", "node_modules/", "*.config.js", "*.config.ts"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/frontend/**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // 项目大量使用 any 渐进迁移，先降级为告警而非报错
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
);
