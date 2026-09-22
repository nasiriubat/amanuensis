import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { BookOpen, ChevronsUpDown, Feather, KeyRound, Library, LogOut, Moon, Settings2, Sun, UserRound } from "lucide-react";
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

export function AppShell() {
  const { user, logout } = useAuth();
  const { resolved, setTheme } = useTheme();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col border-r border-border bg-card/60 px-3 py-4 md:flex">
        <Brand />
        <nav className="mt-6 flex flex-col gap-0.5">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
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
              onClick={() => navigate("/account")}
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
              <DropdownMenuItem onSelect={() => navigate("/account")}>
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
      </aside>

      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-[1120px] px-5 py-8 md:px-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
