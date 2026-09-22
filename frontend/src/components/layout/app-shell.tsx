import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { BookOpen, ChevronsUpDown, Feather, KeyRound, Library, LogOut, Menu, Moon, Settings2, Sun, UserRound, X } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { cn, initials } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const nav = [
  { to: "/", label: "Library", icon: Library, end: true },
  { to: "/profiles", label: "Author profiles", icon: Feather },
];

function Brand() {
  return (
    <NavLink to="/" className="flex items-center gap-2.5 px-2 py-1.5">
      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]">
        <BookOpen className="h-4 w-4" />
      </span>
      <span className="text-[15px] font-semibold tracking-tight">Paper Writer</span>
    </NavLink>
  );
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const { resolved, setTheme } = useTheme();
  const navigate = useNavigate();
  const go = (to: string) => {
    onNavigate?.();
    navigate(to);
  };
  return (
    <>
      <Brand />
        <nav className="mt-6 flex flex-col gap-0.5">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  isActive && "bg-muted text-foreground",
                )
              }
            >
              <n.icon className="h-4 w-4" />
              {n.label}
            </NavLink>
          ))}
          {user?.role === "admin" ? (
            <>
              <div className="mt-5 mb-1 px-2.5 text-[11px] font-medium uppercase tracking-wide text-subtle">Workspace</div>
              <NavLink
                to="/admin"
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                    isActive && "bg-muted text-foreground",
                  )
                }
              >
                <Settings2 className="h-4 w-4" />
                Settings
              </NavLink>
            </>
          ) : null}
        </nav>

        <div className="mt-auto">
          {user?.must_change_password ? (
            <button
              onClick={() => go("/account")}
              className="mb-2 flex w-full items-start gap-2 rounded-lg border border-warning/40 bg-warning-soft px-2.5 py-2 text-left text-[12px] leading-snug text-foreground"
            >
              <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
              <span>Change your temporary password.</span>
            </button>
          ) : null}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-muted">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[12px] font-semibold text-primary">
                  {initials(user?.display_name ?? "?")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium">{user?.display_name}</span>
                  <span className="block truncate text-[11.5px] text-muted-foreground">{user?.email}</span>
                </span>
                <ChevronsUpDown className="h-4 w-4 text-subtle" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="w-[208px]">
              <DropdownMenuLabel>{user?.role === "admin" ? "Administrator" : "Member"}</DropdownMenuLabel>
              <DropdownMenuItem onSelect={() => go("/account")}>
                <UserRound /> Account
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => setTheme(resolved === "dark" ? "light" : "dark")}>
                {resolved === "dark" ? <Sun /> : <Moon />}
                {resolved === "dark" ? "Light mode" : "Dark mode"}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => void logout().then(() => navigate("/login"))}>
                <LogOut /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
    </>
  );
}

export function AppShell() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col border-r border-border bg-card/60 px-3 py-4 md:flex">
        <SidebarBody />
      </aside>

      {/* Mobile: top bar with a drawer */}
      <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40 md:hidden" />
          <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col bg-card px-3 py-4 shadow-xl focus:outline-none md:hidden">
            <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
            <DialogPrimitive.Close className="absolute right-3 top-3 rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close menu">
              <X className="h-4 w-4" />
            </DialogPrimitive.Close>
            <SidebarBody onNavigate={() => setOpen(false)} />
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      <main className="main-surface min-w-0 flex-1">
        <div className="sticky top-0 z-40 flex items-center gap-2 border-b border-border bg-background/90 px-3 py-2 backdrop-blur md:hidden">
          <button onClick={() => setOpen(true)} className="rounded-md p-2 hover:bg-muted" aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <Brand />
        </div>
        <div key={location.pathname} className="mx-auto w-full max-w-[1480px] px-4 py-6 sm:px-6 md:px-8 md:py-8 xl:px-12">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
