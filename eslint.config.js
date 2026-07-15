import globals from "globals";
import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.es2022,
      },
    },
    rules: {
      // ── Основные ──────────────────────────────────────────
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_", caughtErrorsIgnorePattern: "^_" }],
      "no-console": "off",
      "no-debugger": "warn",

      // ── Производительность: await / async ─────────────────
      "no-await-in-loop": "warn",
      "no-async-promise-executor": "error",
      "require-await": "warn",
      "no-return-await": "warn",

      // ── Производительность: циклы и функции ───────────────
      "no-loop-func": "warn",
      "no-inner-declarations": "warn",
      "prefer-const": "warn",
      "no-var": "warn",

      // ── Производительность: паттерны через AST ────────────
      "no-restricted-syntax": [
        "warn",
        // 1) querySelector/querySelectorAll внутри цикла — кешируй снаружи
        {
          selector:
            "ForStatement CallExpression[callee.property.name='querySelector'], \
             ForStatement CallExpression[callee.property.name='querySelectorAll'], \
             ForInStatement CallExpression[callee.property.name='querySelector'], \
             ForInStatement CallExpression[callee.property.name='querySelectorAll'], \
             ForOfStatement CallExpression[callee.property.name='querySelector'], \
             ForOfStatement CallExpression[callee.property.name='querySelectorAll']",
          message: "⚠ PERF: DOM query inside loop. Cache querySelector/querySelectorAll outside the loop.",
        },
        // 2) innerHTML += в цикле — собери строку или используй DocumentFragment
        {
          selector:
            "ForStatement AssignmentExpression[left.property.name='innerHTML'][operator='+='], \
             ForOfStatement AssignmentExpression[left.property.name='innerHTML'][operator='+=']",
          message: "⚠ PERF: innerHTML += in loop causes repeated DOM parse+rebuild. Build a string first, assign once.",
        },
        // 3) getElementById в функциях (не на верхнем уровне модуля — это кеш)
        {
          selector:
            ":function > BlockStatement CallExpression[callee.property.name='getElementById'], \
             :function > BlockStatement > ExpressionStatement > CallExpression[callee.property.name='getElementById'], \
             ArrowFunctionExpression > BlockStatement CallExpression[callee.property.name='getElementById']",
          message: "⚠ PERF: getElementById inside function body. Cache the reference at module load or in the dom object in state.js.",
        },
        // 4) await внутри цикла — последовательные запросы вместо параллельных
        {
          selector:
            "ForOfStatement AwaitExpression, \
             ForStatement AwaitExpression",
          message: "⚠ PERF: await inside loop. Use Promise.all() for parallel execution if possible.",
        },
        // 5) new Array().push в цикле — лучше预先 аллоцировать или использовать concat
        {
          selector:
            "ForStatement > BlockStatement > ExpressionStatement > CallExpression[callee.object.type='ArrayExpression'][callee.property.name='push']",
          message: "⚠ PERF: Array.push in loop. Consider pre-allocation or building array with map/concat.",
        },
        // 6) JSON.parse(JSON.stringify()) — дорогой deep clone
        {
          selector:
            "CallExpression[callee.object.type='JSON'][callee.property.name='parse'] > CallExpression[callee.object.type='JSON'][callee.property.name='stringify']",
          message: "⚠ PERF: JSON.parse(JSON.stringify()) is slow deep clone. Use structuredClone() or manual copy.",
        },
        // 7) document.createElement внутри цикла без fragment
        {
          selector:
            "ForStatement > BlockStatement CallExpression[callee.object.name='document'][callee.property.name='createElement']",
          message: "⚠ PERF: DOM node creation in loop. Use DocumentFragment to batch DOM insertions.",
        },
        // 8) appendChild в цикле — вызывает reflow каждый раз
        {
          selector:
            "ForStatement > BlockStatement > ExpressionStatement > CallExpression[callee.property.name='appendChild']",
          message: "⚠ PERF: appendChild in loop triggers reflow each time. Use DocumentFragment to batch.",
        },
        // 9) style.width/height/left/top присвоение в цикле — layout thrashing
        {
          selector:
            "ForStatement > BlockStatement > ExpressionStatement > AssignmentExpression[left.object.property.name='style']",
          message: "⚠ PERF: style assignment in loop may cause layout thrashing. Batch reads, then batch writes.",
        },
        // 10) substring/substr вместо slice
        {
          selector: "CallExpression[callee.property.name='substring']",
          message: "⚠ PERF: Use .slice() instead of .substring() — it's faster and more predictable.",
        },
      ],

      // ── Безопасность DOM ──────────────────────────────────
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-script-url": "warn",
    },
  },
  {
    ignores: ["app/static/js/vendor/**"],
  },
];
