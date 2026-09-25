import { NavLink, Outlet } from "react-router-dom";
import { Activity, BookType, Cpu, FileText, FlaskConical, Globe, HardDrive, Palette, Plug, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/ui/misc";

const items = [
  { to: "providers", label: "Providers", icon: Plug, hint: "API keys and endpoints" },
  { to: "models", label: "Models", icon: Cpu, hint: "Which model does what" },
  { to: "kinds", label: "Paper types", icon: BookType, hint: "Genres and their rules" },
  { to: "house-style", label: "House style", icon: Palette, hint: "Prose hygiene rules" },
  { to: "users", label: "Users", icon: Users, hint: "Members and roles" },
  { to: "site", label: "Site", icon: Globe, hint: "Name, logo, SEO" },
  { to: "pages", label: "Pages", icon: FileText, hint: "About, contact, homepage" },
  { to: "usage", label: "Usage", icon: Activity, hint: "Tokens and calls" },
  { to: "storage", label: "Storage", icon: HardDrive, hint: "Disk use and cleanup" },
  { to: "study", label: "Study", icon: FlaskConical, hint: "Usage events and study kit" },
];

export function AdminLayout() {
  return (
    <div className="animate-in">
      <PageHeader title="Settings" description="Workspace configuration. Only administrators see this." />
      <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
        <nav className="flex gap-0.5 overflow-x-auto pb-1 lg:sticky lg:top-8 lg:flex-col lg:self-start lg:overflow-visible lg:pb-0 [&>a]:shrink-0">
          {items.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  isActive && "bg-muted text-foreground font-medium",
                )
              }
            >
              <it.icon className="h-4 w-4" />
              <span className="flex flex-col leading-tight">
                {it.label}
                <span className="text-[11px] font-normal text-subtle">{it.hint}</span>
              </span>
            </NavLink>
          ))}
        </nav>
        <div className="min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
