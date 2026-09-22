import * as React from "react";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/utils";

export const DropdownMenu = Dropdown.Root;
export const DropdownMenuTrigger = Dropdown.Trigger;

export const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof Dropdown.Content>,
  React.ComponentPropsWithoutRef<typeof Dropdown.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <Dropdown.Portal>
    <Dropdown.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn("z-[60] min-w-[180px] card-surface p-1 shadow-[0_12px_32px_-8px_rgba(16,24,40,0.2)] animate-in", className)}
      {...props}
    />
  </Dropdown.Portal>
));
DropdownMenuContent.displayName = "DropdownMenuContent";

export const DropdownMenuItem = React.forwardRef<
  React.ElementRef<typeof Dropdown.Item>,
  React.ComponentPropsWithoutRef<typeof Dropdown.Item> & { destructive?: boolean }
>(({ className, destructive, ...props }, ref) => (
  <Dropdown.Item
    ref={ref}
    className={cn(
      "relative flex cursor-pointer select-none items-center gap-2 rounded-md px-2 py-1.5 text-sm outline-none data-[highlighted]:bg-muted data-[disabled]:opacity-50 [&>svg]:h-4 [&>svg]:w-4 [&>svg]:text-muted-foreground",
      destructive && "text-destructive [&>svg]:text-destructive data-[highlighted]:bg-destructive-soft",
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = "DropdownMenuItem";

export const DropdownMenuSeparator = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof Dropdown.Separator>) => (
  <Dropdown.Separator className={cn("my-1 h-px bg-border", className)} {...props} />
);

export const DropdownMenuLabel = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof Dropdown.Label>) => (
  <Dropdown.Label className={cn("px-2 py-1.5 text-[11px] font-medium uppercase tracking-wide text-subtle", className)} {...props} />
);
