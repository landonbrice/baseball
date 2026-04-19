export default function Lede({ children, maxWidth = '720px' }) {
  return (
    <div
      className="bg-parchment border-l-[3px] border-maroon py-2.5 pl-3.5 pr-3 rounded-r-[3px] font-serif italic text-body text-graphite"
      style={{ maxWidth }}
    >
      {children}
    </div>
  )
}
