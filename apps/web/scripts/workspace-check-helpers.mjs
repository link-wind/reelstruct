export function hasVisibleResultSuccess({
  bodyText = "",
  stageStripText = "",
  hasResultVideo = false,
  hasDownloadButton = false,
  resultStatusText = "",
}) {
  if (hasResultVideo) return true;
  if (hasDownloadButton) return true;
  if (resultStatusText && resultStatusText !== "等待生成") return true;

  const text = `${bodyText}\n${stageStripText}`;
  return (
    text.includes("下载结果包") ||
    text.includes("任务编号：") ||
    text.includes("素材来源验证") ||
    text.includes("结果已生成") ||
    text.includes("迁移任务已完成")
  );
}

