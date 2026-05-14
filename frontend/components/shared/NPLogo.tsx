export default function NPLogo({ size = 32 }: { size?: number }) {
  return (
    <div className="font-urbanist font-bold text-white tracking-tight"
         style={{ fontSize: size * 0.5 }}>
      <span className="text-brand-blue">Now</span>Purchase
    </div>
  )
}
