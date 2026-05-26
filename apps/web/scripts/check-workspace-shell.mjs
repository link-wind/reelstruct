import { access } from "node:fs/promises";
import { fileURLToPath } from "node:url";

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
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
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
  const workspaceText = await page.locator("body").innerText();
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
  if (!workspaceText.includes("结构拆解解释")) {
    await page.getByRole("tab", { name: "打开结构拆解标签" }).click();
    const structureTabText = await page.locator("body").innerText();
    if (!structureTabText.includes("结构拆解解释")) {
      throw new Error("workspace analysis summary panel is missing");
    }
    await page.getByRole("tab", { name: "打开样例解析标签" }).click();
  }
  if (!workspaceText.includes("素材缺口与补全")) {
    await page.getByRole("tab", { name: "打开素材补全标签" }).click();
    const materialTabText = await page.locator("body").innerText();
    if (!materialTabText.includes("素材缺口与补全")) {
      throw new Error("workspace material gap panel is missing");
    }
    await page.getByRole("tab", { name: "打开样例解析标签" }).click();
  }
  if (!workspaceText.includes("迁移解释")) {
    await page.getByRole("tab", { name: "打开结构拆解标签" }).click();
    const structureTabText = await page.locator("body").innerText();
    if (!structureTabText.includes("迁移解释")) {
      throw new Error("workspace transfer explanation panel is missing");
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
  if (!uploadedWorkspaceText.includes("Shot ")) {
    throw new Error("workspace sample keyframes are missing after upload");
  }
  await page.getByRole("tab", { name: "打开镜头证据标签" }).click();
  const uploadedEvidenceText = await page.locator("body").innerText();
  if (!uploadedEvidenceText.includes("镜头证据") || !uploadedEvidenceText.includes("Shot ")) {
    throw new Error("workspace shot evidence tab is missing uploaded shot evidence");
  }
  await page.getByRole("tab", { name: "打开样例解析标签" }).click();

  await page.waitForTimeout(1500);
  let generatedWorkspaceText = "";
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    await page.locator("#generateDemo").click();
    await page.waitForFunction(() => {
      const text = document.body.innerText;
      return text.includes("迁移任务已完成") || text.includes("生成失败");
    }, null, { timeout: 120000 });
    generatedWorkspaceText = await page.locator("body").innerText();
    if (!generatedWorkspaceText.includes("生成失败")) {
      break;
    }
    if (attempt === 1) {
      await page.waitForTimeout(2000);
    }
  }
  if (generatedWorkspaceText.includes("生成失败")) {
    throw new Error(`workspace fixture structure generation failed:\n${generatedWorkspaceText.slice(0, 2400)}`);
  }
  await page.getByRole("tab", { name: "打开结构拆解标签" }).click();
  await page.waitForFunction(() => document.body.innerText.includes("节点证据"), null, { timeout: 10000 });
  generatedWorkspaceText = await page.locator("body").innerText();
  if (!generatedWorkspaceText.includes("节点证据")) {
    throw new Error(`workspace selected structure node evidence panel is missing after generation:\n${generatedWorkspaceText.slice(0, 3200)}`);
  }
  if (!generatedWorkspaceText.includes("样例证据") || !generatedWorkspaceText.includes("引用镜头")) {
    throw new Error("workspace selected structure node evidence details are missing after generation");
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
