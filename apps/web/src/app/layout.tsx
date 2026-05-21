import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ReelStruct',
  description: 'AI video structure transfer engine',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
