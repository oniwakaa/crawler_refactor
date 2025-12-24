"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { AuthForm } from "@/components/ui/sign-in"
import { toast } from "sonner"

export default function SignupPage() {
    const router = useRouter()
    const supabase = createClient()

    const handleSignup = async (data: any) => {
        if (!data.password) return

        const { error } = await supabase.auth.signUp({
            email: data.email,
            password: data.password,
            options: {
                data: {
                    first_name: data.firstName,
                    last_name: data.lastName,
                    role: data.role,
                    company: data.company
                }
            }
        })

        if (error) {
            toast.error("Signup failed", {
                description: error.message,
            })
            return
        }

        toast.success("Confirm your email", {
            description: "We sent you a verification link.",
        })
    }

    return (
        <div className="flex min-h-screen items-center justify-center p-4">
            <AuthForm
                mode="signup"
                className="w-full max-w-sm"
                onEmailSubmit={handleSignup}
            />
        </div>
    )
}
