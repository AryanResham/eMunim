import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspace = process.env.EMUNIM_E2E_DIR || path.join(root, 'backend/data/browser-tests', new Date().toISOString().replaceAll(/[:.]/g, '-'))
process.env.EMUNIM_E2E_DIR = workspace

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  retries: 0,
  timeout: 180000,
  expect: { timeout: 15000 },
  outputDir: path.join(workspace, 'artifacts'),
  reporter: [['list'], ['json', { outputFile: path.join(workspace, 'results.json') }]],
  use: { baseURL: 'http://127.0.0.1:5176', channel: 'chrome', headless: true, actionTimeout: 15000, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: [
    { command: `python scripts/e2e_server.py backend --workspace "${workspace}"`, cwd: root, url: 'http://127.0.0.1:8002/api/health', timeout: 60000 },
    { command: `python scripts/e2e_server.py annotation --workspace "${workspace}"`, cwd: root, url: 'http://127.0.0.1:8766', timeout: 30000 },
    { command: 'npm.cmd run dev -- --host 127.0.0.1 --port 5176 --strictPort', url: 'http://127.0.0.1:5176', env: { VITE_API_URL: 'http://127.0.0.1:8002/api' }, timeout: 30000 },
  ],
})
