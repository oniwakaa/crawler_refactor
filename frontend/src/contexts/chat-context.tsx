"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import { AzureService } from '@/lib/api/azure';

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    data?: any[];
    created_at?: string;
    metadata?: any;
}

export interface Conversation {
    id: string;
    title: string;
    created_at: string;
    user_id: string;
}

interface ChatContextType {
    conversations: Conversation[];
    messages: Message[];
    currentChatId: string | null;
    isLoading: boolean;
    createNewChat: () => void;
    selectChat: (id: string) => void;
    sendMessage: (content: string) => Promise<void>;
    refreshConversations: () => Promise<void>;
    deleteConversation: (id: string) => Promise<void>;
    setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export function ChatProvider({ children }: { children: React.ReactNode }) {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [messages, setMessages] = useState<Message[]>([]);
    const [currentChatId, setCurrentChatId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const supabase = createClient();

    const fetchConversations = useCallback(async () => {
        try {
            const { data: { user } } = await supabase.auth.getUser();
            if (!user) return;

            // Ensure we are selecting from the correct table as per user's schema
            const { data, error } = await supabase
                .from('conversations')
                .select('*')
                .eq('user_id', user.id)
                .order('created_at', { ascending: false });

            if (error) throw error;
            setConversations(data || []);
        } catch (error) {
            console.error('Error fetching conversations:', error);
        }
    }, [supabase]);

    useEffect(() => {
        fetchConversations();
    }, [fetchConversations]);

    const createNewChat = useCallback(() => {
        setCurrentChatId(null);
        setMessages([]);
    }, []);

    const selectChat = useCallback(async (id: string) => {
        setCurrentChatId(id);
        setIsLoading(true);
        setMessages([]); // Clear previous messages while loading
        try {
            const { data: messagesData, error } = await supabase
                .from('messages')
                .select('*')
                .eq('conversation_id', id)
                .order('created_at', { ascending: true });

            if (error) throw error;

            // Collect job IDs from messages
            const jobIds = messagesData
                .map((msg: any) => msg.metadata?.job_id)
                .filter(Boolean);

            // Fetch leads for these jobs
            let leadsMap: Record<string, any[]> = {};
            if (jobIds.length > 0) {
                const { data: leadsData, error: leadsError } = await supabase
                    .from('leads')
                    .select('*')
                    .in('job_id', jobIds);

                if (leadsError) {
                    console.error('Error fetching leads:', leadsError);
                } else {
                    leadsData?.forEach(lead => {
                        if (!leadsMap[lead.job_id]) leadsMap[lead.job_id] = [];
                        leadsMap[lead.job_id].push(lead);
                    });
                }
            }

            // Map Supabase messages to our Message interface
            const mappedMessages: Message[] = (messagesData || []).map(msg => ({
                id: msg.id,
                role: msg.role as 'user' | 'assistant',
                content: msg.content,
                // Attach leads if available, or fall back to empty array
                // metadata is typed as Json, so we access it safely
                data: leadsMap[msg.metadata?.job_id] || [],
                created_at: msg.created_at,
                // Store metadata so we can access job_id later if needed
                metadata: msg.metadata
            }));

            setMessages(mappedMessages);
        } catch (error) {
            console.error('Error fetching messages:', error);
            toast.error('Failed to load chat history');
        } finally {
            setIsLoading(false);
        }
    }, [supabase]);

    // Real-time subscription for Leads
    useEffect(() => {
        const channel = supabase.channel('global-leads-changes')
            .on(
                'postgres_changes',
                {
                    event: 'INSERT',
                    schema: 'public',
                    table: 'leads'
                },
                (payload) => {
                    const newLead = payload.new;
                    // Update messages if the lead belongs to one of the current messages' job
                    setMessages(prev => {
                        // Check if any message has this job_id
                        const hasJob = prev.some(msg => (msg as any).metadata?.job_id === newLead.job_id);
                        if (!hasJob) return prev;

                        return prev.map(msg => {
                            if ((msg as any).metadata?.job_id === newLead.job_id) {
                                return {
                                    ...msg,
                                    data: [...(msg.data || []), newLead]
                                };
                            }
                            return msg;
                        });
                    });
                }
            )
            .subscribe();

        return () => {
            supabase.removeChannel(channel);
        };
    }, [supabase]);

    const deleteConversation = useCallback(async (id: string) => {
        try {
            const { error } = await supabase
                .from('conversations')
                .delete()
                .eq('id', id);

            if (error) throw error;

            setConversations(prev => prev.filter(c => c.id !== id));
            if (currentChatId === id) {
                createNewChat();
            }
            toast.success('Conversation deleted');
        } catch (error) {
            console.error('Error deleting conversation:', error);
            toast.error('Failed to delete conversation');
        }
    }, [supabase, currentChatId, createNewChat]);

    const sendMessage = async (content: string) => {
        try {
            const { data: { user } } = await supabase.auth.getUser();
            if (!user) {
                toast.error("You must be logged in to send messages.");
                return;
            }

            let chatId = currentChatId;

            // Create new conversation if none exists
            if (!chatId) {
                const { data: newParams, error: newChatError } = await supabase
                    .from('conversations')
                    .insert({
                        user_id: user.id,
                        title: content.slice(0, 30) + (content.length > 30 ? '...' : ''), // Simple title generation
                    })
                    .select()
                    .single();

                if (newChatError) throw newChatError;
                chatId = newParams.id;
                setCurrentChatId(chatId);
                fetchConversations(); // Refresh list
            }

            if (!chatId) throw new Error("Failed to get chat ID");

            // 1. Add User Message to UI immediately
            const userMsg: Message = {
                id: Date.now().toString(), // Temp ID
                role: 'user',
                content,
                created_at: new Date().toISOString()
            };
            setMessages(prev => [...prev, userMsg]);

            // 2. Save User Message to DB
            const { error: msgError } = await supabase
                .from('messages')
                .insert({
                    conversation_id: chatId,
                    role: 'user',
                    content,
                    user_id: user.id
                });

            if (msgError) throw msgError;

            // 3. Trigger Azure Search (Background Job)
            // We pass the chatId so the backend can tag the job/leads
            // Assuming AzureService needs update or we handle the response manually here
            const response = await AzureService.startSearch({
                query: content,
                user_id: user.id,
                // conversation_id: chatId // Pass this if backend supports it, otherwise we link logic here
            });

            // 4. Create Assistant Message placeholder
            const assistantMsgId = `resp-${response.job_id}`;
            const assistantMsg: Message = {
                id: assistantMsgId,
                role: 'assistant',
                content: "I've started searching. Results will appear as they are found...",
                created_at: new Date().toISOString(),
                data: [],
                metadata: { job_id: response.job_id }
            };
            setMessages(prev => [...prev, assistantMsg]);

            // 5. Save Assistant Message to DB
            // We'll save the initial state. As leads come in, we might receive them via real-time but saving them to 'messages' metadata might be needed 
            // OR we rely on fetching 'leads' table joined with 'messages' later.
            // For now, let's save the basic message.
            await supabase
                .from('messages')
                .insert({
                    conversation_id: chatId,
                    role: 'assistant',
                    content: assistantMsg.content,
                    user_id: user.id,
                    metadata: { job_id: response.job_id } // Link to job
                });

        } catch (error) {
            console.error('Error sending message:', error);
            toast.error('Failed to send message');
            // Rollback UI updates if needed?
        }
    };

    return (
        <ChatContext.Provider value={{
            conversations,
            messages,
            currentChatId,
            isLoading,
            createNewChat,
            selectChat,
            sendMessage,
            refreshConversations: fetchConversations,
            deleteConversation,
            setMessages
        }}>
            {children}
        </ChatContext.Provider>
    );
}

export function useChat() {
    const context = useContext(ChatContext);
    if (context === undefined) {
        throw new Error('useChat must be used within a ChatProvider');
    }
    return context;
}
