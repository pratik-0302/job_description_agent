import { motion } from "framer-motion";
import { Building2, MapPin, DollarSign, Calendar, ChevronRight } from "lucide-react";
import Badge from "./Badge";

function ctcLabel(pkg) {
  if (!pkg) return null;
  return `₹${pkg} LPA`;
}

function typeVariant(jtype) {
  const map = { FTE: "success", Internship: "info", PPO: "purple", "6m": "warning" };
  return map[jtype] || "default";
}

export default function JDCard({ doc, onClick, delay = 0 }) {
  const meta = doc.metadata || {};
  const title = meta.job_title || doc.title || doc.file_name || "Untitled JD";
  const company = meta.company_name || null;
  const location = meta.location || null;
  const ctc = ctcLabel(meta.package_ctc);
  const deadline = meta.application_deadline || null;
  const skills = (meta.skills_required || []).slice(0, 5);
  const jtype = meta.job_type;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      onClick={onClick}
      className="glass rounded-2xl p-5 cursor-pointer hover:border-violet-500/30 hover:shadow-[0_0_24px_rgba(124,58,237,0.15)] transition-all duration-200 group"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {jtype && <Badge variant={typeVariant(jtype)}>{jtype}</Badge>}
            {doc.status && (
              <Badge variant={doc.status === "indexed" ? "success" : doc.status === "failed" ? "danger" : "warning"}>
                {doc.status}
              </Badge>
            )}
          </div>
          <h3 className="text-white font-semibold text-base leading-snug line-clamp-2 group-hover:text-violet-300 transition-colors">
            {title}
          </h3>
        </div>
        <ChevronRight size={16} className="text-white/20 group-hover:text-violet-400 shrink-0 mt-1 transition-colors" />
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-white/40">
        {company && (
          <span className="flex items-center gap-1">
            <Building2 size={11} /> {company}
          </span>
        )}
        {location && (
          <span className="flex items-center gap-1">
            <MapPin size={11} /> {location}
          </span>
        )}
        {ctc && (
          <span className="flex items-center gap-1 text-emerald-400/70">
            <DollarSign size={11} /> {ctc}
          </span>
        )}
        {deadline && (
          <span className="flex items-center gap-1">
            <Calendar size={11} /> {deadline}
          </span>
        )}
      </div>

      {skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {skills.map((s) => (
            <span key={s} className="chip">{s}</span>
          ))}
          {(meta.skills_required || []).length > 5 && (
            <span className="chip bg-white/5 border-white/10 text-white/30">
              +{meta.skills_required.length - 5}
            </span>
          )}
        </div>
      )}
    </motion.div>
  );
}
