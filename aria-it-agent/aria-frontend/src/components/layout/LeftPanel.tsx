"use client";

import { motion } from "framer-motion";
import { User, Play, LayoutDashboard, MessageSquare, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

interface LeftPanelProps {
  currentView: "chat" | "dashboard";
  setView: (view: "chat" | "dashboard") => void;
  onWorkflowTrigger: (workflowMessage: string) => void;
  role: string;
  setRole: (role: string) => void;
}

const WORKFLOWS = [
  { id: "laptop", label: "My laptop is extremely slow", icon: "💻", query: "My laptop is extremely slow and freezing. Can you fix it?" },
  { id: "security", label: "Report Security Incident", icon: "🚨", query: "I clicked a link and now my screen says ransomware. Help!" },
  { id: "password", label: "Reset Password", icon: "🔑", query: "I forgot my password and am locked out of my account." },
  { id: "outage", label: "Production is down", icon: "🔥", query: "Production api-gateway is returning 503 errors!" },
  { id: "onboard", label: "Onboard new employee", icon: "👋", query: "I have a new employee joining today, please onboard them." },
];

export default function LeftPanel({ currentView, setView, onWorkflowTrigger, role, setRole }: LeftPanelProps) {
  return (
    <motion.div 
      initial={{ x: -50, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      className="w-72 border-r border-white/10 glass-panel flex flex-col gap-6 p-4 h-full shrink-0 overflow-y-auto"
    >
      {/* Simulation Controls */}
      <div className="space-y-3">
        <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">User Simulation</h3>
        <div className="bg-white/5 border border-white/10 rounded-xl p-3 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-slate-300">
              <User className="w-4 h-4 text-blue-400" />
              Role
            </div>
            <select 
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="bg-black/50 border border-white/10 text-xs rounded-md px-2 py-1 text-slate-200 outline-none focus:border-blue-500"
            >
              <option value="employee">Employee</option>
              <option value="it_staff">IT Staff</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          
          <div className="flex items-center justify-between border-t border-white/5 pt-3">
            <span className="text-sm text-slate-300">Auto-Workflows</span>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-9 h-5 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-500"></div>
            </label>
          </div>
        </div>
      </div>

      {/* Quick Workflows */}
      <div className="space-y-3">
        <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
          <Terminal className="w-3 h-3" /> Quick Workflows
        </h3>
        <div className="flex flex-col gap-2">
          {WORKFLOWS.map((wf, i) => (
            <motion.button
              key={wf.id}
              whileHover={{ scale: 1.02, x: 4 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => onWorkflowTrigger(wf.query)}
              className="flex items-center gap-3 w-full bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/20 text-left px-3 py-2.5 rounded-xl transition-colors text-sm text-slate-200 group"
            >
              <span className="text-base">{wf.icon}</span>
              <span className="truncate">{wf.label}</span>
              <Play className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100 text-blue-400 transition-opacity" />
            </motion.button>
          ))}
        </div>
      </div>

      {/* Views */}
      <div className="space-y-3 mt-auto">
        <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Views</h3>
        <div className="flex flex-col gap-2">
          <button 
            onClick={() => setView("chat")}
            className={cn(
              "flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm transition-colors",
              currentView === "chat" 
                ? "bg-blue-500/20 border border-blue-500/50 text-blue-100 shadow-[0_0_15px_rgba(59,130,246,0.2)]" 
                : "bg-white/5 border border-white/5 text-slate-400 hover:text-slate-200"
            )}
          >
            <MessageSquare className="w-4 h-4" />
            Agent Chat
          </button>
          
          <button 
            onClick={() => setView("dashboard")}
            className={cn(
              "flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm transition-colors",
              currentView === "dashboard" 
                ? "bg-purple-500/20 border border-purple-500/50 text-purple-100 shadow-[0_0_15px_rgba(168,85,247,0.2)]" 
                : "bg-white/5 border border-white/5 text-slate-400 hover:text-slate-200"
            )}
          >
            <LayoutDashboard className="w-4 h-4" />
            Analytics Dashboard
          </button>
        </div>
      </div>
    </motion.div>
  );
}
