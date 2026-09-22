import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11.5px] font-medium leading-4 whitespace-nowrap",
  {
    variants: {
      variant: {
        neutral: "bg-muted text-muted-foreground border-transparent",
        outline: "bg-transparent text-muted-foreground border-border-strong",
        primary: "bg-primary-soft text-primary border-transparent",
        success: "bg-success-soft text-success border-transparent",
        warning: "bg-warning-soft text-warning border-transparent",
        destructive: "bg-destructive-soft text-destructive border-transparent",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export function Badge({ className, variant, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export function Dot({ className }: { className?: string }) {
  return <span className={cn("inline-block h-1.5 w-1.5 rounded-full bg-current", className)} />;
}
