"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
    Settings,
    LogOut,
    Menu,
    Plus,
} from "lucide-react"
import { createClient } from "@/lib/supabase/client"
import { useRouter } from "next/navigation"
import { useSidebar } from "@/contexts/sidebar-context"

export function AppSidebar() {
    const { isSidebarOpen, setIsSidebarOpen } = useSidebar()
    const pathname = usePathname()
    const router = useRouter()
    const supabase = createClient()

    const handleLogout = async () => {
        await supabase.auth.signOut()
        router.push("/login")
    }

    return (
        <aside
            className={cn(
                "relative flex flex-col border-r bg-muted/30 transition-all duration-300",
                isSidebarOpen ? "w-[280px]" : "w-[60px]"
            )}
        >
            {/* Logo Section */}
            <div className={cn("flex h-14 items-center px-4 lg:h-[60px]", isSidebarOpen ? "justify-between" : "justify-center")}>
                {isSidebarOpen && (
                    <Link href="/" className="flex items-center gap-2 font-semibold transition-opacity duration-200">
                        <span className="text-2xl font-extralight lowercase tracking-tighter text-foreground">
                            amplify
                        </span>
                    </Link>
                )}
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                    className="text-muted-foreground hover:text-foreground"
                >
                    <Menu className="h-5 w-5" />
                </Button>
            </div>

            {/* Conversation History / Navigation */}
            <div className="flex-1 py-4 overflow-hidden">
                <div className={cn("px-4 mb-4", !isSidebarOpen && "px-2")}>
                    <Button
                        className={cn(
                            "w-full justify-start gap-2 overflow-hidden",
                            !isSidebarOpen && "justify-center p-0"
                        )}
                        variant="outline"
                    >
                        <Plus className="h-4 w-4 shrink-0" />
                        {isSidebarOpen && "New Chat"}
                    </Button>
                </div>

                <ScrollArea className="h-[calc(100vh-250px)]">
                    <nav className="grid gap-1 px-2">
                        {/* Real Conversations will go here */}
                    </nav>
                </ScrollArea>
            </div>

            {/* Account Section */}
            <div className="border-t p-2">
                <div className="flex flex-col gap-1">
                    <Button
                        variant="ghost"
                        className={cn("justify-start gap-2", !isSidebarOpen && "justify-center")}
                        asChild
                    >
                        <Link href="/settings">
                            <Settings className="h-4 w-4 shrink-0" />
                            {isSidebarOpen && <span>Settings</span>}
                        </Link>
                    </Button>
                    <Button
                        variant="ghost"
                        className={cn("justify-start gap-2 text-red-500 hover:text-red-600 hover:bg-red-500/10", !isSidebarOpen && "justify-center")}
                        onClick={handleLogout}
                    >
                        <LogOut className="h-4 w-4 shrink-0" />
                        {isSidebarOpen && <span>Log out</span>}
                    </Button>
                </div>
            </div>
        </aside>
    )
}
