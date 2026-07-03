import { motion } from "framer-motion";

const variants = {
  primary: "bg-gradient-to-r from-violet-600 to-blue-500 text-white shadow-glow hover:shadow-glow hover:opacity-90",
  ghost:   "bg-white/5 text-white/70 border border-white/10 hover:bg-white/10 hover:text-white",
  danger:  "bg-red-500/15 text-red-400 border border-red-500/25 hover:bg-red-500/25",
  outline: "border border-violet-500/40 text-violet-300 hover:bg-violet-500/10",
};

const sizes = {
  sm: "text-xs px-3 py-1.5 gap-1.5",
  md: "text-sm px-4 py-2 gap-2",
  lg: "text-sm px-5 py-2.5 gap-2",
};

export default function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  disabled = false,
  icon,
  onClick,
  type = "button",
}) {
  return (
    <motion.button
      type={type}
      whileHover={{ scale: disabled ? 1 : 1.02 }}
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-xl font-semibold transition-all duration-150 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </motion.button>
  );
}
