"use client";

import { motion } from "framer-motion";

const AGENTS = [
  { id: "orchestrator", name: "Master Orchestrator", desc: "Routes queries & merges responses", icon: "🧠", color: "text-amber-400" },
  { id: "security", name: "Security Agent", desc: "Incidents, MFA, Passwords", icon: "🛡️", color: "text-red-400" },
  { id: "devops", name: "DevOps Agent", desc: "CI/CD, Pods, Deployments", icon: "⚙️", color: "text-purple-400" },
  { id: "network", name: "Networking Agent", desc: "VPN, DNS, Firewalls", icon: "🌐", color: "text-blue-400" },
  { id: "cloud", name: "Cloud Agent", desc: "AWS, Azure, M365, FinOps", icon: "☁️", color: "text-cyan-400" },
  { id: "infra", name: "Infrastructure Agent", desc: "Servers, Storage, Backups", icon: "🏗️", color: "text-emerald-400" },
  { id: "hardware", name: "Hardware Agent", desc: "Laptops, Printers, Peripherals", icon: "💻", color: "text-orange-400" },
  { id: "hr", name: "HR/Access Agent", desc: "Onboarding, Permissions", icon: "👥", color: "text-pink-400" },
];

export default function RightPanel({ activeAgents = [] }: { activeAgents?: string[] }) {
  return (
    <motion.div 
      initial={{ x: 50, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      className="w-80 border-l border-white/10 glass-panel p-4 flex flex-col gap-4 h-full shrink-0 overflow-y-auto"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Agent Roster</h3>
        <span className="text-xs text-blue-400 font-mono bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20">
          8 Active
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {AGENTS.map((agent, i) => {
          const isActive = activeAgents.includes(agent.id) || activeAgents.length === 0;
          
          return (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={`flex items-center gap-3 p-3 rounded-xl border transition-all duration-300 ${
                isActive 
                  ? "bg-white/10 border-white/20 shadow-[0_0_15px_rgba(255,255,255,0.05)] scale-[1.02]" 
                  : "bg-white/5 border-white/5 opacity-60 hover:opacity-100"
              }`}
            >
              <div className={`w-10 h-10 rounded-lg bg-black/40 border border-white/10 flex items-center justify-center text-xl shadow-inner ${agent.color}`}>
                {agent.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-semibold text-slate-200 truncate">{agent.name}</h4>
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${isActive ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse" : "bg-slate-600"}`}></div>
                </div>
                <p className="text-[10px] text-slate-400 truncate mt-0.5">{agent.desc}</p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
