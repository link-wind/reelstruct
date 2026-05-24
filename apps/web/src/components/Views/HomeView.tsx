import React, { useState } from 'react';

interface HomeViewProps {
  onStartMigration: (prompt: string) => void;
}

export default function HomeView({ onStartMigration }: HomeViewProps) {
  const [prompt, setPrompt] = useState("");

  const handleExampleClick = (exampleText: string) => {
    setPrompt(exampleText);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onStartMigration(prompt.trim());
  };

  return (
    <section className="view home" id="homeView" data-active="true">
      <div className="home-shell">
        <div className="home-copy">
          <p className="eyebrow">产品入口</p>
          <h1>把参考视频变成可执行剪辑结构。</h1>
          <p className="home-lead">
            输入一句任务，直接进入工作台开始拆解结构、映射素材和输出迁移计划。
          </p>
        </div>

        <form className="prompt-panel soft-card" id="homeForm" onSubmit={handleSubmit}>
          <textarea
            id="homePrompt"
            aria-label="输入视频结构迁移任务"
            placeholder="分析这个 42 秒参考广告的节奏，把 Hook、痛点、演示、证明和 CTA 迁移到我上传的产品素材里，目标输出 35 秒竖版短视频。"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          ></textarea>
          <div className="prompt-footer">
            <span>支持参考视频、素材池描述和剪辑约束。</span>
            <button className="btn btn-primary" type="submit">
              进入工作台
            </button>
          </div>
        </form>

        <div className="examples" aria-label="示例任务">
          <button
            className="example"
            type="button"
            onClick={() => handleExampleClick("把参考视频的五段式结构迁移到新品演示素材里，保留 2 秒 Hook 和轻 CTA。")}
          >
            五段式广告迁移
          </button>
          <button
            className="example"
            type="button"
            onClick={() => handleExampleClick("分析一个爆款 Reels 的镜头节奏，把开场反差、演示转场和字幕断句迁移到我的素材。")}
          >
            爆款节奏复刻
          </button>
          <button
            className="example"
            type="button"
            onClick={() => handleExampleClick("把竞品视频拆成可审查结构节点，再用我方素材生成一版 30 秒竖屏剪辑计划。")}
          >
            竞品结构拆解
          </button>
        </div>

      </div>
    </section>
  );
}
