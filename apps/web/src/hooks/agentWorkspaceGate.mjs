export function shouldAutoPlanAfterSampleUpload({
  hasSampleUpload,
  prompt,
  agentStatus,
  hasPlan,
}) {
  return hasSampleUpload && prompt.trim().length > 0 && agentStatus === 'idle' && !hasPlan
}
