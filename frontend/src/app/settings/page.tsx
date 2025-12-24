"use client"

import * as React from "react"
import Pricing from "@/components/ui/pricing-section"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
    DialogFooter,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { AlertTriangle } from "lucide-react"

export default function SettingsOverviewPage() {
    const [deleteConfirmation, setDeleteConfirmation] = React.useState("")
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = React.useState(false)

    const handleDeleteAccount = () => {
        if (deleteConfirmation === "DELETE") {
            // API call would go here
            console.log("Account deleted")
            setIsDeleteDialogOpen(false)
        }
    }

    return (
        <div className="space-y-12 max-w-6xl mx-auto">
            <div>
                <h2 className="text-xl font-semibold mb-4 text-foreground">Plan Overview</h2>
                <Pricing />
            </div>

            <div className="border border-red-200 dark:border-red-900/50 rounded-lg p-6 bg-red-50/50 dark:bg-red-900/10">
                <div className="flex items-start justify-between">
                    <div>
                        <h3 className="text-lg font-medium text-red-600 dark:text-red-500 mb-1">Danger Zone</h3>
                        <p className="text-sm text-muted-foreground">
                            Permanently delete your account and all of your content. This action is not reversible.
                        </p>
                    </div>
                    <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
                        <DialogTrigger asChild>
                            <Button variant="destructive">Delete Account</Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Are you absolutely sure?</DialogTitle>
                                <DialogDescription>
                                    This action cannot be undone. This will permanently delete your account and remove your data from our servers.
                                    <br /><br />
                                    Please type <strong>DELETE</strong> to confirm.
                                </DialogDescription>
                            </DialogHeader>
                            <div className="grid gap-4 py-4">
                                <div className="grid gap-2">
                                    <Label htmlFor="confirmation">Confirmation</Label>
                                    <Input
                                        id="confirmation"
                                        value={deleteConfirmation}
                                        onChange={(e) => setDeleteConfirmation(e.target.value)}
                                        placeholder="Type DELETE"
                                    />
                                </div>
                            </div>
                            <DialogFooter>
                                <Button
                                    variant="destructive"
                                    onClick={handleDeleteAccount}
                                    disabled={deleteConfirmation !== "DELETE"}
                                >
                                    Delete Account
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>
        </div>
    )
}
