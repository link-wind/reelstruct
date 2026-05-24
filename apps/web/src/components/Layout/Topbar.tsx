import React from 'react';

interface TopbarProps {
  modeLabel: string;
  onBackHome?: () => void;
  showBack?: boolean;
}

export default function Topbar({ modeLabel, onBackHome, showBack }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand" aria-label="ReelStruct">
          <div className="brand-mark" aria-hidden="true">RS</div>
          <div>
            <strong>ReelStruct</strong>
            <span id="brandSubtitle">短视频结构迁移工作台</span>
          </div>
        </div>
        <div className="top-actions">
          <span id="modeLabel">{modeLabel}</span>
          {showBack && onBackHome ? (
            <button className="btn btn-quiet" id="backHome" type="button" onClick={onBackHome}>
              返回首页
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
