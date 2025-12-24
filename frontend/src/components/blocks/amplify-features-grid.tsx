"use client";

import { FeatureCard } from "@/components/blocks/grid-feature-cards";
import {
    Bot,
    Search,
    Database,
    Zap,
    Filter,
    Download
} from "lucide-react";
import { motion } from "framer-motion";

export function AmplifyFeaturesGrid() {
    const features = [
        {
            title: "Natural Language Search",
            icon: Search,
            description: "Stop fiddling with filters. Just ask for 'Marketing Directors in NYC' and let AI handle the rest.",
        },
        {
            title: "AI-Powered Extraction",
            icon: Bot,
            description: "Our agents visit websites and profiles to find verified emails and phone numbers instantly.",
        },
        {
            title: "Real-Time Enrichment",
            icon: Database,
            description: "Get fresh data, not stale leads from a database. We scrape and verify in real-time.",
        },
        {
            title: "Smart Filtering",
            icon: Filter,
            description: "AI understands context. 'SaaS companies' captures software, cloud, and tech firms automatically.",
        },
        {
            title: "Lightning Fast",
            icon: Zap,
            description: "Parallel processing ensures you get hundreds of enriched leads in minutes, not hours.",
        },
        {
            title: "Export Ready",
            icon: Download,
            description: "One-click export to CSV or sync directly with your CRM for immediate outreach.",
        },
    ];

    return (
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, index) => (
                <motion.div
                    key={index}
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ margin: "-100px" }}
                    transition={{ duration: 0.5, delay: index * 0.1 }}
                    className="h-full"
                >
                    <FeatureCard
                        feature={feature}
                        className="border border-border/50 bg-muted/20 backdrop-blur-sm h-full"
                    />
                </motion.div>
            ))}
        </div>
    );
}
