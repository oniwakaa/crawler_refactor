"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { Download, CreditCard, FileX2 } from "lucide-react"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
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

export default function SettingsBillingPage() {
    const [isManagePlanOpen, setIsManagePlanOpen] = React.useState(false)
    const [selectedPlan, setSelectedPlan] = React.useState<string>("Pro")

    // Empty arrays - no mock data
    const invoices: any[] = []
    const paymentMethod = null // No payment method configured

    const availablePlans = [
        { id: "Free", name: "Free Plan", price: "$0/month" },
        { id: "Pro", name: "Pro Plan", price: "$49/month" },
        { id: "Enterprise", name: "Enterprise Plan", price: "Custom" },
    ]

    const handleSwitchPlan = (planId: string) => {
        setSelectedPlan(planId)
        // API call would go here
        console.log("Switching to plan:", planId)
        setIsManagePlanOpen(false)
    }

    const handleCancelSubscription = () => {
        // API call would go here
        console.log("Cancelling subscription")
        setIsManagePlanOpen(false)
    }

    return (
        <div className="space-y-8 max-w-5xl mx-auto">
            <div className="grid gap-6 md:grid-cols-2">
                <div className="rounded-lg border p-6">
                    <h3 className="text-lg font-medium mb-4">Current Plan</h3>
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-2xl font-bold">Free Plan</p>
                            <p className="text-sm text-muted-foreground">$0.00 / month</p>
                        </div>

                        <Dialog open={isManagePlanOpen} onOpenChange={setIsManagePlanOpen}>
                            <DialogTrigger asChild>
                                <Button variant="outline">Manage Plan</Button>
                            </DialogTrigger>
                            <DialogContent className="sm:max-w-[500px]">
                                <DialogHeader>
                                    <DialogTitle>Manage Your Subscription</DialogTitle>
                                    <DialogDescription>
                                        Switch to a different plan or cancel your subscription.
                                    </DialogDescription>
                                </DialogHeader>

                                <div className="space-y-6 py-4">
                                    <div className="space-y-3">
                                        <Label>Switch Plan</Label>
                                        <div className="space-y-2">
                                            {availablePlans.map((plan) => (
                                                <button
                                                    key={plan.id}
                                                    onClick={() => handleSwitchPlan(plan.id)}
                                                    className="w-full flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors text-left"
                                                >
                                                    <div>
                                                        <p className="font-medium">{plan.name}</p>
                                                        <p className="text-sm text-muted-foreground">{plan.price}</p>
                                                    </div>
                                                    {plan.id === "Free" && (
                                                        <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                                                            Current
                                                        </span>
                                                    )}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="border-t pt-4">
                                        <Label className="text-red-600 dark:text-red-500">Danger Zone</Label>
                                        <p className="text-sm text-muted-foreground mb-3 mt-1">
                                            Cancel your subscription and downgrade to Free plan.
                                        </p>
                                        <Button
                                            variant="destructive"
                                            className="w-full"
                                            onClick={handleCancelSubscription}
                                        >
                                            Cancel Subscription
                                        </Button>
                                    </div>
                                </div>
                            </DialogContent>
                        </Dialog>
                    </div>
                </div>

                <div className="rounded-lg border p-6">
                    <h3 className="text-lg font-medium mb-4">Payment Method</h3>
                    {paymentMethod ? (
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className="h-10 w-16 bg-muted rounded flex items-center justify-center">
                                    <CreditCard className="h-6 w-6 text-muted-foreground" />
                                </div>
                                <div>
                                    <p className="font-medium">Visa ending in 4242</p>
                                    <p className="text-sm text-muted-foreground">Expires 12/28</p>
                                </div>
                            </div>
                            <Button variant="ghost" size="sm">Update</Button>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-8 text-center">
                            <CreditCard className="h-12 w-12 text-muted-foreground mb-3" />
                            <p className="text-sm text-muted-foreground mb-4">
                                No payment method configured
                            </p>
                            <Button variant="outline" size="sm">Add Payment Method</Button>
                        </div>
                    )}
                </div>
            </div>

            <div className="rounded-lg border">
                <div className="p-6 border-b">
                    <h3 className="text-lg font-medium">Invoice History</h3>
                </div>
                {invoices.length > 0 ? (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Invoice</TableHead>
                                <TableHead>Date</TableHead>
                                <TableHead>Amount</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">Action</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {invoices.map((invoice) => (
                                <TableRow key={invoice.id}>
                                    <TableCell className="font-medium">{invoice.id}</TableCell>
                                    <TableCell>{invoice.date}</TableCell>
                                    <TableCell>{invoice.amount}</TableCell>
                                    <TableCell>
                                        <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
                                            {invoice.status}
                                        </span>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button variant="ghost" size="icon" asChild>
                                            <a href="#" download>
                                                <Download className="h-4 w-4" />
                                                <span className="sr-only">Download</span>
                                            </a>
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-center">
                        <FileX2 className="h-12 w-12 text-muted-foreground mb-3" />
                        <p className="text-sm text-muted-foreground">
                            No invoices yet. Your billing history will appear here.
                        </p>
                    </div>
                )}
            </div>
        </div>
    )
}
