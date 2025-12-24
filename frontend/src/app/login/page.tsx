"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { AuthForm } from "@/components/ui/sign-in"
import { toast } from "sonner"

export default function LoginPage() {
    const router = useRouter()
    const supabase = createClient()

    const handleLogin = async (data: { email: string; password?: string }) => {
        if (!data.password) return

        const { error } = await supabase.auth.signInWithPassword({
            email: data.email,
            password: data.password,
        })

        if (error) {
            toast.error("Login failed", {
                description: error.message,
            })
            return
        }

        toast.success("Welcome back!")
        router.push("/dashboard")
    }

    return (
        <div className="flex min-h-screen items-center justify-center p-4">
            <AuthForm
                className="w-full max-w-sm"
                onEmailSubmit={handleLogin}
            />
        </div>
    )
}
