"use client"

import * as React from "react"

interface SidebarContextType {
    isSidebarOpen: boolean
    setIsSidebarOpen: (open: boolean) => void
    sidebarWidth: number
}

const SidebarContext = React.createContext<SidebarContextType | undefined>(undefined)

export function SidebarProvider({ children }: { children: React.ReactNode }) {
    const [isSidebarOpen, setIsSidebarOpen] = React.useState(true)

    // Calculate sidebar width based on open/closed state
    const sidebarWidth = isSidebarOpen ? 280 : 60

    return (
        <SidebarContext.Provider value={{ isSidebarOpen, setIsSidebarOpen, sidebarWidth }}>
            {children}
        </SidebarContext.Provider>
    )
}

export function useSidebar() {
    const context = React.useContext(SidebarContext)
    if (context === undefined) {
        throw new Error("useSidebar must be used within a SidebarProvider")
    }
    return context
}
