"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { ArrowLeft } from "lucide-react"

interface SettingsLayoutProps {
    children: React.ReactNode
}

export default function SettingsLayout({ children }: SettingsLayoutProps) {
    const pathname = usePathname()

    const tabs = [
        { name: "Overview", href: "/settings" },
        { name: "Billing", href: "/settings/billing" },
        { name: "Contact", href: "/settings/contact" },
    ]

    return (
        <div className="min-h-screen bg-background">
            {/* Back Navigation */}
            <div className="border-b bg-background">
                <div className="container max-w-7xl px-6 py-6">
                    <Link
                        href="/dashboard"
                        className="inline-flex items-center gap-2.5 text-muted-foreground hover:text-foreground transition-colors group"
                    >
                        <ArrowLeft className="h-4 w-4 flex-shrink-0 translate-y-[1px]" />
                        <span className="text-xl font-extralight lowercase tracking-tighter leading-none">
                            amplify
                        </span>
                    </Link>
                </div>
            </div>

            {/* Main Content */}
            <main className="container max-w-7xl px-6 py-10">
                <div className="space-y-8">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
                        <p className="text-muted-foreground mt-1">
                            Manage your account settings and preferences.
                        </p>
                    </div>

                    {/* Tab Navigation */}
                    <div className="border-b">
                        <div className="flex space-x-8">
                            {tabs.map((tab) => {
                                const isSelected =
                                    tab.href === "/settings"
                                        ? pathname === "/settings"
                                        : pathname?.startsWith(tab.href)

                                return (
                                    <Link
                                        key={tab.name}
                                        href={tab.href}
                                        className={cn(
                                            "border-b-2 py-4 text-sm font-medium transition-colors hover:text-primary",
                                            isSelected
                                                ? "border-primary text-primary"
                                                : "border-transparent text-muted-foreground"
                                        )}
                                    >
                                        {tab.name}
                                    </Link>
                                )
                            })}
                        </div>
                    </div>

                    {/* Page Content */}
                    <div className="pb-8">
                        {children}
                    </div>
                </div>
            </main>
        </div>
    )
}
