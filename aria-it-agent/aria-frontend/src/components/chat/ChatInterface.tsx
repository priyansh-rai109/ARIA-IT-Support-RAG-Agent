"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Bot, User, Paperclip, CheckCircle2, Mic, MicOff, Volume2 } from "lucide-react";
import { cn } from "@/lib/utils";
import dynamic from "next/dynamic";

const HoloCore = dynamic(() => import("@/components/avatar/HoloCore"), {
  ssr: false,
  loading: () => <div className="w-full h-full bg-transparent" />
});

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: any[];
  tool_results?: any[];
  primary_agent?: string;
}

export default function ChatInterface({ 
  role, 
  workflowMsg, 
  token,
  onActiveAgentsChange
}: { 
  role: string, 
  workflowMsg?: string, 
  token?: string,
  onActiveAgentsChange?: (agents: string[]) => void
}) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Welcome to **ARIA**. I am the Master Orchestrator. How can I assist you with your IT needs today?",
      primary_agent: "orchestrator"
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  // Voice AI States
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  
  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const animationFrameRef = useRef<number>(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (workflowMsg) {
      handleSend(workflowMsg);
    }
  }, [workflowMsg]);

  // --- Voice AI: Speech-to-Text (STT) setup ---
  useEffect(() => {
    if (typeof window !== "undefined" && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;

      recognitionRef.current.onresult = (event: any) => {
        let interimTranscript = "";
        let finalTranscript = "";

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }
        
        if (finalTranscript) {
          setInput(prev => prev + " " + finalTranscript.trim());
          // Auto-send after a pause could go here, but for now we just append text
        }
      };

      recognitionRef.current.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsListening(false);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }
    
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      cancelAnimationFrame(animationFrameRef.current);
    };
  }, []);

  const toggleMicrophone = async () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      try {
        await navigator.mediaDevices.getUserMedia({ audio: true }); // Request permission
        recognitionRef.current?.start();
        setIsListening(true);
      } catch (err) {
        console.error("Microphone access denied", err);
      }
    }
  };

  // --- Voice AI: Text-to-Speech (TTS) & Audio Analysis ---
  const speakText = (text: string) => {
    if (!('speechSynthesis' in window)) return;
    
    // Stop any current speech
    window.speechSynthesis.cancel();
    setIsSpeaking(true);

    const utterance = new SpeechSynthesisUtterance(text);
    // Find a good voice (preferably a futuristic/female one depending on OS)
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(v => v.name.includes("Samantha") || v.name.includes("Google UK English Female") || v.name.includes("Zira"));
    if (preferredVoice) utterance.voice = preferredVoice;
    
    utterance.rate = 1.05;
    utterance.pitch = 1.1;

    // Simulate audio level since Web Speech API doesn't expose raw audio buffer easily
    // We will generate a fake audio level based on the speech state to animate the avatar
    let fakeAudioInterval: NodeJS.Timeout;
    
    utterance.onstart = () => {
      setIsSpeaking(true);
      fakeAudioInterval = setInterval(() => {
        // Generate random amplitude between 0.3 and 1.0 for lip sync
        setAudioLevel(0.3 + Math.random() * 0.7);
      }, 50);
    };

    utterance.onend = () => {
      setIsSpeaking(false);
      setAudioLevel(0);
      clearInterval(fakeAudioInterval);
    };

    utterance.onerror = () => {
      setIsSpeaking(false);
      setAudioLevel(0);
      clearInterval(fakeAudioInterval);
    };

    window.speechSynthesis.speak(utterance);
  };

  // --------------------------------------------------------

  const handleSend = async (text: string) => {
    if (!text.trim()) return;
    
    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    // Stop speaking if user interrupts by typing/sending
    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }

    try {
      // Append full message history as context
      const requestBody = { 
        message: text, 
        role, 
        use_workflows: true, 
        history: messages.map(m => ({ role: m.role, content: m.content })) 
      };

      // Clear active agents and set to orchestrator while processing
      onActiveAgentsChange?.(["orchestrator"]);

      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(requestBody)
      });
      
      const data = await res.json();
      
      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.text,
        sources: data.sources,
        tool_results: data.tool_results,
        primary_agent: data.primary_agent
      };
      
      setMessages(prev => [...prev, botMsg]);
      
      // Update active agents roster glow
      if (data.agents_involved) {
        onActiveAgentsChange?.(data.agents_involved);
      } else if (data.primary_agent) {
        onActiveAgentsChange?.([data.primary_agent]);
      }
      
      // Voice Output!
      // Strip markdown for TTS
      const cleanText = data.text.replace(/\*\*/g, "").replace(/#/g, "").replace(/`/g, "");
      speakText(cleanText);

    } catch (error) {
      setMessages(prev => [...prev, { id: Date.now().toString(), role: "assistant", content: "❌ Connection error to ARIA Orchestrator." }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== "application/pdf") {
      setMessages(prev => [...prev, { id: Date.now().toString(), role: "assistant", content: "❌ Only PDF files are supported currently." }]);
      return;
    }

    setIsLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/api/upload", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData
      });

      if (!res.ok) throw new Error("Upload failed");

      const data = await res.json();
      
      // We append a simulated user message containing the document text
      const extractedText = `[User uploaded document: ${file.name}]\n\nDocument Content:\n${data.text}`;
      
      const docMsg: Message = { id: Date.now().toString(), role: "user", content: `Uploaded ${file.name}` };
      setMessages(prev => [...prev, docMsg]);
      
      // Optionally trigger the bot immediately or wait for the user to ask a question
      setInput(`I just uploaded ${file.name}. Can you summarize it or tell me what it's about?`);
      
      // Behind the scenes, the extracted text will be sent in the next chat request as part of the history 
      // by temporarily modifying the last message, but for simplicity let's just push an invisible system message 
      // to history by setting it directly into the state.
      setMessages(prev => [...prev, { id: (Date.now() + 1).toString(), role: "user", content: extractedText }]);

    } catch (error) {
      setMessages(prev => [...prev, { id: Date.now().toString(), role: "assistant", content: `❌ Error uploading ${file.name}.` }]);
    } finally {
      setIsLoading(false);
      // reset file input
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col h-full relative">
      
      {/* 3D Holographic Avatar Background Layer */}
      <div className="absolute inset-0 pointer-events-none z-0 opacity-80 flex items-center justify-center overflow-hidden">
        <div className="w-[600px] h-[600px] relative flex items-center justify-center">
          {/* 3D HoloCore in the background */}
          <div className="absolute inset-0 w-full h-full z-0 opacity-60">
            <HoloCore isSpeaking={isSpeaking} audioLevel={audioLevel} isThinking={isLoading} />
          </div>
          
          {/* Semi-transparent robot overlay */}
          <div className="w-[500px] h-[500px] relative z-10 mix-blend-screen opacity-75">
            <motion.img 
              src="/robot.png" 
              alt="ARIA Hologram" 
              className="w-full h-full object-contain filter drop-shadow-[0_0_40px_rgba(59,130,246,0.4)]"
              animate={
                isSpeaking ? { 
                  scale: [1, 1.04, 1], 
                  filter: [
                    "drop-shadow(0 0 35px rgba(139,92,246,0.6)) brightness(1.1) contrast(1.1)",
                    "drop-shadow(0 0 55px rgba(139,92,246,0.9)) brightness(1.4) contrast(1.2)",
                    "drop-shadow(0 0 35px rgba(139,92,246,0.6)) brightness(1.1) contrast(1.1)"
                  ] 
                } :
                isLoading ? { 
                  opacity: [0.4, 0.8, 0.4], 
                  scale: [0.98, 1.02, 0.98],
                  filter: [
                    "drop-shadow(0 0 25px rgba(14,165,233,0.5)) brightness(1.0)",
                    "drop-shadow(0 0 60px rgba(14,165,233,0.8)) brightness(1.3)",
                    "drop-shadow(0 0 25px rgba(14,165,233,0.5)) brightness(1.0)"
                  ] 
                } :
                { 
                  y: [0, -12, 0],
                  filter: [
                    "drop-shadow(0 0 40px rgba(59,130,246,0.3)) brightness(1.0) contrast(1.0)",
                    "drop-shadow(0 0 50px rgba(59,130,246,0.5)) brightness(1.1) contrast(1.05)",
                    "drop-shadow(0 0 40px rgba(59,130,246,0.3)) brightness(1.0) contrast(1.0)"
                  ]
                }
              }
              transition={
                isSpeaking ? { repeat: Infinity, duration: 0.2 + (1 - audioLevel) * 0.3 } :
                isLoading ? { repeat: Infinity, duration: 1.5 } :
                { repeat: Infinity, duration: 5, ease: "easeInOut" }
              }
            />
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 relative z-10 scrollbar-hide">
        <div className="h-64 shrink-0"></div> {/* Spacer so messages don't immediately cover the avatar center */}
        
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              className={cn(
                "max-w-[85%] flex gap-4",
                msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
              )}
            >
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center shrink-0 border shadow-lg",
                msg.role === "user" 
                  ? "bg-indigo-600 border-indigo-400" 
                  : "bg-black/80 border-blue-500/50 shadow-[0_0_15px_rgba(59,130,246,0.3)] backdrop-blur-md"
              )}>
                {msg.role === "user" ? <User className="w-4 h-4 text-white" /> : <img src="/robot.png" alt="ARIA" className="w-5 h-5 object-contain" />}
              </div>
              
              <div className={cn(
                "px-5 py-4 rounded-2xl relative group",
                msg.role === "user" 
                  ? "bg-indigo-600/80 border border-indigo-500/30 text-indigo-50 backdrop-blur-md"
                  : "bg-black/60 border border-white/10 text-slate-200 backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
              )}>
                {/* Agent Badge for AI */}
                {msg.role === "assistant" && msg.primary_agent && (
                  <div className="absolute -top-3 -left-2 bg-black border border-white/20 text-[9px] uppercase tracking-wider px-2 py-0.5 rounded-full text-blue-400 flex items-center gap-1 shadow-md">
                    <span className={cn("w-1.5 h-1.5 rounded-full", isSpeaking ? "bg-purple-500 animate-pulse" : "bg-blue-500")}></span>
                    {msg.primary_agent.replace("_", " ")}
                  </div>
                )}
                
                {/* Message Content (simplified markdown for now) */}
                <div className="text-sm leading-relaxed whitespace-pre-wrap font-sans">
                  {msg.content}
                </div>

                {/* Tool Results */}
                {msg.tool_results && msg.tool_results.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-white/10 space-y-2">
                    <h5 className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Executed Actions</h5>
                    {msg.tool_results.map((t, i) => (
                      <div key={i} className="flex items-center gap-2 bg-white/5 border border-white/5 rounded-md px-3 py-2 text-xs font-mono text-slate-300">
                        <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                        <span>{t.tool_name}</span>
                        <span className="text-slate-500 mx-1">-</span>
                        <span className="text-emerald-400/80 truncate">{t.status || "completed"}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          ))}
          
          {isLoading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-4 max-w-[80%]">
              <div className="w-8 h-8 rounded-full bg-black/80 backdrop-blur-md border border-blue-500/50 flex items-center justify-center shadow-[0_0_15px_rgba(59,130,246,0.3)]">
                <img src="/robot.png" alt="ARIA" className="w-5 h-5 object-contain" />
              </div>
              <div className="px-5 py-4 rounded-2xl bg-black/60 border border-white/10 flex items-center gap-2 backdrop-blur-xl">
                <span className="w-2 h-2 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: "0ms" }}></span>
                <span className="w-2 h-2 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: "150ms" }}></span>
                <span className="w-2 h-2 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: "300ms" }}></span>
                <span className="ml-2 text-xs text-cyan-400 font-mono tracking-widest uppercase">Orchestrator Reasoning</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={endOfMessagesRef} className="h-4" />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-black/40 backdrop-blur-xl border-t border-white/10 relative z-20 shrink-0 shadow-[0_-10px_40px_rgba(0,0,0,0.5)]">
        
        {/* Voice Visualizer (only visible when listening) */}
        <AnimatePresence>
          {isListening && (
            <motion.div 
              initial={{ height: 0, opacity: 0 }} 
              animate={{ height: 30, opacity: 1 }} 
              exit={{ height: 0, opacity: 0 }}
              className="max-w-4xl mx-auto flex items-center justify-center gap-1 mb-2 overflow-hidden"
            >
              {[...Array(20)].map((_, i) => (
                <motion.div
                  key={i}
                  animate={{
                    height: [10, 15 + Math.random() * 15, 10],
                  }}
                  transition={{
                    repeat: Infinity,
                    duration: 0.5 + Math.random() * 0.5,
                  }}
                  className="w-1.5 bg-red-500 rounded-full shadow-[0_0_10px_rgba(239,68,68,0.8)]"
                />
              ))}
              <span className="ml-3 text-[10px] text-red-400 font-mono uppercase tracking-widest animate-pulse">Listening...</span>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="max-w-4xl mx-auto relative flex items-end gap-2 bg-black/60 border border-white/10 hover:border-blue-500/50 transition-colors rounded-2xl p-2 focus-within:border-blue-500 focus-within:shadow-[0_0_20px_rgba(59,130,246,0.2)]">
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            accept="application/pdf" 
            className="hidden" 
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            className="p-3 text-slate-400 hover:text-white transition-colors rounded-xl hover:bg-white/5"
            disabled={isLoading}
          >
            <Paperclip className="w-5 h-5" />
          </button>
          
          <textarea 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend(input);
              }
            }}
            placeholder={isListening ? "Listening for your voice..." : "Ask ARIA to troubleshoot, fix, or provision..."}
            className="flex-1 bg-transparent border-none text-white text-sm outline-none resize-none max-h-32 min-h-[44px] py-3 font-sans placeholder:text-slate-600"
            rows={1}
          />
          
          <button 
            onClick={toggleMicrophone}
            className={cn(
              "p-3 rounded-xl transition-all shadow-lg flex items-center justify-center shrink-0",
              isListening 
                ? "bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30 shadow-[0_0_15px_rgba(239,68,68,0.4)] animate-pulse" 
                : "bg-white/5 text-slate-400 hover:text-white hover:bg-white/10"
            )}
          >
            {isListening ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
          </button>

          <button 
            onClick={() => handleSend(input)}
            disabled={!input.trim() || isLoading}
            className="p-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-all disabled:opacity-50 disabled:hover:bg-blue-600 shadow-[0_0_15px_rgba(59,130,246,0.4)] shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <div className="max-w-4xl mx-auto flex justify-between mt-2 px-2">
          <span className="text-[10px] text-slate-500 flex items-center gap-2">
            <span className={cn("w-1.5 h-1.5 rounded-full", isSpeaking ? "bg-purple-500 animate-pulse" : "bg-emerald-500")}></span> 
            {isSpeaking ? "ARIA Speaks" : "Orchestrator Active"}
            {isSpeaking && <Volume2 className="w-3 h-3 text-purple-400 ml-1 animate-pulse" />}
          </span>
          <span className="text-[10px] text-slate-500">Press Enter to send, Shift+Enter for new line</span>
        </div>
      </div>
    </div>
  );
}
