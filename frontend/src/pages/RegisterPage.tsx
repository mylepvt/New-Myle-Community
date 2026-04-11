import { type FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Eye,
  EyeOff,
  IdCard,
  Info,
  Lock,
  Mail,
  Phone,
  Send,
  Sparkles,
  User,
  UserPlus,
} from 'lucide-react'

import { AuthCard } from '@/components/auth/AuthCard'
import { IconInput } from '@/components/auth/IconInput'
import { Button } from '@/components/ui/button'

function RequiredMark() {
  return (
    <span className="font-semibold text-primary" aria-hidden>
      *
    </span>
  )
}

function SectionTitle({ children }: { children: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="whitespace-nowrap text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {children}
      </span>
      <div className="h-px min-w-0 flex-1 bg-white/[0.08]" />
    </div>
  )
}

export function RegisterPage() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [uplineFboId, setUplineFboId] = useState('')
  const [phone, setPhone] = useState('')
  const [newJoining, setNewJoining] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitted(true)
  }

  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-[max(1rem,env(safe-area-inset-top))]">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
        <div className="absolute -left-20 top-[10%] h-80 w-80 rounded-full bg-primary/[0.08] blur-3xl" />
        <div className="absolute -right-20 bottom-[15%] h-72 w-72 rounded-full bg-white/[0.03] blur-3xl" />
      </div>

      <div className="relative z-[1] w-full max-w-[min(100%,26rem)]">
        <Link
          to="/login"
          className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4 shrink-0 opacity-80" aria-hidden />
          Back to sign in
        </Link>

        <AuthCard
          variant="split"
          icon={UserPlus}
          title="Join Myle Community"
          subtitle="Submit your registration request"
          footer={
            <p className="text-sm text-muted-foreground">
              Already have an account?{' '}
              <Link
                to="/login"
                className="inline-flex items-center gap-1 font-semibold text-primary hover:underline"
              >
                Sign In
                <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            </p>
          }
        >
          {submitted ? (
            <div
              className="rounded-xl border border-primary/35 bg-primary/[0.08] px-3 py-3 text-center text-sm text-foreground"
              role="status"
            >
              Self-service registration is not enabled for this workspace yet.
              Please contact your administrator.
            </div>
          ) : (
          <form className="space-y-6" onSubmit={handleSubmit} noValidate>
            <div className="space-y-3.5">
              <SectionTitle>Login credentials</SectionTitle>
              <div>
                <label
                  className="mb-1.5 flex flex-wrap items-baseline gap-1 text-sm font-semibold text-foreground"
                  htmlFor="reg-username"
                >
                  Username
                  <RequiredMark />
                </label>
                <IconInput
                  id="reg-username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Choose a username"
                  icon={User}
                />
              </div>
              <div>
                <label
                  className="mb-1.5 flex flex-wrap items-baseline gap-1 text-sm font-semibold text-foreground"
                  htmlFor="reg-email"
                >
                  Email
                  <RequiredMark />
                </label>
                <IconInput
                  id="reg-email"
                  type="email"
                  autoComplete="email"
                  inputMode="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  icon={Mail}
                />
              </div>
              <div>
                <label
                  className="mb-1.5 flex flex-wrap items-baseline gap-1 text-sm font-semibold text-foreground"
                  htmlFor="reg-password"
                >
                  Password
                  <RequiredMark />
                </label>
                <IconInput
                  id="reg-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a password"
                  icon={Lock}
                  endAdornment={
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowPassword((s) => !s)}
                      className="flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  }
                />
              </div>
            </div>

            <div className="space-y-3.5">
              <SectionTitle>Network details</SectionTitle>
              <div>
                <label
                  className="mb-1.5 flex flex-wrap items-baseline gap-1 text-sm font-semibold text-foreground"
                  htmlFor="reg-upline"
                >
                  Upline FBO ID
                  <RequiredMark />
                </label>
                <IconInput
                  id="reg-upline"
                  value={uplineFboId}
                  onChange={(e) => setUplineFboId(e.target.value)}
                  placeholder="e.g. FBO-12345"
                  icon={IdCard}
                />
                <p className="mt-2 flex items-start gap-2 text-xs italic leading-relaxed text-muted-foreground">
                  <Info
                    className="mt-0.5 size-3.5 shrink-0 text-primary/90"
                    aria-hidden
                  />
                  <span>Approved leader or admin FBO ID is accepted.</span>
                </p>
              </div>
            </div>

            <div className="space-y-3.5">
              <SectionTitle>Joining info</SectionTitle>
              <div>
                <label
                  className="mb-1.5 block text-sm font-semibold text-foreground"
                  htmlFor="reg-phone"
                >
                  Phone <span className="font-normal text-muted-foreground">(optional)</span>
                </label>
                <IconInput
                  id="reg-phone"
                  type="tel"
                  autoComplete="tel"
                  inputMode="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+1 …"
                  icon={Phone}
                />
              </div>

              <div className="rounded-2xl border border-white/[0.08] bg-muted/35 p-4">
                <label className="flex cursor-pointer gap-3 text-sm leading-relaxed text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={newJoining}
                    onChange={(e) => setNewJoining(e.target.checked)}
                    className="mt-1 size-4 shrink-0 rounded border-white/25 bg-muted/40 text-primary accent-primary focus:ring-2 focus:ring-primary/40"
                  />
                  <span className="min-w-0">
                    <span className="mb-1 flex flex-wrap items-center gap-2 font-semibold text-foreground">
                      <Sparkles className="size-4 text-primary" aria-hidden />
                      New Joining
                    </span>
                    <span className="text-muted-foreground">
                      Include me in the <strong className="font-semibold text-foreground">first time</strong> onboarding
                      track (7-day training program) when applicable.
                    </span>
                  </span>
                </label>
              </div>
            </div>

            <Button
              type="submit"
              variant="default"
              className="h-11 w-full gap-2 text-base font-semibold shadow-lg shadow-primary/20"
            >
              <Send className="size-4" aria-hidden />
              Submit registration request
            </Button>
          </form>
          )}
        </AuthCard>
      </div>
    </div>
  )
}
