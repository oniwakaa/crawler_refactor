"use client";

import * as React from "react";
import { useEffect, useRef, useCallback, useState } from "react";
import { cn } from "@/lib/utils";
import {
    SendIcon,
    LoaderIcon,
    Paperclip
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useSidebar } from "@/contexts/sidebar-context";
import { createClient } from "@/lib/supabase/client";
import { AzureService } from "@/lib/api/azure";
import { User } from "@supabase/supabase-js";

// --- Types ---

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    data?: any[]; // For table data
    created_at: number;
}

interface UseAutoResizeTextareaProps {
    minHeight: number;
    maxHeight?: number;
}

// --- Hooks ---

function useAutoResizeTextarea({
    minHeight,
    maxHeight,
}: UseAutoResizeTextareaProps) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const adjustHeight = useCallback(
        (reset?: boolean) => {
            const textarea = textareaRef.current;
            if (!textarea) return;

            if (reset) {
                textarea.style.height = `${minHeight}px`;
                return;
            }

            textarea.style.height = `${minHeight}px`;
            const newHeight = Math.max(
                minHeight,
                Math.min(
                    textarea.scrollHeight,
                    maxHeight ?? Number.POSITIVE_INFINITY
                )
            );

            textarea.style.height = `${newHeight}px`;
        },
        [minHeight, maxHeight]
    );

    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = `${minHeight}px`;
        }
    }, [minHeight]);

    useEffect(() => {
        const handleResize = () => adjustHeight();
        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, [adjustHeight]);

    return { textareaRef, adjustHeight };
}

// --- Components ---

interface TextareaProps
    extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    containerClassName?: string;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
    ({ className, containerClassName, ...props }, ref) => {
        return (
            <div className={cn("relative", containerClassName)}>
                <textarea
                    className={cn(
                        "block min-h-[20px] w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-base text-white font-sans leading-[1.2]",
                        "transition-all duration-200 ease-in-out",
                        "placeholder:text-white/20",
                        "focus:outline-none focus:ring-0",
                        "resize-none",
                        "caret-white",
                        className
                    )}
                    ref={ref}
                    {...props}
                />
            </div>
        )
    }
)
Textarea.displayName = "Textarea"

// --- Main Chat Component ---

