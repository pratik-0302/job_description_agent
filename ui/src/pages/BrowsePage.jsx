import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, FolderOpen, RefreshCw, X } from "lucide-react";
import { api } from "../lib/api";
import JDCard from "../components/JDCard";
import EmptyState from "../components/EmptyState";
import Button from "../components/Button";
import Badge from "../components/Badge";

export default function BrowsePage() {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [scanLoading, setScanLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    const res = await api.documents();
    if (res.error) setError(res.error);
    else setDocs(Array.isArray(res) ? res : res.documents || []);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function triggerScan() {
    setScanLoading(true);
    await api.scan();
    setScanLoading(false);
    setTimeout(load, 2000);
  }

  const filtered = docs.filter((d) => {
    const q = query.toLowerCase();
    if (!q) return true;
    const meta = d.metadata || {};
    return (
      (d.title || d.file_name || "").toLowerCase().includes(q) ||
      (meta.company_name || "").toLowerCase().includes(q) ||
      (meta.job_title || "").toLowerCase().includes(q) ||
      (meta.skills_required || []).some((s) => s.toLowerCase().includes(q))
    );
  });

  return (
    <div className="flex h-full">
      {/* List panel */}
      <div className="flex flex-col flex-1 min-w-0 border-r border-white/[0.06]">
        {/* Header */}
        <div className="shrink-0 px-6 py-4 border-b border-white/[0.06] flex items-center justify-between gap-3">
          <div>
            <h1 className="text-white font-semibold text-base flex items-center gap-2">
              <FolderOpen size={16} className="text-violet-400" />
              Browse JDs
              <span className="text-white/30 font-normal text-sm">({docs.length})</span>
            </h1>
            <p className="text-white/30 text-xs mt-0.5">All indexed job descriptions</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={13} className={scanLoading ? "animate-spin" : ""} />}
            onClick={triggerScan}
            disabled={scanLoading}
          >
            Scan
          </Button>
        </div>

        {/* Search */}
        <div className="px-6 py-3 border-b border-white/[0.06]">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by company, role, skill…"
              className="input-premium pl-9"
            />
            {query && (
              <button onClick={() => setQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60">
                <X size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {loading && (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="skeleton rounded-2xl h-28" />
              ))}
            </div>
          )}

          {!loading && error && (
            <EmptyState
              icon="⚠️"
              title="Failed to load documents"
              subtitle={error}
              action={<Button variant="ghost" size="sm" onClick={load}>Retry</Button>}
            />
          )}

          {!loading && !error && filtered.length === 0 && (
            <EmptyState
              icon="📂"
              title={query ? "No matches found" : "No documents indexed yet"}
              subtitle={query ? "Try a different search term." : "Drop PDF or DOCX files in the watch folder, then click Scan."}
              action={!query && <Button size="sm" onClick={triggerScan}>Trigger Scan</Button>}
            />
          )}

          <AnimatePresence>
            {filtered.map((doc, i) => (
              <JDCard
                key={doc.doc_id || doc.id || i}
                doc={doc}
                delay={i * 0.03}
                onClick={() => setSelected(doc)}
              />
            ))}
          </AnimatePresence>
        </div>
      </div>

      {/* Detail panel */}
      <AnimatePresence>
        {selected && (
          <motion.div
            key="detail"
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 24 }}
            transition={{ duration: 0.25 }}
            className="w-96 shrink-0 flex flex-col overflow-y-auto"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
              <h2 className="text-white font-semibold text-sm">Details</h2>
              <button onClick={() => setSelected(null)} className="text-white/30 hover:text-white/70 cursor-pointer">
                <X size={16} />
              </button>
            </div>

            <div className="flex-1 px-6 py-5 space-y-5">
              <div>
                <h3 className="text-white font-bold text-base leading-snug">
                  {selected.metadata?.job_title || selected.title || selected.file_name}
                </h3>
                {selected.metadata?.company_name && (
                  <p className="text-white/40 text-sm mt-1">{selected.metadata.company_name}</p>
                )}
              </div>

              {/* Meta fields */}
              {[
                ["Location", selected.metadata?.location],
                ["CTC", selected.metadata?.package_ctc ? `₹${selected.metadata.package_ctc} LPA` : null],
                ["Job Type", selected.metadata?.job_type],
                ["Deadline", selected.metadata?.application_deadline],
                ["Min CGPA", selected.metadata?.min_cgpa],
                ["Eligible Branches", (selected.metadata?.eligible_branches || []).join(", ")],
              ]
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <div key={k}>
                    <p className="text-white/30 text-[10px] uppercase tracking-wider font-medium mb-1">{k}</p>
                    <p className="text-white/70 text-sm">{v}</p>
                  </div>
                ))}

              {/* Skills */}
              {(selected.metadata?.skills_required || []).length > 0 && (
                <div>
                  <p className="text-white/30 text-[10px] uppercase tracking-wider font-medium mb-2">Skills</p>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.metadata.skills_required.map((s) => (
                      <span key={s} className="chip">{s}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Status */}
              <div>
                <p className="text-white/30 text-[10px] uppercase tracking-wider font-medium mb-1">Status</p>
                <Badge variant={selected.status === "indexed" ? "success" : selected.status === "failed" ? "danger" : "warning"}>
                  {selected.status || "unknown"}
                </Badge>
              </div>

              {/* Snippet */}
              {selected.snippet && (
                <div>
                  <p className="text-white/30 text-[10px] uppercase tracking-wider font-medium mb-2">Preview</p>
                  <p className="text-white/40 text-xs leading-relaxed line-clamp-6">{selected.snippet}</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
