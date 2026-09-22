import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ChevronsUpDown, Feather, KeyRound, Library, LogOut, Moon, Settings2, Sun, UserRound } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { SiteLogo, useDocumentMeta, useSite } from "@/lib/site";
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
  { to: "/library", label: "Library", icon: Library, end: true },
  { to: "/profiles", label: "Author profiles", icon: Feather },
];

function Brand() {
  const site = useSite();
  return (
    <NavLink to="/library" className="flex items-center gap-2.5 px-2 py-1.5">
      <SiteLogo />
      <span className="truncate text-[15px] font-semibold tracking-tight">{site.name}</span>
    </NavLink>
  );
}

function SidebarBody() {
  const { user, logout } = useAuth();
  const { resolved, setTheme } = useTheme();
  const navigate = useNavigate();
  const go = (to: string) => navigate(to);
  return (
    <>
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
  const { user } = useAuth();
  useDocumentMeta();
  const location = useLocation();
  const bottom = [
    { to: "/library", label: "Library", icon: Library, end: true },
    { to: "/profiles", label: "Authors", icon: Feather },
    ...(user?.role === "admin" ? [{ to: "/admin", label: "Settings", icon: Settings2 }] : []),
    { to: "/account", label: "Account", icon: UserRound },
  ];

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col border-r border-border bg-card/60 px-3 py-4 md:flex">
        <SidebarBody />
      </aside>

      <main className="main-surface min-w-0 flex-1">
        <div className="sticky top-0 z-40 flex items-center border-b border-border bg-background/90 px-2 py-1.5 backdrop-blur md:hidden">
          <Brand />
        </div>
        <div className="mx-auto w-full max-w-[1480px] px-0 pb-24 md:px-6 md:py-6 md:pb-8 xl:px-10">
          <div key={location.pathname} className="min-h-[calc(100vh-4rem)] bg-card px-4 py-6 md:min-h-0 md:rounded-[var(--radius-lg)] md:border md:border-border md:px-8 md:py-8 md:shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
            <Outlet />
          </div>
        </div>

        <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border bg-card/95 backdrop-blur md:hidden" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
          {bottom.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                cn("flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium text-muted-foreground", isActive && "text-primary")
              }
            >
              <n.icon className="h-5 w-5" />
              {n.label}
            </NavLink>
          ))}
        </nav>
      </main>
    </div>
  );
}
