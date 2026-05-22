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
  const page = await browser.newPage({ viewport: { width: 1440, height: 2800 } });
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "生成迁移 demo" }).click();
  await page.waitForTimeout(3000);

  await page.getByRole("button", { name: "全选缺口" }).click();
  await page.getByRole("button", { name: "加入需求单" }).click();

  const bodyText = await page.locator("body").innerText();
  if (!bodyText.includes("素材需求单")) {
    throw new Error("missing request sheet panel");
  }
  if (!bodyText.includes("商品卖点特写")) {
    throw new Error("missing selected material task content");
  }
  if (!bodyText.includes("建议镜头")) {
    throw new Error("missing task details in request sheet");
  }

  console.log("REQUEST_SHEET_OK=1");
} finally {
  await browser.close();
}
