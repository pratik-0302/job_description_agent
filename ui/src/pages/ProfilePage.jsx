import { useState } from "react";
import { motion } from "framer-motion";
import { User, Save, Plus, X, CheckCircle } from "lucide-react";
import { api } from "../lib/api";
import Button from "../components/Button";

const SESSION_KEY = "jd-session-id";

function getSession() {
  return sessionStorage.getItem(SESSION_KEY) || "default";
}

const BRANCH_OPTIONS = ["CSE", "ECE", "EE", "ME", "CE", "CH", "MT", "PH", "MA", "MnC"];
const JOB_TYPE_OPTIONS = ["FTE", "Internship", "PPO", "6m"];

export default function ProfilePage() {
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState({
    name: "Pratik Suryavanshi",
    branch: "EE",
    cgpa: "",
    skills: [],
    preferred_job_types: ["FTE"],
    preferred_locations: [],
    min_ctc: "",
  });
  const [skillInput, setSkillInput] = useState("");
  const [locInput, setLocInput] = useState("");

  function addSkill() {
    const s = skillInput.trim();
    if (s && !profile.skills.includes(s)) {
      setProfile((p) => ({ ...p, skills: [...p.skills, s] }));
    }
    setSkillInput("");
  }

  function removeSkill(s) {
    setProfile((p) => ({ ...p, skills: p.skills.filter((x) => x !== s) }));
  }

  function addLoc() {
    const l = locInput.trim();
    if (l && !profile.preferred_locations.includes(l)) {
      setProfile((p) => ({ ...p, preferred_locations: [...p.preferred_locations, l] }));
    }
    setLocInput("");
  }

  function removeLoc(l) {
    setProfile((p) => ({ ...p, preferred_locations: p.preferred_locations.filter((x) => x !== l) }));
  }

  function toggleJobType(jt) {
    setProfile((p) => ({
      ...p,
      preferred_job_types: p.preferred_job_types.includes(jt)
        ? p.preferred_job_types.filter((x) => x !== jt)
        : [...p.preferred_job_types, jt],
    }));
  }

  async function saveProfile() {
    setLoading(true);
    const sid = getSession();
    const payload = {
      ...profile,
      cgpa: profile.cgpa ? parseFloat(profile.cgpa) : undefined,
      min_ctc: profile.min_ctc ? parseFloat(profile.min_ctc) : undefined,
    };
    await api.profile(sid, payload);
    setLoading(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
        <div>
          <h1 className="text-white font-semibold text-base flex items-center gap-2">
            <User size={16} className="text-violet-400" />
            My Profile
          </h1>
          <p className="text-white/30 text-xs mt-0.5">Personalise AI recommendations to your preferences</p>
        </div>
        <Button
          size="sm"
          onClick={saveProfile}
          disabled={loading}
          icon={saved ? <CheckCircle size={13} /> : <Save size={13} />}
        >
          {saved ? "Saved!" : "Save"}
        </Button>
      </div>

      <div className="flex-1 px-6 py-6 max-w-2xl space-y-8">
        {/* Avatar + name */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600 to-blue-500 flex items-center justify-center text-2xl font-bold text-white shadow-glow">
            PS
          </div>
          <div>
            <h2 className="text-white font-bold text-lg">Pratik Suryavanshi</h2>
            <p className="text-white/40 text-sm">IIT Delhi · Electrical Engineering</p>
          </div>
        </motion.div>

        {/* Basic info */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }} className="glass rounded-2xl p-5 space-y-4">
          <h3 className="text-white/60 text-xs uppercase tracking-wider font-semibold">Basic Info</h3>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-white/40 text-xs mb-1.5">Branch</label>
              <select
                value={profile.branch}
                onChange={(e) => setProfile((p) => ({ ...p, branch: e.target.value }))}
                className="input-premium"
              >
                {BRANCH_OPTIONS.map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-white/40 text-xs mb-1.5">CGPA</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="10"
                value={profile.cgpa}
                onChange={(e) => setProfile((p) => ({ ...p, cgpa: e.target.value }))}
                placeholder="e.g. 8.5"
                className="input-premium"
              />
            </div>
            <div>
              <label className="block text-white/40 text-xs mb-1.5">Min CTC (LPA)</label>
              <input
                type="number"
                step="0.5"
                min="0"
                value={profile.min_ctc}
                onChange={(e) => setProfile((p) => ({ ...p, min_ctc: e.target.value }))}
                placeholder="e.g. 12"
                className="input-premium"
              />
            </div>
          </div>
        </motion.div>

        {/* Job type preferences */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass rounded-2xl p-5 space-y-4">
          <h3 className="text-white/60 text-xs uppercase tracking-wider font-semibold">Preferred Job Types</h3>
          <div className="flex flex-wrap gap-2">
            {JOB_TYPE_OPTIONS.map((jt) => {
              const active = profile.preferred_job_types.includes(jt);
              return (
                <button
                  key={jt}
                  onClick={() => toggleJobType(jt)}
                  className={`px-4 py-1.5 rounded-xl text-sm font-semibold transition-all duration-150 cursor-pointer border ${
                    active
                      ? "bg-violet-600/30 border-violet-500/50 text-violet-300"
                      : "bg-white/5 border-white/10 text-white/40 hover:text-white/60"
                  }`}
                >
                  {jt}
                </button>
              );
            })}
          </div>
        </motion.div>

        {/* Skills */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="glass rounded-2xl p-5 space-y-4">
          <h3 className="text-white/60 text-xs uppercase tracking-wider font-semibold">Skills</h3>
          <div className="flex gap-2">
            <input
              value={skillInput}
              onChange={(e) => setSkillInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addSkill()}
              placeholder="Add a skill (e.g. Python, React)"
              className="input-premium flex-1"
            />
            <Button variant="outline" size="sm" icon={<Plus size={13} />} onClick={addSkill}>Add</Button>
          </div>
          {profile.skills.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {profile.skills.map((s) => (
                <span key={s} className="chip gap-1.5">
                  {s}
                  <button onClick={() => removeSkill(s)} className="hover:text-white/80 cursor-pointer">
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
          )}
        </motion.div>

        {/* Preferred locations */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass rounded-2xl p-5 space-y-4">
          <h3 className="text-white/60 text-xs uppercase tracking-wider font-semibold">Preferred Locations</h3>
          <div className="flex gap-2">
            <input
              value={locInput}
              onChange={(e) => setLocInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addLoc()}
              placeholder="Add location (e.g. Bangalore, Remote)"
              className="input-premium flex-1"
            />
            <Button variant="outline" size="sm" icon={<Plus size={13} />} onClick={addLoc}>Add</Button>
          </div>
          {profile.preferred_locations.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {profile.preferred_locations.map((l) => (
                <span key={l} className="chip gap-1.5">
                  {l}
                  <button onClick={() => removeLoc(l)} className="hover:text-white/80 cursor-pointer">
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
