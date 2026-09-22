import { Navigate, Outlet, RouterProvider, createBrowserRouter, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { AppShell } from "@/components/layout/app-shell";
import { LoginPage } from "@/pages/login";
import { LibraryPage, ProfilesPage } from "@/pages/library";
import { ProjectHomePage } from "@/pages/project-home";
import { ProfilePage } from "@/pages/profile-page";
import { AccountPage } from "@/pages/account";
import { AdminLayout } from "@/pages/admin/layout";
import { ProvidersPage } from "@/pages/admin/providers";
import { ModelsPage } from "@/pages/admin/models";
import { KindsPage } from "@/pages/admin/kinds";
import { HouseStylePage } from "@/pages/admin/house-style";
import { UsersPage } from "@/pages/admin/users";
import { UsagePage } from "@/pages/admin/usage";

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

const router = createBrowserRouter([
  {
    element: <PublicOnly />,
    children: [{ path: "/login", element: <LoginPage /> }],
  },
  {
    element: <RequireAuth />,
    children: [
      { path: "/", element: <LibraryPage /> },
      { path: "/profiles", element: <ProfilesPage /> },
      { path: "/profiles/:slug", element: <ProfilePage /> },
      { path: "/projects/:slug", element: <ProjectHomePage /> },
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
            ],
          },
        ],
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
