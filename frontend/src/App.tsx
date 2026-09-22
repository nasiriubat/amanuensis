import { Navigate, Outlet, RouterProvider, createBrowserRouter, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { AppShell } from "@/components/layout/app-shell";
import { LoginPage } from "@/pages/login";
import { LibraryPage, ProfilesPage } from "@/pages/library";
import { ProjectHomePage } from "@/pages/project-home";
import { SourcesPage } from "@/pages/sources";
import { PlaybookPage } from "@/pages/playbook";
import { DesignPage } from "@/pages/design";
import { InterviewPage } from "@/pages/interview";
import { OutlinePage } from "@/pages/outline";
import { SpecPage } from "@/pages/spec";
import { StudioPage } from "@/pages/studio";
import { ReferencesPage } from "@/pages/references";
import { FiguresPage } from "@/pages/figures";
import { ExportPage } from "@/pages/export";
import { ProfilePage } from "@/pages/profile-page";
import { AccountPage } from "@/pages/account";
import { AdminLayout } from "@/pages/admin/layout";
import { ProvidersPage } from "@/pages/admin/providers";
import { ModelsPage } from "@/pages/admin/models";
import { KindsPage } from "@/pages/admin/kinds";
import { HouseStylePage } from "@/pages/admin/house-style";
import { UsersPage } from "@/pages/admin/users";
import { UsagePage } from "@/pages/admin/usage";
import { PagesPage, SitePage } from "@/pages/admin/site";
import { PublicPageView } from "@/pages/public-page";
import { useSite } from "@/lib/site";

function Splash() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-border border-t-primary" />
    </div>
  );
}

function RequireAuth() {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Splash />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <AppShell />;
}

function RequireAdmin() {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
}

function PublicOnly() {
  const { user, loading } = useAuth();
  if (loading) return <Splash />;
  if (user) return <Navigate to={user.must_change_password ? "/account" : "/"} replace />;
  return <Outlet />;
}

/** Root for visitors: the configured homepage page, or the sign-in page. */
function Root() {
  const { user, loading } = useAuth();
  const site = useSite();
  if (loading) return <Splash />;
  if (user) return <Navigate to={user.must_change_password ? "/account" : "/library"} replace />;
  if (site.homepage && site.homepage !== "login") return <PublicPageView slug={site.homepage} />;
  return <Navigate to="/login" replace />;
}

const router = createBrowserRouter([
  { path: "/", element: <Root /> },
  { path: "/p/:slug", element: <PublicPageView /> },
  {
    element: <PublicOnly />,
    children: [{ path: "/login", element: <LoginPage /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      { path: "/library", element: <LibraryPage /> },
      { path: "/profiles", element: <ProfilesPage /> },
      { path: "/profiles/:slug", element: <ProfilePage /> },
      { path: "/projects/:slug", element: <ProjectHomePage /> },
      { path: "/projects/:slug/sources", element: <SourcesPage /> },
      { path: "/projects/:slug/playbook", element: <PlaybookPage /> },
      { path: "/projects/:slug/design", element: <DesignPage /> },
      { path: "/projects/:slug/interview", element: <InterviewPage /> },
      { path: "/projects/:slug/outline", element: <OutlinePage /> },
      { path: "/projects/:slug/spec", element: <SpecPage /> },
      { path: "/projects/:slug/studio", element: <StudioPage /> },
      { path: "/projects/:slug/references", element: <ReferencesPage /> },
      { path: "/projects/:slug/figures", element: <FiguresPage /> },
      { path: "/projects/:slug/export", element: <ExportPage /> },
      { path: "/account", element: <AccountPage /> },
      {
        element: <RequireAdmin />,
        children: [
          {
            path: "/admin",
            element: <AdminLayout />,
            children: [
              { index: true, element: <Navigate to="providers" replace /> },
              { path: "providers", element: <ProvidersPage /> },
              { path: "models", element: <ModelsPage /> },
              { path: "kinds", element: <KindsPage /> },
              { path: "house-style", element: <HouseStylePage /> },
              { path: "users", element: <UsersPage /> },
              { path: "usage", element: <UsagePage /> },
              { path: "site", element: <SitePage /> },
              { path: "pages", element: <PagesPage /> },
            ],
          },
        ],
      },
      { path: "*", element: <Navigate to="/library" replace /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
