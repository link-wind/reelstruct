import React from 'react'

export interface ShotEvidenceViewModel {
  shotIndex: number
  time: string
  frames: Array<{ role: string; time: number; publicUrl: string }>
  ocrTexts: Array<{ text: string; frameIndex: number; frameTime: number; position: string; confidence: number }>
  transcriptTexts: Array<{ text: string; sourceStart: number; sourceEnd: number; overlapRatio: number }>
  visualSummary: string
  textSummary: string
  functionHint: string
  confidence: number
  warnings: string[]
}

export interface AnalysisUnitViewModel {
  unitId: string
  time: string
  duration: number
  shotIndices: number[]
  representativeFrames: Array<{ role: string; time: number; publicUrl: string; shotIndex: number }>
  ocrTexts: Array<{ text: string; frameIndex: number; frameTime: number; position: string; confidence: number }>
  transcriptTexts: Array<{ text: string; sourceStart: number; sourceEnd: number; overlapRatio: number }>
  visualSummary: string
  textSummary: string
  functionHint: string
  confidence: number
  warnings: string[]
  shots: ShotEvidenceViewModel[]
}

export default function ShotEvidencePanel({
  units = [],
  shots,
  warnings = [],
}: {
  units?: AnalysisUnitViewModel[]
  shots: ShotEvidenceViewModel[]
  warnings?: string[]
}) {
  return (
    <article className="insight-panel soft-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">Shot evidence</p>
          <h3>镜头证据</h3>
        </div>
        <span className="status">
          {units.length ? `${units.length} units / ${shots.length} shots` : shots.length ? `${shots.length} shots` : '等待生成'}
        </span>
      </div>

      {warnings.length ? (
        <div className="warning-list">
          {warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}

      {units.length ? (
        <div className="shot-evidence-list">
          {units.map((unit) => (
            <section className="analysis-unit-item" key={unit.unitId}>
              <div className="shot-evidence-head">
                <strong>{unit.unitId}</strong>
                <span>
                  {unit.time} · shots {unit.shotIndices.join(', ')}
                </span>
              </div>
              {unit.representativeFrames.length ? (
                <div className="node-keyframes">
                  {unit.representativeFrames.map((frame) => (
                    <figure key={`${unit.unitId}-${frame.shotIndex}-${frame.role}-${frame.time}`}>
                      <img src={frame.publicUrl} alt={`${unit.unitId} shot ${frame.shotIndex} ${frame.role}`} />
                      <figcaption>
                        shot {frame.shotIndex} · {frame.role} · {frame.time.toFixed(2)}s
                      </figcaption>
                    </figure>
                  ))}
                </div>
              ) : null}
              <p>{unit.visualSummary || '等待分析单元理解结果'}</p>
              {unit.textSummary ? <small>{unit.textSummary}</small> : null}
              <div className="analysis-unit-meta">
                <span>包含 {unit.shotIndices.length} 个原始镜头</span>
                <span>置信度 {Math.round(unit.confidence * 100)}%</span>
                {unit.functionHint ? <span>{unit.functionHint}</span> : null}
              </div>
              {unit.ocrTexts.length ? (
                <div className="shot-text-evidence-list" aria-label={`${unit.unitId} OCR`}>
                  <strong>OCR 可见文字</strong>
                  {unit.ocrTexts.slice(0, 4).map((item) => (
                    <div key={`${unit.unitId}-ocr-${item.frameIndex}-${item.frameTime}-${item.text}`}>
                      <span>
                        frame {item.frameIndex} · {item.frameTime.toFixed(2)}s · {Math.round(item.confidence * 100)}%
                      </span>
                      <p>{item.text}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {unit.transcriptTexts.length ? (
                <div className="shot-text-evidence-list" aria-label={`${unit.unitId} ASR`}>
                  <strong>ASR 口播文本</strong>
                  {unit.transcriptTexts.slice(0, 4).map((item) => (
                    <div key={`${unit.unitId}-asr-${item.sourceStart}-${item.sourceEnd}-${item.text}`}>
                      <span>
                        {item.sourceStart.toFixed(2)}s - {item.sourceEnd.toFixed(2)}s
                      </span>
                      <p>{item.text}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {unit.warnings.length ? (
                <div className="warning-list">
                  {unit.warnings.map((warning) => (
                    <span key={warning}>{warning}</span>
                  ))}
                </div>
              ) : null}
              <details className="analysis-unit-shots">
                <summary>查看原始 shots</summary>
                <div>
                  {unit.shots.map((shot) => (
                    <span key={shot.shotIndex}>
                      Shot {shot.shotIndex} · {shot.time}
                    </span>
                  ))}
                </div>
              </details>
            </section>
          ))}
        </div>
      ) : shots.length ? (
        <div className="shot-evidence-list">
          {shots.map((shot) => (
            <section className="shot-evidence-item" key={shot.shotIndex}>
              <div className="shot-evidence-head">
                <strong>Shot {shot.shotIndex}</strong>
                <span>{shot.time}</span>
              </div>
              {shot.frames.length ? (
                <div className="node-keyframes">
                  {shot.frames.map((frame) => (
                    <figure key={`${shot.shotIndex}-${frame.role}-${frame.time}`}>
                      <img src={frame.publicUrl} alt={`Shot ${shot.shotIndex} ${frame.role}`} />
                      <figcaption>
                        {frame.role} · {frame.time.toFixed(2)}s
                      </figcaption>
                    </figure>
                  ))}
                </div>
              ) : null}
              <p>{shot.visualSummary || '等待镜头理解结果'}</p>
              {shot.ocrTexts.length ? (
                <div className="shot-text-evidence-list" aria-label={`Shot ${shot.shotIndex} OCR`}>
                  <strong>OCR 可见文字</strong>
                  {shot.ocrTexts.map((item) => (
                    <div key={`${shot.shotIndex}-ocr-${item.frameIndex}-${item.frameTime}-${item.text}`}>
                      <span>
                        frame {item.frameIndex} · {item.frameTime.toFixed(2)}s · {Math.round(item.confidence * 100)}%
                      </span>
                      <p>{item.text}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {shot.transcriptTexts.length ? (
                <div className="shot-text-evidence-list" aria-label={`Shot ${shot.shotIndex} ASR`}>
                  <strong>ASR 口播文本</strong>
                  {shot.transcriptTexts.map((item) => (
                    <div key={`${shot.shotIndex}-asr-${item.sourceStart}-${item.sourceEnd}`}>
                      <span>
                        {item.sourceStart.toFixed(2)}s - {item.sourceEnd.toFixed(2)}s
                      </span>
                      <p>{item.text}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {shot.textSummary ? <small>{shot.textSummary}</small> : null}
              {shot.functionHint ? <span className="status">{shot.functionHint}</span> : null}
              {shot.warnings.length ? (
                <div className="warning-list">
                  {shot.warnings.map((warning) => (
                    <span key={warning}>{warning}</span>
                  ))}
                </div>
              ) : null}
            </section>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>还没有镜头证据</strong>
          <span>上传并生成结构后，这里会展示每个 shot 的画面、文本和 AI 理解。</span>
        </div>
      )}
    </article>
  )
}
