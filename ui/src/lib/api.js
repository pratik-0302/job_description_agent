const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function req(method, path, body) {
  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json();
    if (!res.ok) return { error: `${res.status}: ${data.detail || res.statusText}` };
    return data;
  } catch (e) {
    return { error: `Connection failed: ${e.message}` };
  }
}

async function upload(file) {
  try {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/api/upload`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) return { error: `${res.status}: ${data.detail || res.statusText}` };
    return data;
  } catch (e) {
    return { error: `Upload failed: ${e.message}` };
  }
}

export const api = {
  health:    ()         => req("GET",  "/api/index/health"),
  status:    ()         => req("GET",  "/api/index/status"),
  scan:      ()         => req("POST", "/api/index/scan"),
  query:     (q, sid)   => req("POST", "/api/query",    { query_text: q, session_id: sid }),
  documents: ()         => req("GET",  "/api/documents"),
  document:  (id)       => req("GET",  `/api/documents/${id}`),
  analytics: ()         => req("GET",  "/api/analytics/summary"),
  profile:   (sid, p)   => req("PUT",  `/api/profile/${sid}`, p),
  upload:    (file)     => upload(file),
};