export function ChatInterface() {
    const [value, setValue] = useState("");
    const [messages, setMessages] = useState<Message[]>([]);
    const [isTyping, setIsTyping] = useState(false);
    const [user, setUser] = useState<User | null>(null);
    const [currentJobId, setCurrentJobId] = useState<string | null>(null);
    const supabase = createClient();
    const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 60, maxHeight: 200 });
    const { sidebarWidth } = useSidebar();

    useEffect(() => {
        const getUser = async () => {
            const { data: { user } } = await supabase.auth.getUser();
            setUser(user);
        };
        getUser();
    }, []);

    // Subscribe to leads when we have a job ID
    useEffect(() => {
        if (!currentJobId) return;

        const channel = supabase
            .channel('realtime-leads')
            .on(
                'postgres_changes',
                {
                    event: 'INSERT',
                    schema: 'public',
                    table: 'leads',
                    filter: `job_id=eq.${currentJobId}`
                },
                (payload) => {
                    const newLead = payload.new;
                    setMessages(prev => {
                        const lastMsg = prev[prev.length - 1];
                        if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === `resp-${currentJobId}`) {
                            // Update existing assistant message
                            return prev.map(msg => {
                                if (msg.id === `resp-${currentJobId}`) {
                                    return {
                                        ...msg,
                                        data: [...(msg.data || []), newLead]
                                    };
                                }
                                return msg;
                            });
                        } else {
                            // Create new assistant message if not exists (should rarely happen if we init it)
                            return prev;
                        }
                    });
                }
            )
            .subscribe();

        return () => {
            supabase.removeChannel(channel);
        };
    }, [currentJobId, supabase]);

    const scrollToBottom = () => {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    };

    useEffect(() => {
        if (messages.length > 0) {
            scrollToBottom();
        }
    }, [messages, isTyping]);

    const handleSendMessage = async () => {
        if (!value.trim()) return;

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: value,
            created_at: Date.now()
        };

        setMessages(prev => [...prev, userMsg]);
        setValue("");
        adjustHeight(true);
        setIsTyping(true);

        try {
            if (!user) {
                toast.error("You must be logged in to search.");
                setIsTyping(false);
                return;
            }

            // Start Azure Search
            const response = await AzureService.startSearch({
                query: value,
                user_id: user.id
            });

            const jobId = response.job_id;
            setCurrentJobId(jobId);

            // Create placeholder assistant message
            const assistantMsg: Message = {
                id: `resp-${jobId}`,
                role: 'assistant',
                content: "I've started searching. Results will appear as they are found...",
                created_at: Date.now(),
                data: []
            };
            setMessages(prev => [...prev, assistantMsg]);

        } catch (error) {
            console.error(error);
            toast.error("Failed to start search request");
        } finally {
            setIsTyping(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    const isEmpty = messages.length === 0;

    return (
        <div className={cn(
            "w-full bg-transparent text-white relative transition-all duration-500 font-sans",
            isEmpty ? "min-h-screen flex flex-col items-center justify-center p-6" : "min-h-screen pb-32 pt-20 px-6"
        )}>
            {/* Background Effects */}
            <div className="fixed inset-0 w-full h-full overflow-hidden -z-10 pointer-events-none">
                <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full mix-blend-normal filter blur-[128px] animate-pulse" />
                <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full mix-blend-normal filter blur-[128px] animate-pulse delay-700" />
            </div>

            {/* Messages Area */}
            {!isEmpty && (
                <div className="w-full max-w-3xl mx-auto space-y-8 mb-8">
                    <AnimatePresence>
                        {messages.map((msg) => (
                            <motion.div
                                key={msg.id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className={cn(
                                    "flex flex-col gap-2 max-w-[85%] w-fit",
                                    msg.role === 'user' ? "ml-auto" : "mr-auto"
                                )}
                            >
                                <div className={cn(
                                    "text-sm leading-relaxed text-white font-normal",
                                    msg.role === 'user'
                                        ? "bg-white/10 backdrop-blur-md px-4 py-2.5 rounded-2xl rounded-tr-sm"
                                        : "opacity-90 px-1"
                                )}>
                                    {msg.content}
                                </div>
                                {msg.data && (
                                    <div className="mt-4 border border-white/10 rounded-xl overflow-hidden bg-white/5 backdrop-blur-sm">
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm text-left">
                                                <thead className="bg-white/5 text-white/60">
                                                    <tr>
                                                        <th className="px-4 py-3 font-medium">Name</th>
                                                        <th className="px-4 py-3 font-medium">Company</th>
                                                        <th className="px-4 py-3 font-medium">Role</th>
                                                        <th className="px-4 py-3 font-medium">Email</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="text-white/80">
                                                    {msg.data.map((row, i) => (
                                                        <tr key={i} className="border-t border-white/5 hover:bg-white/5 transition-colors">
                                                            <td className="px-4 py-3">{row.name}</td>
                                                            <td className="px-4 py-3">{row.company}</td>
                                                            <td className="px-4 py-3">{row.role}</td>
                                                            <td className="px-4 py-3 font-mono text-xs opacity-70">{row.email}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}
                            </motion.div>
                        ))}
                    </AnimatePresence>

                    {isTyping && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="flex flex-col gap-1"
                        >
                            <div className="text-sm text-white/50 font-light animate-pulse">
                                Thinking...
                            </div>
                        </motion.div>
                    )}
                </div>
            )}

            {/* Input Container */}
            <motion.div
                layout
                className={cn(
                    "w-full max-w-2xl mx-auto relative z-20",
                    !isEmpty && "fixed bottom-8 px-6 mx-auto"
                )}
                style={!isEmpty ? {
                    left: `${sidebarWidth}px`,
                    right: 0,
                    width: `calc(100% - ${sidebarWidth}px)`,
                    maxWidth: '800px',
                    marginLeft: 'auto',
                    marginRight: 'auto'
                } : undefined}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            >
                {/* Empty State Header */}
                <AnimatePresence>
                    {isEmpty && (
                        <motion.div
                            className="text-center space-y-3 mb-8"
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -20, transition: { duration: 0.3 } }}
                        >
                            <h1 className="text-4xl font-medium tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 pb-1">
                                How can I help today?
                            </h1>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* The Input Box */}
                <motion.div
                    className="relative backdrop-blur-2xl bg-white/[0.03] rounded-2xl border border-white/[0.05] shadow-2xl transition-all duration-300 hover:bg-white/[0.05]"
                    layoutId="chat-input-container"
                >
                    <div className="p-4">
                        <Textarea
                            ref={textareaRef}
                            value={value}
                            onChange={(e) => {
                                setValue(e.target.value);
                                adjustHeight();
                            }}
                            onKeyDown={handleKeyDown}
                            placeholder="Ask Amplify to find Leads..."
                            className="bg-transparent border-none focus:ring-0 px-0 py-2.5 text-base min-h-[40px] max-h-[200px]"
                            containerClassName="border-none"
                        />
                    </div>

                    <div className="p-3 border-t border-white/[0.05] flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                            <button className="p-2 text-white/40 hover:text-white transition-colors rounded-lg hover:bg-white/5">
                                <Paperclip className="w-4 h-4" />
                            </button>
                        </div>
                        <Button
                            onClick={handleSendMessage}
                            disabled={!value.trim() || isTyping}
                            className={cn(
                                "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all h-auto",
                                value.trim() ? "bg-white text-black hover:bg-white/90" : "bg-white/5 text-white/30 cursor-not-allowed hover:bg-white/5"
                            )}
                        >
                            {isTyping ? <LoaderIcon className="w-4 h-4 animate-spin" /> : <SendIcon className="w-4 h-4" />}
                            <span>Send</span>
                        </Button>
                    </div>
                </motion.div>

                {/* Suggestion Chips (Empty State) */}
                <AnimatePresence>
                    {isEmpty && (
                        <div className="flex gap-2 flex-wrap justify-center mt-8">
                            {['Sales Managers in Italy', 'SaaS companies in Berlin', 'CTOs at Fintech startups'].map((suggestion, i) => (
                                <motion.button
                                    key={i}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0, transition: { delay: i * 0.1 } }}
                                    exit={{ opacity: 0, transition: { duration: 0.2 } }}
                                    onClick={() => setValue(suggestion)}
                                    className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-full text-sm text-white/70 hover:text-white transition-colors border border-white/5"
                                >
                                    {suggestion}
                                </motion.button>
                            ))}
                        </div>
                    )}
                </AnimatePresence>
            </motion.div>
        </div>
    );
}
