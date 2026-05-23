"use client";

import { useState, useEffect } from "react";
import Navbar from "@/components/layout/Navbar";
import LeftPanel from "@/components/layout/LeftPanel";
import RightPanel from "@/components/layout/RightPanel";
import ChatInterface from "@/components/chat/ChatInterface";
import dynamic from "next/dynamic";

const MetricsDashboard = dynamic(() => import("@/components/dashboard/MetricsDashboard"), {
  ssr: false,
  loading: () => <div className="flex-1 flex items-center justify-center text-slate-500 font-mono text-xs">Loading Live HUD Telemetry...</div>
});

export default function Home() {
  const [currentView, setCurrentView] = useState<"chat" | "dashboard">("chat");
  const [role, setRole] = useState("admin"); // Default to admin for full visibility, user can change
  const [activeAgents, setActiveAgents] = useState<string[]>([]);
  const [workflowTrigger, setWorkflowTrigger] = useState<string | undefined>();
  
  // Auth state
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    // Authenticate with backend when role changes
    const login = async () => {
      try {
        setToken(null); // Show loading overlay during auth swap
        const formData = new URLSearchParams();
        
        let username = "employee";
        let password = "emp123";
        
        if (role === "admin") {
          username = "admin";
          password = "admin123";
        } else if (role === "it_staff") {
          username = "support";
          password = "sup123";
        } else if (role === "manager") {
          username = "manager";
          password = "mgr123";
        }
        
        formData.append("username", username);
        formData.append("password", password);
        
        const res = await fetch("http://localhost:8000/api/auth/login", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: formData.toString()
        });
        const data = await res.json();
        if (data.access_token) {
          setToken(data.access_token);
        }
      } catch (err) {
        console.error("Login failed for role:", role, err);
      }
    };
    login();
  }, [role]);

  const handleWorkflowTrigger = (query: string) => {
    setWorkflowTrigger(query);
    setCurrentView("chat");
    setTimeout(() => {
      setWorkflowTrigger(undefined);
    }, 100);
  };

  if (!token) {
    return (
      <div className="h-screen w-screen bg-slate-950 flex flex-col items-center justify-center text-white font-mono gap-4">
        <div className="w-12 h-12 rounded-full border-t-2 border-r-2 border-blue-500 animate-spin"></div>
        <div className="animate-pulse tracking-widest text-xs uppercase text-blue-400">
          Establishing Secure connection ({role.replace("_", " ")})
        </div>
      </div>
    );
  }

  return (
    <main className="h-screen flex flex-col bg-slate-950 overflow-hidden text-slate-200">
      <Navbar />
      
      <div className="flex-1 flex overflow-hidden relative">
        <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none"></div>
        <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-purple-600/10 rounded-full blur-[120px] pointer-events-none"></div>
 
        <LeftPanel 
          currentView={currentView} 
          setView={setCurrentView} 
          onWorkflowTrigger={handleWorkflowTrigger}
          role={role}
          setRole={setRole}
        />
        
        <div className="flex-1 flex flex-col min-w-0 relative z-10 bg-black/20">
          {currentView === "chat" ? (
            <ChatInterface 
              role={role} 
              workflowMsg={workflowTrigger} 
              token={token} 
              onActiveAgentsChange={setActiveAgents}
            />
          ) : (
            <MetricsDashboard token={token} />
          )}
        </div>
 
        <RightPanel activeAgents={activeAgents} />
      </div>
    </main>
  );
}
