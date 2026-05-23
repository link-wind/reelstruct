const playwrightModule =
  process.env.PLAYWRIGHT_MODULE ||
  "file:///Users/linkwind/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";

const { chromium } = await import(playwrightModule);
const { fileURLToPath } = await import("node:url");
const { spawnSync } = await import("node:child_process");

const baseUrl = process.env.BASE_URL || "http://127.0.0.1:3002";
const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const materialFixturePath = fileURLToPath(new URL("../../../fixtures/vid_001.mp4", import.meta.url));

const browser = await chromium.launch({
  headless: true,
  executablePath: chromePath,
});

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 2800 } });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: baseUrl });
  const page = await context.newPage();
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.getByLabel("输出版本").selectOption("high_click");
  await page.getByRole("button", { name: "生成版本对比" }).click();
  await page.waitForTimeout(700);
  const variantBodyText = await page.locator("body").innerText();
  if (!variantBodyText.includes("高点击版") || !variantBodyText.includes("高转化版") || !variantBodyText.includes("高节奏版")) {
    throw new Error("missing output variant comparison cards");
  }
  if (!variantBodyText.includes("前 2 秒")) {
    throw new Error("missing high-click hook summary in variant comparison");
  }
  const highClickVariantCard = page
    .locator("article")
    .filter({ hasText: "高点击版" })
    .filter({ has: page.getByRole("button", { name: "选择这个版本" }) })
    .first();
  if ((await highClickVariantCard.count()) > 0) {
    await highClickVariantCard.getByRole("button", { name: "选择这个版本" }).click();
  }
  await page.getByRole("button", { name: "批量生成四版 demo" }).click();
  await page.waitForTimeout(7000);
  const bodyTextAfterBatchRun = await page.locator("body").innerText();
  if (!bodyTextAfterBatchRun.includes("四版 demo 已生成")) {
    throw new Error("missing batch demo generation status");
  }
  for (const variantLabel of ["默认版", "高点击版", "高转化版", "高节奏版"]) {
    if (!bodyTextAfterBatchRun.includes(variantLabel)) {
      throw new Error(`missing generated batch run for ${variantLabel}`);
    }
  }
  if (!bodyTextAfterBatchRun.includes("Variant: 高点击版")) {
    throw new Error("missing selected batch run in current preview");
  }
  if (!bodyTextAfterBatchRun.includes("Batch: batch-")) {
    throw new Error("missing batch id in current preview");
  }
  if (!bodyTextAfterBatchRun.includes("批次工作台")) {
    throw new Error("missing batch workspace panel");
  }
  if (!bodyTextAfterBatchRun.includes("样例方法") || !bodyTextAfterBatchRun.includes("新内容迁移") || !bodyTextAfterBatchRun.includes("素材/包装支撑")) {
    throw new Error("missing explainable structure migration columns");
  }
  if (!bodyTextAfterBatchRun.includes("结构拆解来源") || !bodyTextAfterBatchRun.includes("证据镜头")) {
    throw new Error("missing AI structure decomposition evidence display");
  }
  if (!(bodyTextAfterBatchRun.includes("AI 视频结构拆解") || bodyTextAfterBatchRun.includes("基础兜底拆解") || bodyTextAfterBatchRun.includes("基础规则拆解"))) {
    throw new Error("missing decomposition source label");
  }
  if (!bodyTextAfterBatchRun.includes("可迁移规则") || !bodyTextAfterBatchRun.includes("迁移理由")) {
    throw new Error("missing transfer reasoning details");
  }
  if (!bodyTextAfterBatchRun.includes("画面包装方案") || !bodyTextAfterBatchRun.includes("标题卡片") || !bodyTextAfterBatchRun.includes("字幕密度")) {
    throw new Error("missing structured packaging plan details");
  }

  await page.getByRole("button", { name: "全选缺口" }).click();
  await page.getByRole("button", { name: "加入需求单" }).click();
  await page.getByRole("button", { name: "移出需求单" }).first().click();
  const remainingAfterRemove = await page.getByRole("button", { name: "移出需求单" }).count();
  if (remainingAfterRemove < 1) {
    throw new Error("expected request sheet to keep remaining tasks after single remove");
  }
  await page.getByRole("button", { name: "加入需求单" }).click();
  await page.getByRole("button", { name: "已拍" }).first().click();
  await page.getByLabel("卖点展开 上传补拍素材").setInputFiles(materialFixturePath);
  await page.waitForTimeout(800);
  const bodyTextAfterMaterialUpload = await page.locator("body").innerText();
  if (!bodyTextAfterMaterialUpload.includes("补拍素材已绑定") || !bodyTextAfterMaterialUpload.includes("已上传 material-")) {
    throw new Error("missing uploaded material binding state");
  }
  if (!bodyTextAfterMaterialUpload.includes("素材适配分析") || !bodyTextAfterMaterialUpload.includes("推荐槽位：Hook")) {
    throw new Error("missing uploaded material fit analysis");
  }

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
  if (!rerunBodyText.includes("Gaps: 1")) {
    throw new Error("missing reduced gap count after delivered material rerun");
  }
  if (!rerunBodyText.includes("已补齐素材")) {
    throw new Error("missing delivered material state after rerun");
  }
  if (!rerunBodyText.includes("素材来源") || !rerunBodyText.includes("用户上传")) {
    throw new Error("missing uploaded material source explanation after rerun");
  }
  if (!rerunBodyText.includes("fixture 匹配")) {
    throw new Error("missing fixture material source explanation after rerun");
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
  await page.getByLabel("搜索记录").fill("高点击版");
  await page.waitForTimeout(300);
  const bodyTextAfterSearchHit = await page.locator("body").innerText();
  if (!bodyTextAfterSearchHit.includes("巷口手作咖啡 高点击版结构迁移方案")) {
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
  if (!bodyTextAfterPin.includes("Variant: 高点击版") || !bodyTextAfterPin.includes("高点击版")) {
    throw new Error("missing selected output variant state");
  }
  if (!bodyTextAfterPin.includes("当前预览")) {
    throw new Error("missing current run marker in recent run comparison");
  }
  if (!bodyTextAfterPin.includes("Hook：") || !bodyTextAfterPin.includes("CTA：")) {
    throw new Error("missing hook and cta summaries in recent run comparison");
  }
  if (!bodyTextAfterPin.includes("前 2 秒抛出反差问题")) {
    throw new Error("missing high-click hook text in recent run comparison");
  }
  await page.getByRole("button", { name: "设为首选版本" }).click();
  await page.waitForTimeout(500);
  const bodyTextAfterPreferred = await page.locator("body").innerText();
  if (!bodyTextAfterPreferred.includes("首选版本") || !bodyTextAfterPreferred.includes("Preferred: 首选版本")) {
    throw new Error("missing preferred run state");
  }
  const firstCurrentRunMatch = bodyTextAfterPin.match(/Run:\s*(demo-[a-z0-9]{8})/);
  if (!firstCurrentRunMatch) {
    throw new Error("missing current run id");
  }
  const templateTitle = `${firstCurrentRunMatch[1]} 结构模板`;
  await page.getByLabel("模板名称").fill(templateTitle);
  await page.getByRole("textbox", { name: "模板标签", exact: true }).fill("餐饮，本地生活");
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
  if (!bodyTextAfterTemplateSave.includes("标签 餐饮") || !bodyTextAfterTemplateSave.includes("标签 本地生活")) {
    throw new Error("missing saved template tags");
  }
  await page.getByLabel("按模板标签筛选").fill("本地生活");
  await page.waitForTimeout(500);
  const bodyTextAfterTemplateTagFilter = await page.locator("body").innerText();
  if (!bodyTextAfterTemplateTagFilter.includes(templateTitle)) {
    throw new Error("missing template after tag filter");
  }
  await page.getByLabel("按模板标签筛选").fill("");
  await page.waitForTimeout(300);
  const editedTemplateTitle = `${firstCurrentRunMatch[1]} 夜咖模板`;
  await page.getByLabel("编辑模板标题").fill(editedTemplateTitle);
  await page.getByLabel("模板节奏摘要").fill("5-7-5-3 的夜场节奏");
  await page.getByLabel("编辑模板标签").fill("餐饮，本地生活，夜咖");
  await page.getByLabel("Hook 时长").fill("5");
  await page.getByLabel("Hook 素材要求").fill("夜景开场镜头");
  await page.getByRole("button", { name: "保存模板修改" }).click();
  await page.waitForTimeout(500);
  const bodyTextAfterTemplateEdit = await page.locator("body").innerText();
  if (!bodyTextAfterTemplateEdit.includes(editedTemplateTitle)) {
    throw new Error("missing edited template title");
  }
  if (!bodyTextAfterTemplateEdit.includes("标签 夜咖")) {
    throw new Error("missing edited template tag");
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
  if (!firstJsonText.includes("\"variant\": \"high_click\"")) {
    throw new Error("missing persisted output variant in exported json");
  }

  await page.getByRole("button", { name: "生成迁移 demo" }).click();
  await page.waitForTimeout(3000);
  const bodyTextAfterTemplateRun = await page.locator("body").innerText();
  if (!bodyTextAfterTemplateRun.includes(`Template: ${editedTemplateTitle}`)) {
    throw new Error("missing applied template state on current run");
  }
  if (!bodyTextAfterTemplateRun.includes("Variant: 高点击版")) {
    throw new Error("missing applied output variant on current run");
  }
  if (!bodyTextAfterTemplateRun.includes("Tags: 餐饮 / 本地生活 / 夜咖")) {
    throw new Error("missing inherited template tags on current run");
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
  await page.getByLabel("按 run 标签筛选").fill("夜咖");
  await page.waitForTimeout(500);
  const bodyTextAfterRunTagFilter = await page.locator("body").innerText();
  if (!bodyTextAfterRunTagFilter.includes("标签 夜咖") || !bodyTextAfterRunTagFilter.includes(`模板 ${editedTemplateTitle}`)) {
    throw new Error("missing tag-filtered run badge");
  }
  await page.getByLabel("按 run 标签筛选").fill("");
  await page.waitForTimeout(300);
  await page.getByRole("button", { name: "回退到这一版" }).first().click();
  await page.waitForTimeout(500);
  const bodyTextAfterRollback = await page.locator("body").innerText();
  if (!bodyTextAfterRollback.includes(templateTitle)) {
    throw new Error("missing rolled back template title");
  }
  const forkedTemplateTitle = `${templateTitle} 副本`;
  const baseTemplateCard = page
    .locator("article")
    .filter({ hasText: templateTitle })
    .filter({ has: page.getByRole("button", { name: "复制模板" }) })
    .first();
  await baseTemplateCard.getByRole("button", { name: "复制模板" }).click();
  await page.waitForTimeout(500);
  const bodyTextAfterFork = await page.locator("body").innerText();
  if (!bodyTextAfterFork.includes(forkedTemplateTitle)) {
    throw new Error("missing forked template title");
  }
  await page.getByRole("button", { name: "生成迁移 demo" }).click();
  await page.waitForTimeout(3000);
  const bodyTextAfterRollbackRun = await page.locator("body").innerText();
  if (!bodyTextAfterRollbackRun.includes(`Template: ${forkedTemplateTitle}`)) {
    throw new Error("missing rolled back template state on current run");
  }

  const [jsonDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "导出 run JSON" }).click(),
  ]);
  const jsonDownloadPath = await jsonDownload.path();
  const jsonText = jsonDownloadPath ? await fs.readFile(jsonDownloadPath, "utf-8") : "";
  if (!jsonText.includes(`\"template_title\": \"${forkedTemplateTitle}\"`)) {
    throw new Error("missing persisted template title in exported json");
  }
  if (!jsonText.includes("\"template_tags\": [") || !jsonText.includes("\"夜咖\"")) {
    throw new Error("missing persisted template tags in exported json");
  }
  if (!jsonText.includes("\"variant\": \"high_click\"")) {
    throw new Error("missing persisted output variant in exported templated json");
  }

  const [zipDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "下载结果包" }).click(),
  ]);
  const zipDownloadPath = await zipDownload.path();
  if (!zipDownloadPath) {
    throw new Error("missing exported run package path");
  }
  const zipList = spawnSync("unzip", ["-l", zipDownloadPath], { encoding: "utf-8" });
  if (zipList.status !== 0 || !zipList.stdout.includes("run.json") || !zipList.stdout.includes("material-sources.txt") || !zipList.stdout.includes("material-analysis.txt") || !zipList.stdout.includes("packaging-plan.txt") || !zipList.stdout.includes("final-demo.mp4")) {
    throw new Error("missing expected files in exported run package");
  }
  const sourceText = spawnSync("unzip", ["-p", zipDownloadPath, "material-sources.txt"], { encoding: "utf-8" }).stdout;
  if (!sourceText.includes("素材来源说明") || !sourceText.includes("fixture 匹配")) {
    throw new Error("missing material source explanation in exported run package");
  }
  const materialAnalysisText = spawnSync("unzip", ["-p", zipDownloadPath, "material-analysis.txt"], { encoding: "utf-8" }).stdout;
  if (!materialAnalysisText.includes("真实素材适配说明") || !materialAnalysisText.includes("推荐槽位：Hook")) {
    throw new Error("missing material analysis explanation in exported run package");
  }
  const packagingPlanText = spawnSync("unzip", ["-p", zipDownloadPath, "packaging-plan.txt"], { encoding: "utf-8" }).stdout;
  if (!packagingPlanText.includes("画面包装方案") || !packagingPlanText.includes("标题卡片") || !packagingPlanText.includes("字幕密度")) {
    throw new Error("missing packaging plan explanation in exported run package");
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
    .filter({ hasText: forkedTemplateTitle })
    .filter({ has: page.getByRole("button", { name: "删除模板" }) })
    .first();
  await templateCard.getByRole("button", { name: "删除模板" }).click();
  await page.waitForTimeout(500);
  if ((await templateCard.count()) !== 0) {
    throw new Error("deleted template card still visible");
  }

  const originalTemplateCard = page
    .locator("article")
    .filter({ hasText: templateTitle })
    .filter({ has: page.getByRole("button", { name: "删除模板" }) })
    .first();
  await originalTemplateCard.getByRole("button", { name: "删除模板" }).click();
  await page.waitForTimeout(500);
  if ((await originalTemplateCard.count()) !== 0) {
    throw new Error("deleted original template card still visible");
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
