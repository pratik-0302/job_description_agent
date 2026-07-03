import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Sidebar from "./components/Sidebar";
import ChatPage from "./pages/ChatPage";
import BrowsePage from "./pages/BrowsePage";
import AnalyticsPage from "./pages/AnalyticsPage";
import ProfilePage from "./pages/ProfilePage";
import { api } from "./lib/api";

const pages = {
  chat:      ChatPage,
  browse:    BrowsePage,
  analytics: AnalyticsPage,
  profile:   ProfilePage,
};

export default function App() {
  const [page, setPage] = useState("chat");
  const [indexStatus, setIndexStatus] = useState(null);

  useEffect(() => {
    api.health().then((res) => {
      if (!res.error) setIndexStatus(res);
    });
    const id = setInterval(() => {
      api.health().then((res) => {
        if (!res.error) setIndexStatus(res);
      });
    }, 30_000);
    return () => clearInterval(id);
  }, []);

  const Page = pages[page];

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#09090B] mesh-bg noise relative">
      {/* Ambient blobs */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden z-0">
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full bg-violet-600/10 blur-3xl animate-blob" />
        <div className="absolute top-1/2 -right-24 w-80 h-80 rounded-full bg-blue-600/8 blur-3xl animate-blob" style={{ animationDelay: "3s" }} />
        <div className="absolute -bottom-24 left-1/3 w-72 h-72 rounded-full bg-cyan-600/6 blur-3xl animate-blob" style={{ animationDelay: "6s" }} />
      </div>

      <Sidebar page={page} setPage={setPage} indexStatus={indexStatus} />

      <main className="flex-1 min-w-0 relative z-10">
        <AnimatePresence mode="wait">
          <motion.div
            key={page}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22 }}
            className="h-full"
          >
            <Page />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
