import { test, expect } from '@playwright/test'
import path from 'node:path'

test('annotation rejects incomplete verification and saves completed labels', async ({ page }) => {
  await page.goto('http://127.0.0.1:8766')
  await expect(page.getByRole('img')).toBeVisible()
  await page.locator('#annotator').fill('Automated fixture test')
  for (const id of ['group', 'vendor_group', 'template_group']) await page.locator('#' + id).fill('synthetic-browser-fixture')
  await page.locator('#field-invoice_no').fill('TEST-GST-001')
  await page.locator('#status').selectOption('verified')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Review every field')
  for (const checkbox of await page.locator('input[type=checkbox]').all()) await checkbox.check()
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Saved verified')
  await page.reload()
  await expect(page.locator('#field-invoice_no')).toHaveValue('TEST-GST-001')
  await expect(page.locator('#status')).toHaveValue('verified')
  page.once('dialog', dialog => dialog.accept())
  await page.locator('#metadata select').first().selectOption('UTILITY_BILL')
  await expect(page.locator('#status')).toHaveValue('draft')
  await expect(page.locator('#field-consumer_no')).toHaveValue('')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Saved draft')
  page.once('dialog', dialog => dialog.accept())
  await page.locator('#metadata select').first().selectOption('GST_INVOICE')
  page.once('dialog', dialog => dialog.accept())
  await page.locator('#documents').selectOption('1')
  await page.locator('#documents').selectOption('0')
  await expect(page.locator('#metadata select').first()).toHaveValue('UTILITY_BILL')
  await expect(page.locator('#field-consumer_no')).toBeVisible()
})

test('configuration, records and dashboard load without browser errors', async ({ page }) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  await page.getByRole('button', { name: 'Settings', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Service configuration' })).toBeVisible()
  await page.getByRole('button', { name: 'Records', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Saved records' })).toBeVisible()
  await page.getByRole('button', { name: 'Dashboard', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Document overview' })).toBeVisible()
  await page.getByRole('button', { name: 'Research', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Research benchmarks' })).toBeVisible()
  await expect(page.getByText('No measured run is available yet.')).toBeVisible()
  expect(errors).toEqual([])
})

test('mobile navigation exposes upload and research without horizontal page overflow', async ({page})=>{
  await page.setViewportSize({width:390,height:844})
  await page.goto('/')
  await expect(page.getByRole('heading',{name:'Upload an accounting document'})).toBeVisible()
  await expect(page.getByRole('button',{name:'Expand navigation'})).toBeVisible()
  await page.getByRole('button',{name:'Research',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Research benchmarks'})).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
})

for (const [pipeline, label] of [
  ['hosted_vlm', 'Hosted vision model'],
  ['ocr_layoutlm', 'OCR + LayoutLM'],
  ['layoutlm_hosted_fallback', 'LayoutLM + selective hosted fallback'],
]) {
  test(`live ${pipeline}: upload, extract, edit, validate, save, search and CSV`, async ({ page }) => {
    test.skip(process.env.EMUNIM_LIVE_E2E !== '1', 'Set EMUNIM_LIVE_E2E=1 to permit live API calls')
    const errors = []
    const calls = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('request', request => { if (request.url().endsWith('/api/ocr')) calls.push(request.url()) })
    await page.goto('/')
    await page.getByRole('button', { name: label, exact: true }).click()
    await page.locator('input[type=file]').setInputFiles(path.join(process.env.EMUNIM_E2E_DIR, 'fixtures/images/gst_invoice.png'))
    const preparation = page.waitForResponse(response=>response.url().endsWith(pipeline==='hosted_vlm'?'/api/upload':'/api/ocr'),{timeout:90000})
    await page.getByRole('button', { name: 'Upload and continue', exact: true }).click()
    expect((await preparation).status()).toBe(200)
    await expect(page.getByRole('heading', { name: 'Confirm document type' })).toBeVisible({ timeout: 20000 })
    await page.locator('select').selectOption('GST_INVOICE')
    const extracted = page.waitForResponse(response => response.url().endsWith('/api/extract'), { timeout: 120000 })
    await page.getByRole('button', { name: 'Extract fields', exact: true }).click()
    const response = await extracted
    expect(response.status()).toBe(200)
    const run = await response.json()
    expect(run.pipeline).toBe(pipeline)
    if (pipeline === 'ocr_layoutlm') expect(run.metadata.hosted.attempts).toBe(0)
    expect(calls.length).toBe(pipeline === 'hosted_vlm' ? 0 : 1)
    await expect(page.getByRole('heading', { name: 'Review extracted fields' })).toBeVisible()
    const editedId = 'BROWSER-' + pipeline
    await page.getByLabel('Invoice No.', { exact: false }).fill(editedId)
    await page.getByRole('button', { name: /Validate corrected values|Run validation/ }).click()
    await expect(page.getByRole('heading', { name: 'Validate and save' })).toBeVisible()
    await page.getByLabel('Review note / reason for accepting unresolved issues').fill('Automated synthetic browser test; not a real accounting record.')
    await expect(page.getByRole('button', { name: 'Save reviewed record' })).toBeDisabled()
    await page.getByRole('checkbox', { name: 'I reviewed the source and the final values.' }).check()
    await page.getByRole('button', { name: 'Save reviewed record' }).click()
    await expect(page.getByRole('heading', { name: 'Record saved' })).toBeVisible()
    await page.getByRole('button', { name: 'Records', exact: true }).click()
    await page.getByRole('textbox', { name: 'Search saved records' }).fill(editedId)
    await expect(page.locator('tbody tr')).toHaveCount(1)
    await page.getByRole('button', { name: 'View', exact: true }).click()
    await expect(page.locator('.record-detail')).toContainText(editedId)
    const downloadEvent = page.waitForEvent('download')
    await page.getByRole('link', { name: 'Export CSV' }).click()
    const download = await downloadEvent
    expect(await download.failure()).toBeNull()
    expect(errors).toEqual([])
  })
}
