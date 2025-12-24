"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Eye, EyeOff, KeyRound, Mail } from "lucide-react"

interface AuthFormProps extends React.HTMLAttributes<HTMLDivElement> {
  mode?: "login" | "signup"
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onEmailSubmit?: (data: any) => void
  onSocialSignIn?: (provider: 'google' | 'microsoft' | 'apple' | 'sso') => void
  onEmailLink?: () => void
}

const AuthForm = React.forwardRef<HTMLDivElement, AuthFormProps>(
  ({ className, mode = "login", onEmailSubmit, ...props }, ref) => {
    const [showPassword, setShowPassword] = React.useState(false)

    const handleFormSubmit = (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      const formData = new FormData(event.currentTarget)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const data: any = Object.fromEntries(formData.entries())
      onEmailSubmit?.(data)
    }

    return (
      <Card ref={ref} className={cn("w-full max-w-md mx-auto", className)} {...props}>
        <CardHeader className="text-left">
          <CardTitle className="text-2xl">
            {mode === "login" ? "Sign in" : "Create account"}
          </CardTitle>
          <CardDescription>
            {mode === "login"
              ? "Welcome back to Amplify."
              : "Start your leads discovery journey."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <form onSubmit={handleFormSubmit} className="space-y-4">
              {mode === "signup" && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="firstName">First name</Label>
                      <Input id="firstName" name="firstName" placeholder="John" required />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="lastName">Last name</Label>
                      <Input id="lastName" name="lastName" placeholder="Doe" required />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="role">Role (Optional)</Label>
                    <Input id="role" name="role" placeholder="Sales Manager" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="company">Company (Optional)</Label>
                    <Input id="company" name="company" placeholder="Acme Inc" />
                  </div>
                </>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="name@company.com"
                    className="pl-9"
                    required
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Password</Label>
                  {mode === "login" && (
                    <a href="#" className="text-sm font-medium text-primary hover:underline">
                      Forgot password?
                    </a>
                  )}
                </div>
                <div className="relative">
                  <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    className="pl-9 pr-10"
                    required
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 text-muted-foreground"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              <Button type="submit" className="w-full">
                {mode === "login" ? "Sign In" : "Create Account"}
              </Button>
            </form>
          </div>
        </CardContent>
        <CardFooter className="flex-col items-start space-y-4">
          <div className="text-sm text-muted-foreground text-center w-full">
            {mode === "login" ? (
              <>
                Don&apos;t have an account?{" "}
                <a href="/signup" className="underline hover:text-primary">Sign up</a>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <a href="/login" className="underline hover:text-primary">Sign in</a>
              </>
            )}
          </div>
          <p className="text-xs text-muted-foreground text-center w-full">
            By continuing, you agree to our{" "}
            <a href="#" className="underline hover:text-primary">Terms</a>{" "}
            &{" "}
            <a href="#" className="underline hover:text-primary">Privacy</a>
          </p>
        </CardFooter>
      </Card>
    )
  }
)
AuthForm.displayName = "AuthForm"

export { AuthForm }