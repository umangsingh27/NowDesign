'use client'
import { ReactNode } from 'react'
import clsx from 'clsx'

interface GlassCardProps {
  children: ReactNode
  className?: string
  theme?: 'dark' | 'light'
  padding?: 'sm' | 'md' | 'lg' | 'none'
}

export default function GlassCard({
  children, className, theme = 'dark', padding = 'md',
}: GlassCardProps) {
  const padMap = { none: '', sm: 'p-4', md: 'p-6', lg: 'p-8' }
  return (
    <div className={clsx(
      'rounded-2xl',
      padMap[padding],
      theme === 'dark'
        ? 'bg-black/60 border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.4)]'
        : 'bg-white/70 border border-black/10 shadow-[0_8px_32px_rgba(0,0,0,0.12)]',
      'backdrop-blur-md',
      className,
    )}>
      {children}
    </div>
  )
}
