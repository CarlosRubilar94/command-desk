import { useLayoutEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { PageHeaderContext } from "./page-header-context";
import { resolvePageTitle } from "@/lib/resolve-page-title";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";

export function PageHeaderProvider({
  children,
  pluginTabs,
}: {
  children: ReactNode;
  pluginTabs: { path: string; label: string }[];
}) {
  const { pathname } = useLocation();
  const { t } = useI18n();
  const [titleOverride, setTitleOverride] = useState<string | null>(null);
  const [afterTitle, setAfterTitle] = useState<ReactNode>(null);
  const [end, setEnd] = useState<ReactNode>(null);

  useLayoutEffect(() => {
    setTitleOverride(null);
    setAfterTitle(null);
    setEnd(null);
  }, [pathname]);

  const defaultTitle = useMemo(
    () => resolvePageTitle(pathname, t, pluginTabs),
    [pathname, t, pluginTabs],
  );
  const displayTitle = titleOverride ?? defaultTitle;

  const isChatRoute = pathname === "/chat" || pathname === "/chat/";
  const isEnvRoute =
    pathname === "/env" || pathname.startsWith("/env/");

  const value = useMemo(
    () => ({
      setAfterTitle,
      setEnd,
      setTitle: setTitleOverride,
    }),
    [],
  );

  return (
    <PageHeaderContext.Provider value={value}>
      <div className="flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden">
        <header className="deck-app-header z-1 w-full shrink-0" role="banner">
          <div
            className={cn(
              "deck-header-left min-w-0 flex-1",
              isChatRoute
                ? "flex-row items-center gap-3"
                : "flex-col items-start gap-2 sm:flex-row sm:items-center sm:gap-3",
              afterTitle && isEnvRoute && "sm:flex-wrap",
            )}
          >
            <h1 className="min-w-0 truncate">{displayTitle}</h1>
            {afterTitle ? (
              <div
                className={cn(
                  "min-w-0 scrollbar-none",
                  isEnvRoute
                    ? "w-full overflow-x-auto sm:flex-1"
                    : "shrink-0 overflow-visible",
                )}
              >
                {afterTitle}
              </div>
            ) : null}
          </div>

          {end ? (
            <div className="deck-header-actions shrink-0">{end}</div>
          ) : null}
        </header>

        <main
          className={cn(
            "min-h-0 w-full min-w-0 flex-1 flex flex-col",
            isChatRoute
              ? "overflow-hidden"
              : "overflow-y-auto overflow-x-hidden [scrollbar-gutter:stable]",
          )}
        >
          {children}
        </main>
      </div>
    </PageHeaderContext.Provider>
  );
}
