"use strict";

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { runCommand } = require("../runners/powershell");

const DEFAULT_DASHBOARD = "http://127.0.0.1:9119";
const DEFAULT_API = "http://127.0.0.1:8642";

function fetchJson(url, timeoutMs = 8000) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      let body = "";
      res.on("data", (chunk) => { body += chunk; });
      res.on("end", () => {
        try {
          resolve({
            ok: res.statusCode >= 200 && res.statusCode < 300,
            status: res.statusCode,
            data: JSON.parse(body),
          });
        } catch {
          resolve({ ok: false, status: res.statusCode, error: "invalid json" });
        }
      });
    });
    req.on("error", (error) => resolve({ ok: false, error: error.message }));
    req.on("timeout", () => {
      req.destroy();
      resolve({ ok: false, error: "timeout" });
    });
  });
}

function readConfigYamlPlugins(homeDir) {
  const configPath = path.join(homeDir, "config.yaml");
  try {
    const text = fs.readFileSync(configPath, "utf8").replace(/\r\n/g, "\n");
    const enabledMatch = text.match(
      /plugins:\n\s*enabled:\n((?:\s+-\s+.+\n)+)/
    );
    if (!enabledMatch) return { pluginsEnabled: [], rtkPluginEnabled: false };
    const plugins = [...enabledMatch[1].matchAll(/-\s+(\S+)/g)].map((m) => m[1]);
    return {
      pluginsEnabled: plugins,
      rtkPluginEnabled: plugins.includes("rtk-rewrite"),
    };
  } catch {
    return { pluginsEnabled: [], rtkPluginEnabled: false };
  }
}

function expandUserPath(value) {
  if (!value || typeof value !== "string") return value;
  const home = process.env.USERPROFILE || "";
  const local = process.env.LOCALAPPDATA || "";
  return value
    .replace(/%USERPROFILE%/gi, home)
    .replace(/%LOCALAPPDATA%/gi, local);
}

async function collectCommandDesk(config) {
  const dashboardUrl = config.paths?.commandDeskDashboardUrl || `${DEFAULT_DASHBOARD}/api/status`;
  const apiHealthUrl = config.paths?.commandDeskApiHealthUrl || `${DEFAULT_API}/health`;
  const homeDir = expandUserPath(config.paths?.commandDeskHome || path.join(process.env.USERPROFILE || "", ".command-desk"));

  const result = {
    service: "Command Desk",
    available: false,
    version: null,
    dashboardUp: false,
    dashboardUrl: DEFAULT_DASHBOARD,
    apiHealth: false,
    apiUrl: DEFAULT_API,
    gatewayRunning: null,
    gatewayState: null,
    activeSessions: null,
    activeAgents: null,
    pluginsEnabled: [],
    rtkPluginEnabled: false,
    homeExists: fs.existsSync(homeDir),
    homeDir: homeDir.replace(process.env.USERPROFILE || "", "~"),
    cliVersion: null,
    reason: "Command Desk dashboard offline.",
  };

  const statusRes = await fetchJson(dashboardUrl);
  if (statusRes.ok && statusRes.data) {
    result.available = true;
    result.dashboardUp = true;
    result.version = statusRes.data.version || null;
    result.gatewayRunning = statusRes.data.gateway_running ?? null;
    result.gatewayState = statusRes.data.gateway_state ?? null;
    result.activeSessions = statusRes.data.active_sessions ?? null;
    result.activeAgents = statusRes.data.active_agents ?? null;
    result.reason = null;
  }

  const healthRes = await fetchJson(apiHealthUrl);
  result.apiHealth = healthRes.ok;

  const plugins = readConfigYamlPlugins(homeDir);
  result.pluginsEnabled = plugins.pluginsEnabled;
  result.rtkPluginEnabled = plugins.rtkPluginEnabled;

  const cli = expandUserPath(config.paths?.commandDeskCli);
  if (cli && fs.existsSync(cli)) {
    const verRun = await runCommand("cmd", ["/c", cli, "--version"], {
      timeoutMs: 15000,
      env: { COMMAND_DESK_HOME: homeDir, HERMES_HOME: homeDir },
    });
    if (verRun.ok) {
      result.cliVersion = verRun.stdout.trim().split("\n")[0];
      if (!result.version) result.version = result.cliVersion;
    }
  } else {
    const verRun = await runCommand("command-desk", ["--version"], {
      timeoutMs: 10000,
      env: { COMMAND_DESK_HOME: homeDir, HERMES_HOME: homeDir },
    });
    if (verRun.ok) {
      result.cliVersion = verRun.stdout.trim().split("\n")[0];
    }
  }

  if (!result.dashboardUp && result.homeExists) {
    result.reason = "Home presente; dashboard :9119 offline.";
  }

  return result;
}

module.exports = { collectCommandDesk, fetchJson };
