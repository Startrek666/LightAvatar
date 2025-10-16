/* eslint-env node */
module.exports = {
    root: true,
    extends: [
        'plugin:vue/vue3-recommended',
        'eslint:recommended',
        '@vue/eslint-config-typescript'
    ],
    parserOptions: {
        ecmaVersion: 'latest'
    },
    rules: {
        // 允许使用 v-model:xxx 语法 (Vue 3.4+)
        'vue/no-v-model-argument': 'off',

        // 允许未使用的变量（开发阶段）
        '@typescript-eslint/no-unused-vars': 'warn',
        'no-unused-vars': 'warn',

        // 其他规则
        'vue/multi-word-component-names': 'off',
        'vue/require-default-prop': 'off'
    }
}

