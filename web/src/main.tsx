import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App";
import { SystemActionsProvider } from "./contexts/SystemActions";
import { I18nProvider } from "./i18n";
import { exposePluginSDK } from "./plugins";
import { ThemeProvider } from "./themes";
import { HERMES_BASE_PATH } from "./lib/api";

const THEME_STORAGE_KEY = "hermes-dashboard-theme";
const OPS_THEME = "command-desk-ops";
const THEME_ALIASES: Record<string, string> = {
  "lens-5i": "nous-blue",
  default: OPS_THEME,
  "default-large": "command-desk-ops-large",
  midnight: OPS_THEME,
  ember: OPS_THEME,
  mono: OPS_THEME,
  cyberpunk: OPS_THEME,
  rose: OPS_THEME,
  "nous-blue": OPS_THEME,
};

/** Pre-apply Command Deck Ops palette before React mounts to avoid a teal flash. */
if (typeof window !== "undefined") {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY) ?? OPS_THEME;
  const themeName = THEME_ALIASES[stored] ?? stored;
  if (themeName !== stored) {
    window.localStorage.setItem(THEME_STORAGE_KEY, themeName);
  }
  const root = document.documentElement;
  root.style.setProperty("--background-base", "#060a10");
  root.style.setProperty("--midground-base", "#E8ECF2");
  root.style.setProperty("--foreground-base", "#ffffff");
  root.style.setProperty("--warm-glow", "rgba(125, 211, 252, 0.14)");
  root.style.setProperty("--noise-opacity-mul", "0.12");
  root.dataset.deckTheme = "ops";
}

// Expose the plugin SDK before rendering so plugins loaded via <script>
// can access React, components, etc. immediately.
exposePluginSDK();

createRoot(document.getElementById("root")!).render(
  <BrowserRouter basename={HERMES_BASE_PATH || undefined}>
    <I18nProvider>
      <ThemeProvider>
        <SystemActionsProvider>
          <App />
        </SystemActionsProvider>
      </ThemeProvider>
    </I18nProvider>
  </BrowserRouter>,
);
