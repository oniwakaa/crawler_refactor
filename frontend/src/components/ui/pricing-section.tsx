import * as React from "react";
import Link from "next/link";
import { CircleCheck } from "lucide-react";

// shadcn/ui bits
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// ---- minimal craft-ds inline (single-file helper) ----------------
import clsx, { type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

type SectionProps = { children: React.ReactNode; className?: string; id?: string };
type ContainerProps = { children: React.ReactNode; className?: string; id?: string };

const Section = ({ children, className, id }: SectionProps) => (
  <section className={cn("py-8 md:py-12", className)} id={id}>
    {children}
  </section>
);

const Container = ({ children, className, id }: ContainerProps) => (
  <div className={cn("mx-auto max-w-5xl p-6 sm:p-8", className)} id={id}>
    {children}
  </div>
);
// ------------------------------------------------------------------

type PlanTier = "Free" | "Pro" | "Enterprise";

interface PricingCardProps {
  title: PlanTier;
  price: string;
  description?: string;
  features: string[];
  cta: string;
  href: string;
  featured?: boolean;
}

// Dummy pricing data
const pricingData: PricingCardProps[] = [
  {
    title: "Free",
    price: "$0/month",
    description: "Get started with basic lead generation.",
    features: ["50 Leads/month", "Basic Search", "Email Support", "Community Access"],
    cta: "Current Plan",
    href: "#",
  },
  {
    title: "Pro",
    price: "$49/month",
    description: "Scale your outreach with advanced tools.",
    features: ["1,000 Leads/month", "Advanced Filters", "Export to CSV", "Priority Support"],
    cta: "Upgrade to Pro",
    href: "#",
    featured: true,
  },
  {
    title: "Enterprise",
    price: "Custom",
    description: "For large teams and high-volume needs.",
    features: ["Unlimited Leads", "API Access", "Dedicated Success Manager", "Custom Integrations"],
    cta: "Contact Sales",
    href: "/settings/contact",
  },
];


export default function Pricing() {
  return (
    <Section>
      <Container className="flex flex-col items-center gap-4 text-center">
        <h2 className="!my-0">Pricing</h2>
        <p className="text-lg opacity-70 md:text-2xl">Select the plan that best suits your needs.</p>

        <div className="not-prose mt-4 grid grid-cols-1 gap-6 min-[900px]:grid-cols-3">
          {pricingData.map((plan) => (
            <PricingCard key={plan.title} plan={plan} />
          ))}
        </div>
      </Container>
    </Section>
  );
}

function PricingCard({ plan }: { plan: PricingCardProps }) {
  return (
    <div
      className={cn(
        "flex flex-col rounded-lg border p-6 text-left",
        plan.featured && "border-primary shadow-sm ring-1 ring-primary/10"
      )}
      aria-label={`${plan.title} plan`}
    >
      <div className="text-center">
        <div className="inline-flex items-center gap-2">
          <Badge variant={plan.featured ? "default" : "secondary"}>{plan.title}</Badge>
          {plan.featured && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">Most popular</span>
          )}
        </div>
        <h4 className="mb-2 mt-4 text-2xl text-primary">{plan.price}</h4>
        {plan.description && <p className="text-sm opacity-70">{plan.description}</p>}
      </div>

      <div className="my-4 border-t" />

      <ul className="space-y-3">
        {plan.features.map((feature) => (
          <li key={feature} className="flex items-center text-sm opacity-80">
            <CircleCheck className="mr-2 h-4 w-4" aria-hidden />
            <span>{feature}</span>
          </li>
        ))}
      </ul>

      <div className="mt-auto pt-6">
        <Link href={plan.href} target="_blank" rel="noreferrer noopener">
          <Button size="sm" className="w-full" variant={plan.featured ? "default" : "secondary"}>
            {plan.cta}
          </Button>
        </Link>
      </div>
    </div>
  );
}
