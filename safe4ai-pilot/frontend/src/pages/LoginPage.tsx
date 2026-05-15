import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { login } from "../api/auth";
import Button from "../components/Button";
import Logo from "../components/Logo";

const schema = z.object({
  email:    z.string().email("Enter a valid email"),
  password: z.string().min(12, "Password must be at least 12 characters"),
});
type Form = z.infer<typeof schema>;

export default function LoginPage() {
  const [serverError, setServerError] = useState("");
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({
    resolver: zodResolver(schema),
  });

  async function onSubmit(data: Form) {
    setServerError("");
    try {
      await login(data.email, data.password);
      await qc.invalidateQueries({ queryKey: ["me"] });
      navigate("/chat");
    } catch {
      setServerError("Invalid credentials. Try again.");
    }
  }

  return (
    <div className="grid h-screen" style={{ gridTemplateColumns: "1fr 1.05fr" }}>
      {/* Left — dark brand panel */}
      <div className="relative flex flex-col justify-between bg-ink p-10 overflow-hidden">
        {/* Decorative rings */}
        <div className="absolute top-1/2 left-1/2 pointer-events-none" style={{ transform: "translate(-50%, -50%)" }}>
          <div className="absolute rounded-full border" style={{
            width: 420, height: 420,
            borderColor: "rgba(59,108,242,.08)",
            transform: "translate(-50%, -50%)",
          }} />
          <div className="absolute rounded-full border" style={{
            width: 280, height: 280,
            borderColor: "rgba(59,108,242,.12)",
            transform: "translate(-50%, -50%)",
          }} />
        </div>

        <div className="relative flex items-center gap-2.5">
          <Logo size={28} />
          <span className="font-medium text-[13.5px] tracking-tight" style={{ color: "#e8e6e0" }}>private·ai</span>
        </div>

        <div className="relative max-w-[340px]">
          <p className="font-mono text-[11px] uppercase mb-4" style={{ letterSpacing: "0.08em", color: "#7c8aa0" }}>
            Private AI · Enterprise RAG
          </p>
          <h2 className="font-serif text-[36px] italic leading-tight" style={{ color: "#f4f1ea" }}>
            Answers grounded in<br /><em style={{ color: "#7aa2f7" }}>your</em> documents
          </h2>
          <p className="mt-4 text-[13px] leading-relaxed" style={{ color: "#7c8aa0" }}>
            All retrieval happens on your infrastructure. Zero data leaves your network.
          </p>
        </div>

        <div className="relative flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "#2f8f5e" }} />
          <span className="font-mono text-[10.5px]" style={{ color: "#4a4f57" }}>All systems operational</span>
        </div>
      </div>

      {/* Right — sign-in form */}
      <div className="flex items-center justify-center bg-paper" style={{ padding: "60px 64px" }}>
        <div className="w-full max-w-[360px]">
          <div className="flex flex-col items-center mb-8">
            <h1 className="font-serif text-[28px] text-ink tracking-tight">Sign in</h1>
            <p className="mt-1 text-[13px] text-text-3">Access your workspace</p>
          </div>

          <p className="mb-4 text-center text-[11.5px] text-text-3">
            Sign in with your workspace credentials.
          </p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
            <div>
              <label className="block text-[12px] font-medium text-text-2 mb-1.5">Email</label>
              <input
                type="email"
                required
                autoComplete="email"
                {...register("email")}
                className={[
                  "w-full rounded border bg-surface px-3.5 py-2.5 text-[13.5px] text-text",
                  "placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-accent/30",
                  "transition-shadow",
                  errors.email ? "border-danger" : "border-line",
                ].join(" ")}
                placeholder="you@company.com"
              />
              {errors.email && <p className="mt-1 text-[11px] text-danger">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-[12px] font-medium text-text-2 mb-1.5">Password</label>
              <input
                type="password"
                required
                autoComplete="current-password"
                {...register("password")}
                className={[
                  "w-full rounded border bg-surface px-3.5 py-2.5 text-[13.5px] text-text",
                  "placeholder:text-text-mute focus:outline-none focus:ring-2 focus:ring-accent/30",
                  "transition-shadow",
                  errors.password ? "border-danger" : "border-line",
                ].join(" ")}
              />
              <p className="mt-1 text-[11px] text-text-3">
                Use at least 12 characters.
              </p>
              {errors.password && <p className="mt-1 text-[11px] text-danger">{errors.password.message}</p>}
            </div>

            <div className="text-right">
              <span className="text-[12px] text-text-mute">
                Password reset is unavailable in this pilot.
              </span>
            </div>

            {serverError && (
              <p className="rounded-lg bg-danger-soft border border-danger/20 px-3.5 py-2.5 text-[12.5px] text-danger">
                {serverError}
              </p>
            )}

            <Button variant="primary" size="lg" type="submit" loading={isSubmitting} className="w-full mt-1">
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
