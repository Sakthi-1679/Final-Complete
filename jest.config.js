/** @type {import('jest').Config} */
const config = {
  // Use ts-jest to handle TypeScript files
  preset: "ts-jest",

  // jsdom simulates a browser environment (needed for React)
  testEnvironment: "jsdom",

  // Map tests/frontend → look for files inside tests/frontend/
  roots: ["<rootDir>/tests/frontend"],

  // Resolve path aliases (mirrors tsconfig.paths if any)
  moduleNameMapper: {
    "\\.(css|less|scss|sass)$": "<rootDir>/tests/frontend/__mocks__/styleMock.js",
    "\\.(jpg|jpeg|png|gif|webp|svg)$": "<rootDir>/tests/frontend/__mocks__/fileMock.js",
    // Allow imports like "../../frontend/..." from test files
    "^../../frontend/(.*)$": "<rootDir>/frontend/$1",
  },

  // Run setup file before each test (provides @testing-library/jest-dom matchers)
  setupFilesAfterFramework: [],
  setupFilesAfterFramework: [],
  setupFilesAfterEachTest: [],

  // Actual setup
  setupFilesAfterFramework: [],
  setupFilesAfterFramework: [],
  setupFiles: ["<rootDir>/tests/frontend/setup.ts"],

  // TypeScript + JSX transform
  transform: {
    "^.+\\.(ts|tsx)$": ["ts-jest", {
      tsconfig: {
        jsx: "react-jsx",
        esModuleInterop: true,
        allowSyntheticDefaultImports: true,
      },
    }],
  },

  // Which files count as tests
  testMatch: [
    "<rootDir>/tests/frontend/**/*.test.{ts,tsx}",
    "<rootDir>/tests/frontend/**/*.spec.{ts,tsx}",
  ],

  // Coverage settings
  collectCoverageFrom: [
    "frontend/**/*.{ts,tsx}",
    "!frontend/**/*.d.ts",
    "!frontend/index.tsx",
    "!frontend/vite-env.d.ts",
  ],

  coverageDirectory: "coverage/frontend",

  coverageThresholds: {
    global: {
      branches:   40,
      functions:  50,
      lines:      50,
      statements: 50,
    },
  },
};

module.exports = config;
