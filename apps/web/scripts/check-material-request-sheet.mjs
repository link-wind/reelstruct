const playwrightModule =
  process.env.PLAYWRIGHT_MODULE ||
  "file:///Users/linkwind/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";

const { chromium } = await import(playwrightModule);

const baseUrl = process.env.BASE_URL || "http://127.0.0.1:3002";
const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath,
});

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 2800 } });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: baseUrl });
  const page = await context.newPage();
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "生成迁移 demo" }).click();
  await page.waitForTimeout(3000);

  await page.getByRole("button", { name: "全选缺口" }).click();
  await page.getByRole("button", { name: "加入需求单" }).click();
  await page.getByRole("button", { name: "移出需求单" }).first().click();
  const remainingAfterRemove = await page.getByRole("button", { name: "移出需求单" }).count();
  if (remainingAfterRemove < 1) {
    throw new Error("expected request sheet to keep remaining tasks after single remove");
  }
  await page.getByRole("button", { name: "加入需求单" }).click();
  await page.getByRole("button", { name: "已拍" }).first().click();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "导出 txt" }).click(),
  ]);
  const downloadPath = await download.path();
  const fs = await import("node:fs/promises");
  const exportedText = downloadPath ? await fs.readFile(downloadPath, "utf-8") : "";

  await page.getByRole("button", { name: "复制需求单" }).click();
  const clipboardText = await page.evaluate(() => navigator.clipboard.readText());

  const bodyText = await page.locator("body").innerText();
  if (!bodyText.includes("素材需求单")) {
    throw new Error("missing request sheet panel");
  }
  if (!bodyText.includes("最近 run 记录")) {
    throw new Error("missing recent runs panel");
  }
  if (!bodyText.includes("商品卖点特写")) {
    throw new Error("missing selected material task content");
  }
  if (!bodyText.includes("建议镜头")) {
    throw new Error("missing task details in request sheet");
  }
  if (!bodyText.includes("已拍")) {
    throw new Error("missing task status toggle");
  }
  if (!exportedText.includes("当前状态：已拍")) {
    throw new Error("missing exported status content");
  }
  if (!clipboardText.includes("素材需求单")) {
    throw new Error("missing clipboard text");
  }
  if (!clipboardText.includes("当前状态：已拍")) {
    throw new Error("missing clipboard status content");
  }

  await page.getByRole("button", { name: "应用改稿并重生成" }).click();
  await page.waitForTimeout(3000);
  const rerunBodyText = await page.locator("body").innerText();
  if (!rerunBodyText.includes("当前状态：已拍")) {
    throw new Error("missing persisted request sheet status after rerun");
  }
  if (!rerunBodyText.includes("巷口手作咖啡 结构迁移方案")) {
    throw new Error("missing recent run summary content");
  }
  await page.getByRole("button", { name: "只看成功" }).click();
  const filteredBodyText = await page.locator("body").innerText();
  if (!filteredBodyText.includes("只看成功")) {
    throw new Error("missing success filter control");
  }
  await page.getByRole("button", { name: "全部记录" }).click();

  const [jsonDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "导出 run JSON" }).click(),
  ]);
  const jsonDownloadPath = await jsonDownload.path();
  const jsonText = jsonDownloadPath ? await fs.readFile(jsonDownloadPath, "utf-8") : "";
  if (!jsonText.includes("\"material_request_sheet\"")) {
    throw new Error("missing material request sheet in exported run json");
  }
  if (!jsonText.includes("\"status\": \"已拍\"")) {
    throw new Error("missing persisted status in exported run json");
  }

  const firstRunId = await page.locator('text=/demo-[a-z0-9]{8}/').first().innerText();
  const firstRunCard = page.locator("article").filter({ hasText: firstRunId }).first();
  await page.getByRole("button", { name: "删除记录" }).first().click();
  await page.waitForTimeout(500);
  if ((await firstRunCard.count()) !== 0) {
    throw new Error("deleted run card still visible in recent runs list");
  }

  await page.getByRole("button", { name: "清空需求单" }).click();
  const bodyTextAfterClear = await page.locator("body").innerText();
  if (!bodyTextAfterClear.includes("先从补拍建议里勾选缺口，再点“加入需求单”。")) {
    throw new Error("missing empty request sheet hint after clear");
  }

  console.log("REQUEST_SHEET_OK=1");
} finally {
  await browser.close();
}
