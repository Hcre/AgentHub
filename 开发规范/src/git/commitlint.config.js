// commitlint 配置示例
// 安装: npm install --save-dev @commitlint/cli @commitlint/config-conventional
// 配合 husky: npx husky add .husky/commit-msg 'npx --no -- commitlint --edit $1'
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'refactor', 'docs', 'style', 'test', 'chore', 'perf'],
    ],
    'subject-case': [2, 'never', ['upper-case']],
    'subject-min-length': [2, 'always', 5],
    'body-max-line-length': [1, 'always', 100],
  },
};
