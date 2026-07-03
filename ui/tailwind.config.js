/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["'Plus Jakarta Sans'", "Inter", "sans-serif"],
      },
      colors: {
        bg:       "#09090B",
        surface:  "rgba(255,255,255,0.04)",
        border2:  "rgba(255,255,255,0.08)",
        primary:  "#7C3AED",
        secondary:"#3B82F6",
        accent:   "#06B6D4",
        success:  "#10B981",
        warning:  "#F59E0B",
        danger:   "#EF4444",
        muted:    "#9CA3AF",
      },
      boxShadow: {
        glass:      "0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)",
        glow:       "0 0 32px rgba(124,58,237,0.4)",
        "glow-blue":"0 0 32px rgba(59,130,246,0.4)",
        card:       "0 4px 24px rgba(0,0,0,0.6)",
        "inner-glow":"inset 0 1px 0 rgba(255,255,255,0.08)",
      },
      animation: {
        blob:       "blob 9s infinite",
        shimmer:    "shimmer 2.2s infinite",
        float:      "float 6s ease-in-out infinite",
        "pulse-slow":"pulse 4s cubic-bezier(0.4,0,0.6,1) infinite",
        fadeIn:     "fadeIn 0.4s ease",
        slideUp:    "slideUp 0.4s ease",
      },
      keyframes: {
        blob: {
          "0%,100%": { transform:"translate(0,0) scale(1)" },
          "33%":     { transform:"translate(40px,-25px) scale(1.07)" },
          "66%":     { transform:"translate(-25px,20px) scale(0.95)" },
        },
        shimmer: {
          "0%":   { backgroundPosition:"-400px 0" },
          "100%": { backgroundPosition:"400px 0" },
        },
        float: {
          "0%,100%": { transform:"translateY(0)" },
          "50%":     { transform:"translateY(-12px)" },
        },
        fadeIn: {
          "0%":   { opacity:0 },
          "100%": { opacity:1 },
        },
        slideUp: {
          "0%":   { opacity:0, transform:"translateY(16px)" },
          "100%": { opacity:1, transform:"translateY(0)" },
        },
      },
    },
  },
  plugins: [],
}
