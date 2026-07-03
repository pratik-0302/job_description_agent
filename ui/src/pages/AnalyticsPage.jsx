import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { BarChart2, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import StatCard from "../components/StatCard";
import Button from "../components/Button";
import EmptyState from "../components/EmptyState";

function SkillBar({ skill, count, max }) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <p className="text-white/60 text-xs w-28 shrink-0 truncate">{skill}</p>
      <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-500"
        />
      </div>
      <p className="text-white/30 text-xs w-6 text-right shrink-0">{count}</p>
    </div>
  );
}

export default function AnalyticsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    const res = await api.analytics();
    if (res.error) setError(res.error);
    else setData(res);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  const topSkills = Object.entries(data?.skills_frequency || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 12);
  const maxSkill = topSkills[0]?.[1] || 1;

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
        <div>
          <h1 className="text-white font-semibold text-base flex items-center gap-2">
            <BarChart2 size={16} className="text-violet-400" />
            Analytics
          </h1>
          <p className="text-white/30 text-xs mt-0.5">Insights across your job description index</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          icon={<RefreshCw size={13} className={loading ? "animate-spin" : ""} />}
          onClick={load}
          disabled={loading}
        >
          Refresh
        </Button>
      </div>

      <div className="flex-1 px-6 py-6 space-y-8">
        {loading && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton rounded-2xl h-24" />
            ))}
          </div>
        )}

        {!loading && error && (
          <EmptyState
            icon="⚠️"
            title="Analytics unavailable"
            subtitle={error}
            action={<Button variant="ghost" size="sm" onClick={load}>Retry</Button>}
          />
        )}

        {!loading && !error && data && (
          <>
            {/* Stat grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard icon="📄" label="Total JDs"     value={data.total_documents}  color="violet" delay={0}    />
              <StatCard icon="✅" label="Indexed"       value={data.indexed_count}    color="green"  delay={0.05} />
              <StatCard icon="🏢" label="Companies"     value={data.company_count}    color="blue"   delay={0.1}  />
              <StatCard icon="💰" label="Avg CTC"       value={data.avg_ctc ? `₹${data.avg_ctc} L` : "—"} color="cyan" delay={0.15} />
            </div>

            {/* Job types breakdown */}
            {data.job_type_breakdown && Object.keys(data.job_type_breakdown).length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="glass rounded-2xl p-5"
              >
                <h2 className="text-white/60 text-xs uppercase tracking-wider font-semibold mb-4">Job Types</h2>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(data.job_type_breakdown).map(([type, count]) => (
                    <div key={type} className="glass rounded-xl px-4 py-3 text-center min-w-[80px]">
                      <p className="text-white font-bold text-lg">{count}</p>
                      <p className="text-white/40 text-xs mt-0.5">{type}</p>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Top skills */}
            {topSkills.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25 }}
                className="glass rounded-2xl p-5"
              >
                <h2 className="text-white/60 text-xs uppercase tracking-wider font-semibold mb-4">Top Skills in Demand</h2>
                <div className="space-y-3">
                  {topSkills.map(([skill, count]) => (
                    <SkillBar key={skill} skill={skill} count={count} max={maxSkill} />
                  ))}
                </div>
              </motion.div>
            )}

            {/* Recent activity */}
            {(data.recent_documents || []).length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="glass rounded-2xl p-5"
              >
                <h2 className="text-white/60 text-xs uppercase tracking-wider font-semibold mb-4">Recently Indexed</h2>
                <div className="space-y-2">
                  {data.recent_documents.slice(0, 8).map((doc, i) => (
                    <div key={i} className="flex items-center gap-3 py-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0" />
                      <p className="text-white/60 text-sm flex-1 truncate">{doc.title || doc.file_name}</p>
                      <p className="text-white/25 text-xs shrink-0">{doc.company || ""}</p>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
