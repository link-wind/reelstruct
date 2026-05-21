const workflow = [
  {
    title: '样例输入',
    eyebrow: 'Sample',
    body: '上传爆款样例视频，提取时长、封面、镜头数和字幕概览。',
    meta: '1 个样例视频',
  },
  {
    title: '结构拆解',
    eyebrow: 'Structure',
    body: '拆出 hook、卖点展开、节奏变化和 CTA，形成可迁移模板。',
    meta: '脚本 + 节奏',
  },
  {
    title: '迁移生成',
    eyebrow: 'Transfer',
    body: '把样例结构映射到新主题、商品卖点或用户素材。',
    meta: '脚本 + 时间线',
  },
  {
    title: '缺口补全',
    eyebrow: 'Output',
    body: '标记素材缺口，并用字幕、卡片、素材重排补足表达。',
    meta: '可视化 / demo',
  },
]

const slots = [
  { label: 'Hook', time: '0-3s', status: '已映射', note: '痛点开场 + 快切镜头' },
  { label: '卖点展开', time: '3-16s', status: '待补全', note: '缺少商品特写，使用卖点卡片补足' },
  { label: '使用过程', time: '16-24s', status: '已映射', note: '复用场景素材 + 字幕解释' },
  { label: 'CTA', time: '24-30s', status: '已生成', note: '结尾行动号召和封面文案' },
]

export default function Home() {
  return (
    <main className="min-h-screen bg-paper text-ink">
      <section className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold uppercase tracking-wide text-signal">ReelStruct</p>
            <h1 className="mt-3 text-4xl font-semibold leading-tight sm:text-5xl">
              爆款结构迁移引擎
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
              从样例视频中拆解脚本、节奏和包装结构，再迁移到新的主题、商品或素材里，生成可解释的短视频时间线。
            </p>
          </div>
          <div className="flex gap-3">
            <button className="rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-white">
              新建迁移任务
            </button>
            <button className="rounded-md border border-line bg-white px-4 py-2.5 text-sm font-medium text-ink">
              查看演示样例
            </button>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-5 px-6 py-6 lg:grid-cols-4">
        {workflow.map((item) => (
          <article key={item.title} className="rounded-lg border border-line bg-white p-5 shadow-panel">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {item.eyebrow}
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                {item.meta}
              </span>
            </div>
            <h2 className="mt-4 text-lg font-semibold">{item.title}</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">{item.body}</p>
          </article>
        ))}
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-6 pb-10 lg:grid-cols-[1fr_420px]">
        <div className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <div className="flex items-center justify-between gap-4 border-b border-line pb-4">
            <div>
              <p className="text-sm font-semibold text-signal">结构迁移预览</p>
              <h2 className="mt-1 text-2xl font-semibold">样例结构到新视频时间线</h2>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-mint">
              P0 闭环
            </span>
          </div>

          <div className="mt-5 grid gap-4">
            {slots.map((slot) => (
              <article key={slot.label} className="grid gap-3 rounded-md border border-line p-4 sm:grid-cols-[96px_110px_1fr]">
                <strong>{slot.label}</strong>
                <span className="text-sm text-slate-500">{slot.time}</span>
                <div>
                  <span
                    className={
                      slot.status === '待补全'
                        ? 'text-sm font-semibold text-coral'
                        : 'text-sm font-semibold text-mint'
                    }
                  >
                    {slot.status}
                  </span>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{slot.note}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className="rounded-lg border border-line bg-white p-5 shadow-panel">
          <p className="text-sm font-semibold text-signal">CompositionSpec</p>
          <h2 className="mt-1 text-xl font-semibold">中间视频协议</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            参考 Hyperframes 的时间线描述方式，先用结构化 JSON 表达视频片段、字幕、卡片和补全策略，再交给 FFmpeg 渲染。
          </p>
          <pre className="mt-4 overflow-auto rounded-md bg-slate-950 p-4 text-xs leading-5 text-slate-100">
{`{
  "duration": 30,
  "tracks": [
    {"type": "video", "start": 0},
    {"type": "caption", "start": 1},
    {"type": "card", "start": 6}
  ]
}`}
          </pre>
        </aside>
      </section>
    </main>
  )
}
