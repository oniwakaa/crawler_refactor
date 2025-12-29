"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowRightIcon } from "lucide-react";
import { Mockup, MockupFrame } from "@/components/ui/mockup";
import { Glow } from "@/components/ui/glow";
import Image from "next/image";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

interface HeroAction {
  text: string;
  href: string;
  icon?: React.ReactNode;
  variant?: "default" | "glow";
}

import { TypingAnimation } from "@/components/ui/typing-animation";

interface HeroProps {
  badge?: {
    text: string;
    action: {
      text: string;
      href: string;
    };
  };
  title: string;
  subtitle?: string;
  description?: string;
  actions: HeroAction[];
  image: {
    light: string;
    dark: string;
    alt: string;
  };
  visual?: React.ReactNode;
}

export function HeroSection({
  badge,
  title,
  subtitle,
  description,
  actions,
  image,
  visual,
}: HeroProps) {
  const { resolvedTheme } = useTheme();
  const imageSrc = resolvedTheme === "light" ? image.light : image.dark;

  return (
    <section
      className={cn(
        "bg-background text-foreground",
        "py-12 sm:py-24 md:py-32 px-4",
        "fade-bottom overflow-hidden pb-0"
      )}
    >
      <div className="mx-auto flex max-w-container flex-col gap-12 pt-16 sm:gap-24">
        <div className="flex flex-col items-center gap-6 text-center sm:gap-12">

          {/* Brand Wordmark (Title) */}
          <h1 className="relative z-10 inline-block animate-appear text-5xl font-extralight lowercase leading-tight text-foreground drop-shadow-2xl sm:text-7xl sm:leading-tight md:text-9xl md:leading-tight tracking-tighter">
            {title}
          </h1>

          {/* Subtitle (Typing Animation) */}
          {subtitle && (
            <TypingAnimation
              text={subtitle}
              className="text-xl font-normal text-muted-foreground sm:text-2xl md:text-3xl"
            />
          )}

          {/* Legacy Description (Hidden if not used) */}
          {description && (
            <p className="text-md relative z-10 max-w-[550px] animate-appear font-medium text-muted-foreground opacity-0 delay-100 sm:text-xl">
              {description}
            </p>
          )}

          {/* Actions */}
          <div className="relative z-10 flex animate-appear justify-center gap-4 opacity-0 delay-300">
            <div className="relative z-10 flex animate-appear justify-center gap-4 opacity-0 delay-300">
              {actions.map((action, index) => (
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                <Button key={index} variant={action.variant as any} size="lg" asChild>
                  <a href={action.href} className="flex items-center gap-2">
                    {action.icon}
                    {action.text}
                  </a>
                </Button>
              ))}
            </div>
          </div>

          {/* Visual Content (Image or Component) */}
          <div className="relative pt-32 w-full">
            {visual ? (
              <div className="animate-appear opacity-0 delay-700 w-full">
                {visual}
              </div>
            ) : (
              <>
                <MockupFrame
                  className="animate-appear opacity-0 delay-700"
                  size="small"
                >
                  <Mockup type="responsive">
                    <Image
                      src={imageSrc}
                      alt={image.alt}
                      width={1248}
                      height={765}
                      priority
                    />
                  </Mockup>
                </MockupFrame>
                <Glow
                  variant="top"
                  className="animate-appear-zoom opacity-0 delay-1000"
                />
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
