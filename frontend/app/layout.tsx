import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'NowPurchase Design Studio',
  description: 'AI-powered social post generator',
}

export default function RootLayout({
  children,
}: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
