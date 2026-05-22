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
  if ((await page.locator('text=/demo-[a-z0-9]{8}/').count()) < 2) {
    throw new Error("missing recent run summary content");
  }
  await page.getByRole("button", { name: "只看成功" }).click();
  const filteredBodyText = await page.locator("body").innerText();
  if (!filteredBodyText.includes("只看成功")) {
    throw new Error("missing success filter control");
  }
  await page.getByRole("button", { name: "全部记录" }).click();
  await page.getByLabel("搜索记录").fill("不存在的记录");
  await page.waitForTimeout(300);
  const bodyTextAfterSearchMiss = await page.locator("body").innerText();
  if (!bodyTextAfterSearchMiss.includes("没有匹配的 run 记录。")) {
    throw new Error("missing empty search state");
  }
  await page.getByLabel("搜索记录").fill("巷口手作咖啡");
  await page.waitForTimeout(300);
  const bodyTextAfterSearchHit = await page.locator("body").innerText();
  if (!bodyTextAfterSearchHit.includes("巷口手作咖啡 结构迁移方案")) {
    throw new Error("missing matched search result");
  }
  await page.getByLabel("搜索记录").fill("");
  await page.getByLabel("run 备注").fill("优先补拍卖点特写");
  await page.getByRole("button", { name: "保存备注" }).click();
  await page.waitForTimeout(500);
  const bodyTextAfterNoteSave = await page.locator("body").innerText();
  if (!bodyTextAfterNoteSave.includes("优先补拍卖点特写")) {
    throw new Error("missing saved run note");
  }
  await page.getByRole("button", { name: "置顶记录" }).click();
  await page.waitForTimeout(500);
  const bodyTextAfterPin = await page.locator("body").innerText();
  if (!bodyTextAfterPin.includes("已置顶")) {
    throw new Error("missing pinned run state");
  }
  const firstCurrentRunMatch = bodyTextAfterPin.match(/Run:\s*(demo-[a-z0-9]{8})/);
  if (!firstCurrentRunMatch) {
    throw new Error("missing current run id");
  }
  const templateTitle = `${firstCurrentRunMatch[1]} 结构模板`;
  await page.getByLabel("模板名称").fill(templateTitle);
  await page.getByRole("button", { name: "保存为模板" }).click();
  await page.waitForTimeout(500);
  const bodyTextAfterTemplateSave = await page.locator("body").innerText();
  if (!bodyTextAfterTemplateSave.includes("结构模板库")) {
    throw new Error("missing template library panel");
  }
  if (!bodyTextAfterTemplateSave.includes("当前使用模板")) {
    throw new Error("missing active template state");
  }
  if (!bodyTextAfterTemplateSave.includes(templateTitle)) {
    throw new Error("missing saved template title");
  }
  const editedTemplateTitle = `${firstCurrentRunMatch[1]} 夜咖模板`;
  await page.getByLabel("编辑模板标题").fill(editedTemplateTitle);
  await page.getByLabel("模板节奏摘要").fill("5-7-5-3 的夜场节奏");
  await page.getByLabel("Hook 时长").fill("5");
  await page.getByLabel("Hook 素材要求").fill("夜景开场镜头");
  await page.getByRole("button", { name: "保存模板修改" }).click();
  await page.waitForTimeout(500);
  const bodyTextAfterTemplateEdit = await page.locator("body").innerText();
  if (!bodyTextAfterTemplateEdit.includes(editedTemplateTitle)) {
    throw new Error("missing edited template title");
  }

  const [firstJsonDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "导出 run JSON" }).click(),
  ]);
  const firstJsonDownloadPath = await firstJsonDownload.path();
  const firstJsonText = firstJsonDownloadPath ? await fs.readFile(firstJsonDownloadPath, "utf-8") : "";
  if (!firstJsonText.includes("\"material_request_sheet\"")) {
    throw new Error("missing material request sheet in exported run json");
  }
  if (!firstJsonText.includes("\"status\": \"已拍\"")) {
    throw new Error("missing persisted status in exported run json");
  }
  if (!firstJsonText.includes("\"note\": \"优先补拍卖点特写\"")) {
    throw new Error("missing persisted run note in exported json");
  }
  if (!firstJsonText.includes("\"pinned\": true")) {
    throw new Error("missing persisted pinned state in exported json");
  }

  await page.getByRole("button", { name: "生成迁移 demo" }).click();
  await page.waitForTimeout(3000);
  const bodyTextAfterTemplateRun = await page.locator("body").innerText();
  if (!bodyTextAfterTemplateRun.includes(`Template: ${editedTemplateTitle}`)) {
    throw new Error("missing applied template state on current run");
  }
  if (!bodyTextAfterTemplateRun.includes("需求素材：夜景开场镜头")) {
    throw new Error("missing edited required asset in regenerated preview");
  }
  if (!bodyTextAfterTemplateRun.includes("0-5s")) {
    throw new Error("missing edited hook duration in regenerated preview");
  }
  await page.getByLabel("按模板筛选").selectOption({ label: editedTemplateTitle });
  await page.waitForTimeout(500);
  const bodyTextAfterTemplateFilter = await page.locator("body").innerText();
  if (!bodyTextAfterTemplateFilter.includes(`模板 ${editedTemplateTitle}`)) {
    throw new Error("missing template-filtered run badge");
  }
  await page.getByLabel("按模板筛选").selectOption("");
  await page.waitForTimeout(300);
  await page.getByRole("button", { name: "回退到这一版" }).first().click();
  await page.waitForTimeout(500);
  const bodyTextAfterRollback = await page.locator("body").innerText();
  if (!bodyTextAfterRollback.includes(templateTitle)) {
    throw new Error("missing rolled back template title");
  }
  await page.getByRole("button", { name: "生成迁移 demo" }).click();
  await page.waitForTimeout(3000);
  const bodyTextAfterRollbackRun = await page.locator("body").innerText();
  if (!bodyTextAfterRollbackRun.includes(`Template: ${templateTitle}`)) {
    throw new Error("missing rolled back template state on current run");
  }

  const [jsonDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "导出 run JSON" }).click(),
  ]);
  const jsonDownloadPath = await jsonDownload.path();
  const jsonText = jsonDownloadPath ? await fs.readFile(jsonDownloadPath, "utf-8") : "";
  if (!jsonText.includes(`\"template_title\": \"${templateTitle}\"`)) {
    throw new Error("missing persisted template title in exported json");
  }

  const currentRunMatch = bodyTextAfterRollbackRun.match(/Run:\s*(demo-[a-z0-9]{8})/);
  if (!currentRunMatch) {
    throw new Error("missing current run id");
  }
  const currentRunId = currentRunMatch[1];
  const recentRunCards = page.locator("article").filter({ has: page.getByRole("button", { name: "删除记录" }) });
  const recentRunCount = await recentRunCards.count();
  if (recentRunCount < 2) {
    throw new Error("expected at least two recent runs before deletion");
  }
  let deletedRunId = "";
  let deleteIndex = -1;
  for (let index = 0; index < recentRunCount; index += 1) {
    const cardText = await recentRunCards.nth(index).innerText();
    if (!cardText.includes(currentRunId)) {
      const runIdMatch = cardText.match(/demo-[a-z0-9]{8}/);
      deletedRunId = runIdMatch?.[0] || "";
      deleteIndex = index;
      break;
    }
  }
  if (deleteIndex === -1 || !deletedRunId) {
    throw new Error("failed to find non-current run card for deletion");
  }
  await recentRunCards.nth(deleteIndex).getByRole("button", { name: "删除记录" }).click();
  await page.waitForTimeout(500);
  let deletedRunStillVisible = false;
  const remainingRunCount = await recentRunCards.count();
  for (let index = 0; index < remainingRunCount; index += 1) {
    const cardText = await recentRunCards.nth(index).innerText();
    if (cardText.includes(deletedRunId)) {
      deletedRunStillVisible = true;
      break;
    }
  }
  if (deletedRunStillVisible) {
    throw new Error("deleted run card still visible in recent runs list");
  }

  const templateCard = page
    .locator("article")
    .filter({ hasText: templateTitle })
    .filter({ has: page.getByRole("button", { name: "删除模板" }) })
    .first();
  await templateCard.getByRole("button", { name: "删除模板" }).click();
  await page.waitForTimeout(500);
  if ((await templateCard.count()) !== 0) {
    throw new Error("deleted template card still visible");
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
