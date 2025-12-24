"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Send, CheckCircle2 } from "lucide-react"

export default function SettingsContactPage() {
    const [isSubmitted, setIsSubmitted] = React.useState(false)

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        // API call would go here
        setIsSubmitted(true)
        setTimeout(() => setIsSubmitted(false), 3000)
    }

    return (
        <div className="max-w-2xl mx-auto">
            <div className="mb-8">
                <h2 className="text-xl font-semibold mb-2">Contact Support</h2>
                <p className="text-muted-foreground">
                    Have a question or need help? Send us a message and we'll get back to you as soon as possible.
                </p>
            </div>

            {isSubmitted ? (
                <div className="rounded-lg border bg-green-50 dark:bg-green-900/10 p-8 text-center animate-in fade-in zoom-in duration-300">
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                        <CheckCircle2 className="h-6 w-6 text-green-600 dark:text-green-400" />
                    </div>
                    <h3 className="text-lg font-medium text-green-900 dark:text-green-100 mb-2">Message Sent!</h3>
                    <p className="text-sm text-green-700 dark:text-green-300">
                        Thank you for contacting us. We've received your message and will get back to you shortly.
                    </p>
                    <Button variant="outline" className="mt-6" onClick={() => setIsSubmitted(false)}>
                        Send another message
                    </Button>
                </div>
            ) : (
                <form onSubmit={handleSubmit} className="space-y-6">
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <Label htmlFor="name">Name</Label>
                            <Input id="name" placeholder="Your name" required />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <Input id="email" type="email" placeholder="name@example.com" required />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="subject">Subject</Label>
                        <Input id="subject" placeholder="How can we help?" required />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="message">Message</Label>
                        <Textarea
                            id="message"
                            placeholder="Please describe your issue or question..."
                            className="min-h-[150px]"
                            required
                        />
                    </div>

                    <div className="flex justify-end">
                        <Button type="submit" className="gap-2">
                            Send Message
                            <Send className="h-4 w-4" />
                        </Button>
                    </div>
                </form>
            )}
        </div>
    )
}
