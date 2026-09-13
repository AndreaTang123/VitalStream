"use client";

import { clsx } from "clsx";
import { ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variantClasses: Record<Variant, string> = {
  primary: "bg-accent text-slate-950 hover:bg-sky-400 disabled:bg-sky-900 disabled:text-slate-400",
  secondary: "bg-surface border border-border text-foreground hover:bg-slate-800",
  danger: "bg-danger text-slate-950 hover:bg-red-400 disabled:bg-red-950 disabled:text-slate-400",
  ghost: "bg-transparent text-muted hover:text-foreground hover:bg-surface",
};

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }
>(function Button({ variant = "primary", className, disabled, ...props }, ref) {
  return (
    <button
      ref={ref}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
});
