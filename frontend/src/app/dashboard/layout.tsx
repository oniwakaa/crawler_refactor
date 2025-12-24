"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { AppSidebar } from "@/components/dashboard/sidebar"
import { createClient } from "@/lib/supabase/client"
import { useRouter } from "next/navigation"
import { SidebarProvider } from "@/contexts/sidebar-context"

interface DashboardLayoutProps {
    children: React.ReactNode
}

function DashboardLayoutContent({ children }: DashboardLayoutProps) {
    const supabase = createClient()


    return (
        <div className="flex h-screen overflow-hidden bg-background">
            <AppSidebar />

            {/* Main Content */}
            <main className="flex-1 overflow-hidden relative">
                {children}
            </main>
        </div>
    )
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
    return (
        <SidebarProvider>
            <DashboardLayoutContent>{children}</DashboardLayoutContent>
        </SidebarProvider>
    )
}
