const variants = {
  success: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  warning: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  danger:  "bg-red-500/15 text-red-400 border-red-500/25",
  info:    "bg-blue-500/15 text-blue-400 border-blue-500/25",
  purple:  "bg-violet-500/15 text-violet-400 border-violet-500/25",
  default: "bg-white/5 text-white/60 border-white/10",
};

export default function Badge({ children, variant = "default", className = "" }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full border ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
}
