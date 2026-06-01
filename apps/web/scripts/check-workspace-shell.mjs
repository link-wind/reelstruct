import { access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { hasVisibleResultSuccess } from "./workspace-check-helpers.mjs";

const fallbackPlaywrightModule =
  process.env.PLAYWRIGHT_MODULE ||
  "file:///Users/linkwind/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";

let playwright;

try {
  playwright = await import("playwright");
} catch {
  playwright = await import(fallbackPlaywrightModule);
}

const { chromium } = playwright;

const baseUrl = process.env.BASE_URL || "http://127.0.0.1:3000";
const defaultChromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const fixtureVideoPath = fileURLToPath(new URL("../../../fixtures/vid_001.mp4", import.meta.url));

async function waitForStageText(page, matcher, { timeout = 30000, interval = 1000 } = {}) {
  const startedAt = Date.now();
  let lastText = "";
  while (Date.now() - startedAt < timeout) {
    lastText = await page.locator('[data-agent-stage-strip="true"]').innerText().catch(() => "");
    if (matcher(lastText)) {
      return lastText;
    }
    await page.waitForTimeout(interval);
  }
  throw new Error(`stage strip timeout after ${timeout}ms\n${lastText}`);
}

async function waitForVisibleResultSuccess(page, { timeout = 150000, interval = 1000 } = {}) {
  const startedAt = Date.now();
  let lastBodyText = "";
  let lastStageStrip = "";
  let lastResultStatus = "";

  while (Date.now() - startedAt < timeout) {
    lastBodyText = await page.locator("body").innerText().catch(() => "");
    lastStageStrip = await page.locator('[data-agent-stage-strip="true"]').innerText().catch(() => "");
    lastResultStatus = await page.locator(".insight-panel .status").first().innerText().catch(() => "");
    const hasResultVideo = (await page.locator("video.result-video").count().catch(() => 0)) > 0;
    const hasDownloadButton = (await page.getByRole("link", { name: "下载结果包" }).count().catch(() => 0)) > 0;

    if (
      hasVisibleResultSuccess({
        bodyText: lastBodyText,
        stageStripText: lastStageStrip,
        hasResultVideo,
        hasDownloadButton,
        resultStatusText: lastResultStatus,
      })
    ) {
      return {
        bodyText: lastBodyText,
        stageStripText: lastStageStrip,
        resultStatusText: lastResultStatus,
        hasResultVideo,
        hasDownloadButton,
      };
    }

    await page.waitForTimeout(interval);
  }

  throw new Error(
    `workspace result output did not become visible within ${timeout}ms\n${lastBodyText.slice(0, 2400)}`,
  );
}

async function openOutputTab(page) {
  await page.getByRole("tab", { name: "打开结果验证标签" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("结果验证"), null, { timeout: 10000 });
}

async function resolveExecutablePath() {
  if (process.env.CHROME_PATH) {
    return process.env.CHROME_PATH;
  }

  try {
    await access(defaultChromePath);
    return defaultChromePath;
  } catch {
    return undefined;
  }
}

const executablePath = await resolveExecutablePath();

const browser = await chromium.launch(
  executablePath
    ? {
        headless: true,
        executablePath,
      }
    : {
        headless: true,
      },
);

try {
  const badHomepageRequests = [];
  const browserConsoleLogs = [];
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  page.on("console", (message) => {
    browserConsoleLogs.push(`[${message.type()}] ${message.text()}`);
  });
  page.on("response", (response) => {
    const url = response.url();
    if (url.includes("/api/runs") || url.includes("/api/templates")) {
      badHomepageRequests.push(`${response.status()} ${url}`);
    }
  });

  await page.goto(baseUrl, { waitUntil: "networkidle" });
  const homeText = await page.locator("body").innerText();
  if (!homeText.includes("ReelStruct")) {
    throw new Error("homepage is missing ReelStruct brand");
  }
  if (homeText.includes("CutFlow AI")) {
    throw new Error("homepage still shows CutFlow AI brand");
  }
  if (badHomepageRequests.length > 0) {
    throw new Error(`homepage unexpectedly requested run/template APIs: ${badHomepageRequests.join(", ")}`);
  }

  const promptText = "把参考视频迁移到新品空气炸锅，突出少油、快手和易清洁。";
  await page.getByLabel("输入视频结构迁移任务").fill(promptText);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await page.waitForTimeout(500);
  const conversationPanel = page.locator('[aria-label="智能助手对话区"]');
  await conversationPanel.waitFor({ state: "visible", timeout: 10000 });
  const composerInput = page.getByLabel("继续向智能助手输入指令");
  await composerInput.waitFor({ state: "visible", timeout: 10000 });
  const confirmationMenu = page.locator('[data-agent-confirmation-menu="true"]');
  const stageStrip = page.locator('[data-agent-stage-strip="true"]');
  const workspaceText = await page.locator("body").innerText();
  if (!workspaceText.includes("请先上传参考视频，上传后我会自动生成执行计划。")) {
    throw new Error("workspace should wait for sample upload before auto planning");
  }
  if (!workspaceText.includes("目标内容")) {
    throw new Error("workspace target brief panel is missing");
  }
  for (const tabLabel of ["样例解析", "镜头证据", "结构拆解", "素材补全", "结果验证"]) {
    if (!workspaceText.includes(tabLabel)) {
      throw new Error(`workspace tab is missing: ${tabLabel}`);
    }
  }
  if (!workspaceText.includes(promptText)) {
    throw new Error("workspace target brief does not show the homepage prompt");
  }
  if (!workspaceText.includes("还没有结构结果")) {
    await page.getByRole("tab", { name: "打开结构拆解标签" }).click();
    const structureTabText = await page.locator("body").innerText();
    if (!structureTabText.includes("还没有结构结果")) {
      throw new Error("workspace empty structure state is missing");
    }
    await page.getByRole("tab", { name: "打开样例解析标签" }).click();
  }
  if (!workspaceText.includes("样例解析概览")) {
    throw new Error("workspace sample analysis overview panel is missing");
  }
  if (!workspaceText.includes("镜头证据")) {
    await page.getByRole("tab", { name: "打开镜头证据标签" }).click();
    const evidenceTabText = await page.locator("body").innerText();
    if (!evidenceTabText.includes("还没有镜头证据")) {
      throw new Error("workspace shot evidence empty state is missing");
    }
    await page.getByRole("tab", { name: "打开样例解析标签" }).click();
  }
  if (!workspaceText.includes("上传样例后，这里会展示视频基础信息、节奏指标和关键帧证据")) {
    throw new Error("workspace sample analysis empty state is missing");
  }
  if (workspaceText.includes("视觉反差 Hook")) {
    throw new Error("workspace still shows mock structure node before generation");
  }
  if (!workspaceText.includes("素材缺口与补全")) {
    await page.getByRole("tab", { name: "打开素材补全标签" }).click();
    const materialTabText = await page.locator("body").innerText();
    if (!materialTabText.includes("素材缺口与补全")) {
      throw new Error("workspace material gap panel is missing");
    }
    if (!materialTabText.includes("素材库节点")) {
      throw new Error("workspace material library panel is missing");
    }
    await page.getByRole("tab", { name: "打开样例解析标签" }).click();
  }
  if (!workspaceText.includes("结果验证")) {
    await page.getByRole("tab", { name: "打开结果验证标签" }).click();
    const outputTabText = await page.locator("body").innerText();
    if (!outputTabText.includes("结果验证")) {
      throw new Error("workspace result preview panel is missing");
    }
    await page.getByRole("tab", { name: "打开样例解析标签" }).click();
  }

  await page.getByLabel("上传输入视频").setInputFiles(fixtureVideoPath);
  await page.waitForFunction(() => {
    const text = document.body.innerText;
    return text.includes("样例已上传") || text.includes("上传失败");
  }, null, { timeout: 60000 });
  const uploadedWorkspaceText = await page.locator("body").innerText();
  if (uploadedWorkspaceText.includes("上传失败")) {
    throw new Error("workspace fixture video upload failed");
  }
  if (!uploadedWorkspaceText.includes("转写/语音概览")) {
    throw new Error("workspace sample transcript overview is missing after upload");
  }
  if (!uploadedWorkspaceText.includes("平均镜头") || !uploadedWorkspaceText.includes("最快窗口")) {
    throw new Error("workspace sample rhythm metrics are missing after upload");
  }
  if (!uploadedWorkspaceText.includes("镜头 ")) {
    throw new Error("workspace sample keyframes are missing after upload");
  }
  await page.getByRole("tab", { name: "打开镜头证据标签" }).click();
  const uploadedEvidenceText = await page.locator("body").innerText();
  if (!uploadedEvidenceText.includes("镜头证据") || !uploadedEvidenceText.includes("镜头 ")) {
    throw new Error("workspace shot evidence tab is missing uploaded shot evidence");
  }
  await page.getByRole("tab", { name: "打开样例解析标签" }).click();
  await confirmationMenu.waitFor({ state: "visible", timeout: 10000 });
  await stageStrip.waitFor({ state: "visible", timeout: 10000 });
  await page.waitForFunction(() => {
    const text = document.body.innerText;
    return text.includes("等待确认：开始执行计划？") || text.includes("等待确认后开始执行");
  }, null, { timeout: 10000 });

  await page.waitForTimeout(1500);
  await page.locator("#generateDemo").click();
  const initialStageStrip = await page.locator('[data-agent-stage-strip="true"]').innerText().catch(() => "");
  console.log(`[workspace-check] stage strip after click:\n${initialStageStrip}`);
  await waitForStageText(page, (text) =>
    text.includes("正在分析结构") ||
    text.includes("正在生成结构预览") ||
    text.includes("结构预览已生成") ||
    text.includes("正在补充 OCR") ||
    text.includes("正在生成 OCR 证据") ||
    text.includes("正在补充 ASR") ||
    text.includes("正在生成 ASR 证据") ||
    text.includes("正在刷新结构预览") ||
    text.includes("正在生成结果") ||
    text.includes("正在执行迁移任务") ||
    text.includes("迁移任务已完成") ||
    text.includes("生成失败"),
  );
  console.log(`[workspace-check] stage strip during run:\n${await page.locator('[data-agent-stage-strip="true"]').innerText().catch(() => "")}`);
  const conversationTextAfterWait = await page.locator('[data-agent-conversation-panel="true"]').innerText().catch(() => "");
  console.log(`[workspace-check] conversation after wait:\n${conversationTextAfterWait.slice(0, 2000)}`);
  const flowLogs = browserConsoleLogs
    .filter((line) => line.includes("[agent-flow]"))
    .slice(-30);
  console.log(`[workspace-check] browser flow logs:\n${flowLogs.join("\n")}`);
  await openOutputTab(page);
  const visibleResult = await waitForVisibleResultSuccess(page, { timeout: 150000, interval: 1000 });
  const generatedWorkspaceText = visibleResult.bodyText;
  if (generatedWorkspaceText.includes("生成失败")) {
    throw new Error(`workspace fixture structure generation failed:\n${generatedWorkspaceText.slice(0, 2400)}`);
  }
  await page.getByRole("tab", { name: "打开结构拆解标签" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("段落时间线"), null, { timeout: 10000 });
  let generatedWorkspaceTextAfterStructure = await page.locator("body").innerText();
  for (const structureLabel of ["段落结构", "节奏结构", "包装结构"]) {
    if (!generatedWorkspaceTextAfterStructure.includes(structureLabel)) {
      throw new Error(`workspace structure subtab is missing: ${structureLabel}`);
    }
  }
  await page.getByRole("tab", { name: "查看节奏结构" }).click();
  const rhythmTabText = await page.locator("body").innerText();
  for (const rhythmLabel of ["节奏波形", "镜头切换频率", "段落快慢变化", "高潮位置", "节奏爆点"]) {
    if (!rhythmTabText.includes(rhythmLabel)) {
      throw new Error(`workspace rhythm chart is missing label: ${rhythmLabel}`);
    }
  }
  await page.getByRole("tab", { name: "查看段落结构" }).click();
  generatedWorkspaceTextAfterStructure = await page.locator("body").innerText();
  for (const timelineLabel of ["段落时间线", "关键镜头", "查看段落证据"]) {
    if (!generatedWorkspaceTextAfterStructure.includes(timelineLabel)) {
      throw new Error(`workspace segment timeline is missing label: ${timelineLabel}`);
    }
  }
  for (const graphLabel of ["图谱结构概要", "段落 → 分析单元 → 镜头"]) {
    if (!generatedWorkspaceTextAfterStructure.includes(graphLabel)) {
      throw new Error(`workspace AI graph presentation is missing label: ${graphLabel}`);
    }
  }
  const openNodeEvidenceDetails = await page.locator(".node-evidence-details[open]").count();
  if (openNodeEvidenceDetails > 0) {
    throw new Error("workspace node evidence details should be collapsed by default");
  }
  await page.locator(".node-evidence-details summary").first().click();
  const expandedStructureText = await page.locator("body").innerText();
  if (!expandedStructureText.includes("样例证据") || !expandedStructureText.includes("引用镜头")) {
    throw new Error("workspace selected structure node evidence details are missing after expanding");
  }

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
  await mobile.goto(baseUrl, { waitUntil: "networkidle" });
  await mobile.getByRole("button", { name: "进入工作台" }).click();
  await mobile.waitForTimeout(500);
  const metrics = await mobile.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  if (metrics.scrollWidth > metrics.width + 1) {
    throw new Error(`mobile viewport overflows horizontally: ${metrics.scrollWidth} > ${metrics.width}`);
  }

  console.log("WORKSPACE_SHELL_OK=1");
} finally {
  await browser.close();
}
