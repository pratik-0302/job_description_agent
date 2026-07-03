import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Sparkles, RefreshCw, Trash2, Paperclip, X, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import ChatBubble from "../components/ChatBubble";
import Button from "../components/Button";

const SESSION_KEY = "jd-session-id";

function getOrCreateSession() {
  let sid = sessionStorage.getItem(SESSION_KEY);
  if (!sid) {
    sid = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, sid);
  }
  return sid;
}

const STARTERS = [
  "Which companies are hiring for roles with CTC above 20 LPA?",
  "Compare software engineering roles at top product companies.",
  "What skills are most demanded across all JDs?",
  "Show me internships with a PPO offer.",
];

// Small banner shown inside chat when a file is uploaded
function UploadBanner({ upload, onDismiss }) {
  const isQueued  = upload.status === "queued";
  const isExists  = upload.status === "already_exists";
  const isError   = upload.status === "error";
  const isLoading = upload.status === "loading";

  const color = isQueued  ? "border-emerald-500/40 bg-emerald-500/10"
              : isExists  ? "border-amber-500/40  bg-amber-500/10"
              : isError   ? "border-red-500/40    bg-red-500/10"
              :             "border-violet-500/40 bg-violet-500/10";

  const Icon = isQueued  ? CheckCircle
             : isExists  ? AlertCircle
             : isError   ? AlertCircle
             : Loader2;

  const iconColor = isQueued ? "text-emerald-400"
                 : isExists  ? "text-amber-400"
                 : isError   ? "text-red-400"
                 : "text-violet-400";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-xs ${color}`}
    >
      <Icon size={15} className={`shrink-0 mt-0.5 ${iconColor} ${isLoading ? "animate-spin" : ""}`} />
      <div className="flex-1 text-white/70 leading-snug">
        {isLoading ? (
          <span>Uploading <span className="text-white/90 font-medium">{upload.file_name}</span>…</span>
        ) : (
          upload.message
        )}
      </div>
      {!isLoading && (
        <button onClick={onDismiss} className="text-white/30 hover:text-white/60 transition-colors shrink-0">
          <X size={13} />
        </button>
      )}
    </motion.div>
  );
}

export default function ChatPage() {
  const [messages, setMessages]     = useState([]);
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [sessionId]                 = useState(getOrCreateSession);
  const [uploads, setUploads]       = useState([]);   // list of upload banners
  const [dragOver, setDragOver]     = useState(false);
  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, uploads]);

  async function send(text) {
    const q = text.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);

    const res = await api.query(q, sessionId);
    setLoading(false);

    if (res.error) {
      setMessages((m) => [...m, { role: "assistant", content: `Error: ${res.error}` }]);
      return;
    }

    const answer = res.response_text || res.answer || res.response || res.result || JSON.stringify(res);
    setMessages((m) => [...m, { role: "assistant", content: answer }]);
  }

  async function handleFile(file) {
    if (!file) return;
    const id = crypto.randomUUID();
    setUploads((u) => [...u, { id, status: "loading", file_name: file.name, message: "" }]);

    const res = await api.upload(file);

    setUploads((u) =>
      u.map((item) =>
        item.id !== id
          ? item
          : res.error
            ? { ...item, status: "error",  message: res.error }
            : { ...item, status: res.status, message: res.message, file_name: res.file_name || file.name }
      )
    );
  }

  function handleFileInput(e) {
    handleFile(e.target.files?.[0]);
    e.target.value = "";
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files?.[0]);
  }

  function dismissUpload(id) {
    setUploads((u) => u.filter((item) => item.id !== id));
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  return (
    <div
      className="flex flex-col h-full"
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
    >
      {/* Drag-over overlay */}
      <AnimatePresence>
        {dragOver && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-violet-900/60 backdrop-blur-sm rounded-2xl border-2 border-dashed border-violet-400 pointer-events-none"
          >
            <Paperclip size={36} className="text-violet-300 mb-3" />
            <p className="text-violet-200 font-semibold text-sm">Drop your JD (PDF / DOCX)</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
        <div>
          <h1 className="text-white font-semibold text-base flex items-center gap-2">
            <Sparkles size={16} className="text-violet-400" />
            AI Chat
          </h1>
          <p className="text-white/30 text-xs mt-0.5">Ask anything about your job descriptions</p>
        </div>
        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            icon={<Trash2 size={13} />}
            onClick={() => setMessages([])}
          >
            Clear
          </Button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.length === 0 && uploads.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center h-full text-center pb-10"
          >
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-600 to-blue-500 flex items-center justify-center mb-5 shadow-glow">
              <Sparkles size={24} className="text-white" />
            </div>
            <h2 className="text-white font-bold text-xl mb-2">
              What can I help you find?
            </h2>
            <p className="text-white/35 text-sm max-w-sm mb-8">
              Ask me anything about your indexed JDs — or upload a new PDF / DOCX to add it instantly.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="glass rounded-xl px-4 py-3 text-left text-xs text-white/50 hover:text-white/80 hover:border-violet-500/30 transition-all duration-150 cursor-pointer leading-snug"
                >
                  {s}
                </button>
              ))}
            </div>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((m, i) => (
            <ChatBubble key={i} role={m.role} content={m.content} />
          ))}
          {loading && <ChatBubble key="loading" role="assistant" isLoading />}
        </AnimatePresence>

        {/* Upload banners */}
        <AnimatePresence>
          {uploads.map((u) => (
            <UploadBanner key={u.id} upload={u} onDismiss={() => dismissUpload(u.id)} />
          ))}
        </AnimatePresence>

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="shrink-0 px-6 pb-6 pt-3 border-t border-white/[0.06]">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          onChange={handleFileInput}
        />
        <div className="flex items-end gap-3">
          {/* Unified input container — paperclip lives inside */}
          <div className="flex-1 flex items-end rounded-xl border border-white/10 bg-white/[0.04] focus-within:border-violet-500/60 focus-within:bg-violet-500/[0.06] focus-within:shadow-[0_0_0_3px_rgba(124,58,237,0.15)] transition-all duration-200">
            {/* Paperclip */}
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => fileInputRef.current?.click()}
              title="Upload JD (PDF / DOCX)"
              className="p-3 text-white/30 hover:text-violet-400 transition-colors shrink-0 cursor-pointer"
            >
              <Paperclip size={16} />
            </motion.button>

            {/* Textarea */}
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about companies, packages — or drag & drop a JD PDF"
              rows={1}
              style={{ resize: "none" }}
              className="flex-1 bg-transparent py-3 pr-3 text-sm text-white/80 placeholder-white/25 outline-none leading-relaxed min-h-[46px] max-h-40 font-[inherit]"
              onInput={(e) => {
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
              }}
            />
          </div>

          {/* Send button */}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className="w-[46px] h-[46px] rounded-xl bg-gradient-to-br from-violet-600 to-blue-500 flex items-center justify-center shadow-glow disabled:opacity-40 shrink-0 cursor-pointer"
          >
            {loading ? (
              <RefreshCw size={16} className="text-white animate-spin" />
            ) : (
              <Send size={15} className="text-white" />
            )}
          </motion.button>
        </div>
        <p className="text-white/20 text-[10px] mt-2 text-center">
          Session: {sessionId.slice(0, 8)}…  ·  Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}
