import { motion } from "framer-motion";

export default function StatCard({ icon, label, value, sub, color = "violet", delay = 0 }) {
  const glows = {
    violet: "shadow-[0_0_20px_rgba(124,58,237,0.2)]",
    blue:   "shadow-[0_0_20px_rgba(59,130,246,0.2)]",
    cyan:   "shadow-[0_0_20px_rgba(6,182,212,0.2)]",
    green:  "shadow-[0_0_20px_rgba(16,185,129,0.2)]",
  };
  const accents = {
    violet: "text-violet-400",
    blue:   "text-blue-400",
    cyan:   "text-cyan-400",
    green:  "text-emerald-400",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className={`glass rounded-2xl p-5 flex items-start gap-4 ${glows[color]} hover:scale-[1.02] transition-transform duration-200`}
    >
      <div className={`text-2xl ${accents[color]} shrink-0 mt-0.5`}>{icon}</div>
      <div className="min-w-0">
        <p className="text-white/40 text-xs font-medium uppercase tracking-wider mb-1">{label}</p>
        <p className="text-2xl font-bold text-white leading-none">{value ?? "—"}</p>
        {sub && <p className="text-white/40 text-xs mt-1">{sub}</p>}
      </div>
    </motion.div>
  );
}
