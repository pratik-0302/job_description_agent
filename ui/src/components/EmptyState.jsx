import { motion } from "framer-motion";

export default function EmptyState({ icon, title, subtitle, action }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col items-center justify-center py-20 text-center"
    >
      <div className="text-5xl mb-4 opacity-30">{icon}</div>
      <h3 className="text-white/50 font-semibold text-base mb-1">{title}</h3>
      {subtitle && <p className="text-white/25 text-sm max-w-xs">{subtitle}</p>}
      {action && <div className="mt-6">{action}</div>}
    </motion.div>
  );
}
