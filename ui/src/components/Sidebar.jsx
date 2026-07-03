import { motion } from "framer-motion";
import {
  MessageSquare,
  FolderOpen,
  BarChart2,
  User,
  Zap,
  ChevronRight,
  Activity,
} from "lucide-react";

const nav = [
  { id: "chat",      label: "AI Chat",     icon: MessageSquare },
  { id: "browse",    label: "Browse JDs",  icon: FolderOpen },
  { id: "analytics", label: "Analytics",   icon: BarChart2 },
  { id: "profile",   label: "My Profile",  icon: User },
];

export default function Sidebar({ page, setPage, indexStatus }) {
  const healthy = indexStatus?.status === "healthy";

  return (
    <motion.aside
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="w-60 shrink-0 h-screen flex flex-col glass border-r border-white/[0.06] py-6 px-3 z-20"
    >
      {/* Logo */}
      <div className="px-3 mb-8">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-600 to-blue-500 flex items-center justify-center shadow-glow shrink-0">
            <Zap size={15} className="text-white" />
          </div>
          <div>
            <p className="text-white font-bold text-sm leading-none">JD Agent</p>
            <p className="text-white/30 text-[10px] leading-none mt-0.5">by Pratik Suryavanshi</p>
          </div>
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex-1 space-y-1">
        {nav.map(({ id, label, icon: Icon }) => {
          const active = page === id;
          return (
            <button
              key={id}
              onClick={() => setPage(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer ${
                active ? "nav-active" : "text-white/40 hover:text-white/70 hover:bg-white/5"
              }`}
            >
              <Icon size={16} className={active ? "text-violet-400" : "text-current"} />
              {label}
              {active && (
                <ChevronRight size={12} className="ml-auto text-violet-400/50" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Status badge */}
      <div className="mt-4 px-3">
        <div className="glass rounded-xl p-3 flex items-center gap-2.5">
          <div className={`w-2 h-2 rounded-full shrink-0 ${healthy ? "bg-emerald-400" : "bg-amber-400"} ${healthy ? "shadow-[0_0_6px_rgba(52,211,153,0.8)]" : ""}`} />
          <div className="min-w-0">
            <p className="text-white/50 text-[10px] uppercase tracking-wider font-medium">Index</p>
            <p className="text-white/70 text-xs font-semibold truncate">
              {indexStatus ? (healthy ? "Ready" : indexStatus.status || "Offline") : "Checking…"}
            </p>
          </div>
          <Activity size={12} className="text-white/20 ml-auto shrink-0" />
        </div>
      </div>

      {/* User avatar */}
      <div className="mt-3 px-3 pt-3 border-t border-white/[0.06]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-600/40 to-blue-500/40 border border-violet-500/30 flex items-center justify-center text-xs font-bold text-violet-300 shrink-0">
            PS
          </div>
          <div className="min-w-0">
            <p className="text-white/70 text-xs font-semibold truncate">Pratik Suryavanshi</p>
            <p className="text-white/25 text-[10px] truncate">IIT Delhi · EE</p>
          </div>
        </div>
      </div>
    </motion.aside>
  );
}
