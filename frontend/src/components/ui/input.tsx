import * as React from "react";
import { cn } from "@/lib/utils";

export const inputClass =
  "flex h-9 w-full rounded-[var(--radius-sm)] border border-border-strong bg-input px-3 text-sm text-foreground placeholder:text-subtle shadow-[0_1px_1px_rgba(0,0,0,0.03)] transition-[border-color,box-shadow] focus-visible:outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/20 disabled:opacity-50";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(inputClass, className)} {...props} />,
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea ref={ref} className={cn(inputClass, "h-auto min-h-[96px] py-2 leading-relaxed resize-y", className)} {...props} />
  ),
);
Textarea.displayName = "Textarea";

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("text-[13px] font-medium text-foreground", className)} {...props} />;
}

export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label?: string;
  hint?: string;
  error?: string | null;
  children: React.ReactNode;
  className?: string;
}) {
  // Link the label to the control so screen readers and click-to-focus work. A single child
  // element without its own id receives a generated one; anything else is left alone.
  const generated = React.useId();
  let control = children;
  let htmlFor: string | undefined;
  if (React.isValidElement(children)) {
    const props = children.props as { id?: string };
    htmlFor = props.id ?? generated;
    if (!props.id && typeof children.type === "string") control = React.cloneElement(children, { id: generated } as object);
    else if (!props.id) control = React.cloneElement(children, { id: generated } as object);
  }
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label ? <Label htmlFor={htmlFor}>{label}</Label> : null}
      {control}
      {error ? (
        <p className="text-[12.5px] text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-[12.5px] text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
