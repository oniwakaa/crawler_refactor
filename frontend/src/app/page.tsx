import { HeroSection } from "@/components/blocks/hero-section";
import { AmplifyFeaturesGrid } from "@/components/blocks/amplify-features-grid";
import { MinimalFooter } from "@/components/ui/minimal-footer";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <HeroSection
        title="amplify"
        subtitle="Find leads faster with natural language. No stress."
        actions={[
          {
            text: "Get Started",
            href: "/signup",
            variant: "default",
          },
          {
            text: "Sign In",
            href: "/login",
            variant: "glow",
          },
        ]}
        image={{
          light: "/amplify_dashboard_mockup.png",
          dark: "/amplify_dashboard_mockup.png",
          alt: "Amplify Lead Generation Dashboard",
        }}
        visual={<AmplifyFeaturesGrid />}
      />
      <MinimalFooter />
    </div>
  );
}
