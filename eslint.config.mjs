import { defineConfig, globalIgnores } from 'eslint/config'
import { fileURLToPath } from 'node:url'
import js from '@eslint/js'
import globals from 'globals'
import nextVitals from 'eslint-config-next/core-web-vitals'
import nextTs from 'eslint-config-next/typescript'
import expo from 'eslint-config-expo/flat.js'
import eslintConfigPrettier from 'eslint-config-prettier'

const dashboardTsconfig = fileURLToPath(new URL('apps/dashboard/tsconfig.json', import.meta.url))
const mobileTsconfig = fileURLToPath(new URL('apps/mobile/tsconfig.json', import.meta.url))

const nodeExtensions = [
  '.android.cjs',
  '.android.mjs',
  '.android.js',
  '.android.jsx',
  '.android.ts',
  '.android.tsx',
  '.android.d.ts',
  '.ios.cjs',
  '.ios.mjs',
  '.ios.js',
  '.ios.jsx',
  '.ios.ts',
  '.ios.tsx',
  '.ios.d.ts',
  '.web.cjs',
  '.web.mjs',
  '.web.js',
  '.web.jsx',
  '.web.ts',
  '.web.tsx',
  '.web.d.ts',
  '.native.cjs',
  '.native.mjs',
  '.native.js',
  '.native.jsx',
  '.native.ts',
  '.native.tsx',
  '.native.d.ts',
  '.cjs',
  '.mjs',
  '.js',
  '.jsx',
  '.ts',
  '.tsx',
  '.d.ts',
  '.css',
]

const scope = (prefix) => (entries) =>
  entries.map((entry) => {
    const { files, ignores, ...rest } = entry
    return {
      ...rest,
      files: (files ?? ['**/*']).map((f) => `${prefix}/${f}`),
      ...(ignores && { ignores: ignores.map((i) => `${prefix}/${i}`) }),
    }
  })

export default defineConfig([
  globalIgnores([
    '**/node_modules/**',
    '**/.next/**',
    '**/.expo/**',
    '**/dist/**',
    '**/build/**',
    '**/out/**',
    '**/coverage/**',
    '**/next-env.d.ts',
    '**/expo-env.d.ts',
  ]),
  js.configs.recommended,
  {
    files: ['*.{js,mjs,cjs}'],
    languageOptions: { globals: globals.node },
  },
  ...scope('apps/dashboard')([...nextVitals, ...nextTs]),
  {
    files: ['apps/dashboard/**/*.{js,mjs,cjs,jsx,ts,tsx}'],
    rules: {
      '@next/next/no-html-link-for-pages': [
        'error',
        fileURLToPath(new URL('apps/dashboard/src/app', import.meta.url)),
      ],
    },
  },
  {
    files: ['apps/dashboard/**/*.{js,mjs,cjs,jsx,ts,tsx}'],
    settings: {
      'import/resolver': {
        typescript: { project: dashboardTsconfig, alwaysTryTypes: true },
        node: { extensions: nodeExtensions },
      },
    },
  },
  ...scope('apps/mobile')(expo),
  {
    files: ['apps/mobile/**/*.{js,mjs,cjs,jsx,ts,tsx}'],
    settings: {
      'import/resolver': {
        typescript: { project: mobileTsconfig, alwaysTryTypes: true },
        node: { extensions: nodeExtensions },
      },
    },
  },
  eslintConfigPrettier,
])
