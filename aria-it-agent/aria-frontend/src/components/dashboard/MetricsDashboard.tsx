"use client";

import { motion } from "framer-motion";
import { Activity, Cpu, Database, Network } from "lucide-react";
import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

export default function MetricsDashboard({ token }: { token?: string }) {
  const [data, setData] = useState<any[]>([]);
  const [liveStats, setLiveStats] = useState<any>(null);
  const [fetchError, setFetchError] = useState<boolean>(false);

  useEffect(() => {
    // Real-time telemetry chart simulation (CPU / Memory)
    const initialData = Array.from({ length: 20 }, (_, i) => ({
      time: i,
      cpu: 30 + Math.random() * 20,
      memory: 50 + Math.random() * 10,
    }));
    setData(initialData);

    let counter = 20;
    const interval = setInterval(() => {
      setData((prev) => {
        const newPoint = {
          time: counter++,
          cpu: 25 + Math.random() * 25,
          memory: 45 + Math.random() * 15,
        };
        return [...prev.slice(1), newPoint];
      });
    }, 1500);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!token) return;

    const fetchAnalytics = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/analytics", {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        if (!res.ok) throw new Error("Unauthorized or server error");
        const stats = await res.json();
        setLiveStats(stats);
        setFetchError(false);
      } catch (err) {
        console.warn("Could not fetch backend analytics, falling back to simulation.", err);
        setFetchError(true);
      }
    };

    fetchAnalytics();
    const analyticsInterval = setInterval(fetchAnalytics, 4000);
    return () => clearInterval(analyticsInterval);
  }, [token]);

  // Fallback / mock metrics if API is unauthorized or empty
  const activeQueries = liveStats?.summary?.total_queries ?? 142;
  const systemLatency = liveStats?.summary?.avg_latency_ms !== undefined 
    ? `${liveStats.summary.avg_latency_ms.toFixed(0)}ms`
    : liveStats?.summary?.avg_latency !== undefined 
    ? `${(liveStats.summary.avg_latency * 1000).toFixed(0)}ms` 
    : "42ms";
  const successRate = liveStats?.summary?.success_rate !== undefined
    ? `${(liveStats.summary.success_rate * 100).toFixed(1)}%`
    : liveStats?.summary?.hallucination_risk_pct !== undefined
    ? `${(100 - liveStats.summary.hallucination_risk_pct).toFixed(1)}%`
    : "99.4%";
  
  // Format agent/tool distributions
  const agentStats = liveStats?.agents || {
    "orchestrator": 48,
    "security": 32,
    "cloud": 28,
    "network": 19,
    "devops": 15,
  };

  const toolStats = liveStats?.summary?.tool_usage || liveStats?.tools || {
    "rag_kb_search": 64,
    "mfa_reset_tool": 22,
    "aws_ec2_control": 18,
    "ping_device": 14,
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">System Analytics HUD</h2>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            {fetchError ? "⚠️ Simulated Telemetry (Employee access restricted)" : "⚡ Real-time Enterprise Telemetry Feed Connected"}
          </p>
        </div>
        
        <div className="flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 px-3 py-1 rounded-full text-[10px] font-mono text-blue-400 uppercase tracking-wider animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-400"></span> Live Node
        </div>
      </div>
      
      {/* Metric Cards Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Active Connections", val: "1,204", icon: <Network className="w-5 h-5 text-blue-400" />, glow: "glow-primary" },
          { label: "Total Queries Run", val: activeQueries.toLocaleString(), icon: <Cpu className="w-5 h-5 text-purple-400" />, glow: "glow-secondary" },
          { label: "RAG Pipeline Latency", val: systemLatency, icon: <Database className="w-5 h-5 text-emerald-400" />, glow: "shadow-[0_0_15px_rgba(16,185,129,0.15)]" },
          { label: "System Accuracy", val: successRate, icon: <Activity className="w-5 h-5 text-amber-400" />, glow: "shadow-[0_0_15px_rgba(245,158,11,0.15)]" },
        ].map((stat, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className={`glass-panel p-4 rounded-xl border border-white/10 relative overflow-hidden ${stat.glow}`}
          >
            <div className="absolute top-0 right-0 p-4 opacity-20">{stat.icon}</div>
            <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">{stat.label}</p>
            <h3 className="text-2xl font-mono font-bold text-white mt-2">{stat.val}</h3>
          </motion.div>
        ))}
      </div>
 
      {/* Main Panel Content: Chart + Roster Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Telemetry Chart */}
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="glass-panel p-5 rounded-xl border border-white/10 h-80 lg:col-span-2 flex flex-col relative"
        >
          <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-4 font-bold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500 animate-ping"></span> Real-time Telemetry Data
          </h3>
          <div className="flex-1 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                <XAxis dataKey="time" hide />
                <YAxis stroke="#94a3b8" fontSize={10} domain={[0, 100]} axisLine={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.95)', borderColor: 'rgba(255, 255, 255, 0.1)', borderRadius: '12px' }}
                  itemStyle={{ fontSize: '11px', color: '#e2e8f0' }}
                  labelStyle={{ display: 'none' }}
                />
                <Line type="monotone" dataKey="cpu" stroke="#c084fc" strokeWidth={2.5} dot={false} name="CPU Load %" isAnimationActive={false} />
                <Line type="monotone" dataKey="memory" stroke="#34d399" strokeWidth={2.5} dot={false} name="Memory Load %" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </motion.div>
 
        {/* Dynamic Activity List */}
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="glass-panel p-5 rounded-xl border border-white/10 h-80 flex flex-col overflow-hidden"
        >
          <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-4 font-bold">Agent Trigger Frequency</h3>
          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {Object.entries(agentStats).map(([agent, val]: any, idx) => {
              const count = typeof val === "object" ? (val.total_queries ?? 0) : (typeof val === "number" ? val : 0);
              return (
                <div key={agent} className="space-y-1">
                  <div className="flex items-center justify-between text-xs text-slate-300">
                    <span className="capitalize font-mono">{agent.replace("_", " ")}</span>
                    <span className="font-mono text-purple-400">{count} calls</span>
                  </div>
                  <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden">
                    <motion.div 
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(100, (count / 150) * 100)}%` }}
                      transition={{ duration: 1, delay: idx * 0.1 }}
                      className="bg-gradient-to-r from-blue-500 to-purple-500 h-full rounded-full"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      </div>

      {/* Footer Info: Tool Invocations */}
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="glass-panel p-5 rounded-xl border border-white/10"
      >
        <h3 className="text-xs text-slate-400 uppercase tracking-wider mb-4 font-bold">Active Tool Execution Distribution</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(toolStats).map(([tool, count]: any) => (
            <div key={tool} className="bg-black/30 border border-white/5 rounded-xl p-3 flex flex-col justify-between">
              <span className="text-[10px] font-mono text-slate-400 truncate uppercase">{tool.replace(/_/g, " ")}</span>
              <div className="flex items-baseline gap-2 mt-2">
                <span className="text-xl font-bold font-mono text-emerald-400">{count}</span>
                <span className="text-[10px] text-slate-500 font-mono">calls</span>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
