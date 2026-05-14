interface ScoreBadgeProps { score: number; passed: boolean }

export default function ScoreBadge({ score, passed }: ScoreBadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full
      text-sm font-medium font-oxanium
      ${passed
        ? 'bg-success/20 text-green-400 border border-success/30'
        : 'bg-error/20 text-red-400 border border-error/30'
      }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${passed ? 'bg-green-400' : 'bg-red-400'}`} />
      {score}/100 {passed ? 'PASS' : 'FAIL'}
    </span>
  )
}
