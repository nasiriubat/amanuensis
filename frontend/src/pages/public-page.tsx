import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { SiteLogo, useDocumentMeta, useSite } from "@/lib/site";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/misc";
import { RichMarkdown } from "@/components/rich-markdown";

interface PublicPage {
  slug: string;
  title: string;
  content: string;
}

export function PublicFrame({ children, title }: { children: React.ReactNode; title?: string }) {
  const site = useDocumentMeta(title);
  const { user } = useAuth();
  return (
    <div className="main-surface flex min-h-screen flex-col">
      <header className="border-b border-border bg-card/70 backdrop-blur">
        <div className="mx-auto flex w-full max-w-[1100px] items-center gap-3 px-5 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <SiteLogo />
            <span className="text-[15px] font-semibold tracking-tight">{site.name}</span>
          </Link>
          <nav className="ml-4 hidden items-center gap-1 sm:flex">
            {site.homepage !== "landing" ? (
              <Link to="/landing" className="rounded-md px-2.5 py-1.5 text-[13px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground">
                How it works
              </Link>
            ) : null}
            {site.nav_pages.map((p) => (
              <Link key={p.slug} to={`/p/${p.slug}`} className="rounded-md px-2.5 py-1.5 text-[13px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground">
                {p.title}
              </Link>
            ))}
          </nav>
          <div className="ml-auto">
            <Link to={user ? "/" : "/login"}>
              <Button size="sm" variant={user ? "secondary" : "primary"}>
                {user ? "Open workspace" : "Sign in"}
              </Button>
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1100px] flex-1 px-5 py-8">{children}</main>
      <footer className="border-t border-border py-5 text-center text-[12.5px] text-muted-foreground">
        {site.footer || `${site.name}`}
        {site.nav_pages.length ? (
          <span className="ml-3 sm:hidden">
            {site.nav_pages.map((p) => (
              <Link key={p.slug} to={`/p/${p.slug}`} className="mx-1.5 underline-offset-2 hover:underline">
                {p.title}
              </Link>
            ))}
          </span>
        ) : null}
      </footer>
    </div>
  );
}

export function PublicPageView({ slug: fixedSlug }: { slug?: string }) {
  const params = useParams();
  const slug = fixedSlug ?? params.slug ?? "";
  const page = useQuery({ queryKey: ["page", slug], queryFn: () => api.get<PublicPage>(`/api/pages/${slug}`), retry: false });
  const site = useSite();
  return (
    <PublicFrame title={page.data?.title}>
      {page.isLoading ? (
        <Skeleton className="h-64" />
      ) : page.data ? (
        <article className="mx-auto max-w-[760px] rounded-[var(--radius-lg)] border border-border bg-card px-6 py-8 sm:px-10">
          <RichMarkdown source={page.data.content} className="text-[15.5px]" />
        </article>
      ) : (
        <div className="py-20 text-center">
          <h1 className="text-[22px] font-semibold">Page not found</h1>
          <p className="mt-2 text-muted-foreground">This page does not exist or is not published.</p>
          <Link to="/" className="mt-4 inline-block text-primary hover:underline">
            Back to {site.name}
          </Link>
        </div>
      )}
    </PublicFrame>
  );
}
