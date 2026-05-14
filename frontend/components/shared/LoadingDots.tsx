export default function LoadingDots({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-white/60 text-sm font-oxanium">
      {label && <span className="mr-1">{label}</span>}
      {[0, 1, 2].map(i => (
        <span key={i}
          className="w-1.5 h-1.5 rounded-full bg-brand-blue animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  )
}
