"use client";

import { motion } from "framer-motion";
import { Zap, Shield, Activity, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Navbar() {
  return (
    <motion.header 
      initial={{ y: -50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="h-16 border-b border-white/10 glass-panel flex items-center px-6 justify-between shrink-0 z-50 relative"
    >
      {/* Logo Section */}
      <div className="flex items-center gap-4">
        <div className="relative">
          <div className="absolute inset-0 bg-blue-500 rounded-xl blur-lg opacity-50 animate-pulse-slow"></div>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center relative z-10 border border-white/20">
            <Zap className="text-white w-5 h-5" />
          </div>
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white to-white/70">
            ARIA
          </h1>
          <p className="text-[10px] uppercase tracking-widest text-blue-400 font-mono">
            Multi-Agent AI OS
          </p>
        </div>
      </div>

      {/* Metrics Section */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-mono">
          <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]"></div>
          <span className="text-emerald-400">System Online</span>
        </div>
        
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-mono text-purple-400">
          <Shield className="w-3.5 h-3.5" />
          <span>Zero Trust Active</span>
        </div>
        
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-mono text-blue-400">
          <Cpu className="w-3.5 h-3.5" />
          <span>Groq LPU</span>
        </div>
      </div>
    </motion.header>
  );
}
