import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";

export default function ChatBubble({ role, content, isLoading }) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${
        isUser
          ? "bg-gradient-to-br from-violet-600 to-blue-500"
          : "glass border-white/10"
      }`}>
        {isUser ? <User size={14} className="text-white" /> : <Bot size={14} className="text-violet-400" />}
      </div>

      <div className={`max-w-[78%] px-4 py-3 text-sm leading-relaxed ${
        isUser ? "bubble-user text-white/90" : "bubble-ai text-white/80"
      }`}>
        {isLoading ? (
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: "300ms" }} />
          </span>
        ) : isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="prose-chat">
            <ReactMarkdown
              components={{
                p:      ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
                em:     ({ children }) => <em className="text-violet-300">{children}</em>,
                ul:     ({ children }) => <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>,
                ol:     ({ children }) => <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>,
                li:     ({ children }) => <li className="text-white/75">{children}</li>,
                h1:     ({ children }) => <h1 className="text-white font-bold text-base mt-3 mb-1">{children}</h1>,
                h2:     ({ children }) => <h2 className="text-white font-semibold text-sm mt-3 mb-1">{children}</h2>,
                h3:     ({ children }) => <h3 className="text-white/80 font-medium text-sm mt-2 mb-1">{children}</h3>,
                code:   ({ inline, children }) =>
                  inline
                    ? <code className="bg-white/10 text-violet-300 px-1 py-0.5 rounded text-xs font-mono">{children}</code>
                    : <pre className="bg-white/5 rounded-lg p-3 my-2 text-xs font-mono overflow-x-auto"><code>{children}</code></pre>,
                blockquote: ({ children }) => <blockquote className="border-l-2 border-violet-500 pl-3 text-white/50 my-2">{children}</blockquote>,
                hr:     () => <hr className="border-white/10 my-3" />,
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </motion.div>
  );
}
