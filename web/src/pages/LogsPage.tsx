import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  useCallback,
  useRef,
} from "react";
import {
  FileText,
  RefreshCw,
  Search,
  X,
  Copy,
  Check,
  Download,
  WrapText,
  Layers,
  ArrowDown,
  Pause,
  Play,
} from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { FilterGroup, Segmented } from "@nous-research/ui/ui/components/segmented";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Switch } from "@nous-research/ui/ui/components/switch";
import { Input } from "@nous-research/ui/ui/components/input";
import { Card, CardContent, CardHeader, CardTitle } from "@nous-research/ui/ui/components/card";
import { Label } from "@nous-research/ui/ui/components/label";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";
import { cn } from "@/lib/utils";

const FILES = ["agent", "errors", "gateway"] as const;
const LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"] as const;
const COMPONENTS = ["all", "gateway", "agent", "tools", "cli", "cron"] as const;
const LINE_COUNTS = [50, 100, 200, 500] as const;

type LineLevel = "error" | "warning" | "info" | "debug";

function classifyLine(line: string): LineLevel {
  const upper = line.toUpperCase();
  if (
    upper.includes("ERROR") ||
    upper.includes("CRITICAL") ||
    upper.includes("FATAL")
  )
    return "error";
  if (upper.includes("WARNING") || upper.includes("WARN")) return "warning";
  if (upper.includes("DEBUG")) return "debug";
  return "info";
}

/** Map a selected level tab to the {@link classifyLine} bucket it filters to. */
const LEVEL_BUCKET: Record<
  Exclude<(typeof LEVELS)[number], "ALL">,
  LineLevel
> = {
  DEBUG: "debug",
  INFO: "info",
  WARNING: "warning",
  ERROR: "error",
};

const LINE_COLORS: Record<LineLevel, string> = {
  error: "text-destructive",
  warning: "text-warning",
  info: "text-foreground",
  debug: "text-text-tertiary",
};

/** Left accent bar per level — gives a scannable colour gutter. */
const LINE_BORDER: Record<LineLevel, string> = {
  error: "border-destructive/70",
  warning: "border-warning/70",
  info: "border-transparent",
  debug: "border-text-tertiary/40",
};

const formatFilterLabel = (value: string) => value.toUpperCase();

const toSegmentOptions = <T extends string>(values: readonly T[]) =>
  values.map((v) => ({ value: v, label: formatFilterLabel(v) }));

const filterGroupClass =
  "flex min-w-0 w-full flex-col items-start gap-1.5 sm:w-auto sm:max-w-full sm:flex-row sm:items-center";

const segmentedClass = "w-fit max-w-full flex-wrap justify-start self-start";

interface LineGroup {
  line: string;
  level: LineLevel;
  count: number;
  key: number;
}

export default function LogsPage() {
  const [file, setFile] = useState<(typeof FILES)[number]>("agent");
  const [level, setLevel] = useState<(typeof LEVELS)[number]>("ALL");
  const [component, setComponent] =
    useState<(typeof COMPONENTS)[number]>("all");
  const [lineCount, setLineCount] = useState<(typeof LINE_COUNTS)[number]>(100);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Presentation-only controls.
  const [query, setQuery] = useState("");
  const [wrap, setWrap] = useState(true);
  const [dedupe, setDedupe] = useState(true);
  const [follow, setFollow] = useState(true);
  const [copied, setCopied] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { t } = useI18n();
  const { setAfterTitle, setEnd } = usePageHeader();

  const fetchLogs = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .getLogs({ file, lines: lineCount, level, component })
      .then((resp) => setLines(resp.lines))
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [file, lineCount, level, component]);

  // Level filter is applied client-side so the tabs always narrow the view,
  // regardless of whether the backend honours the `level` query param.
  const filteredLines = useMemo(() => {
    let arr = lines;
    if (level !== "ALL") {
      const bucket = LEVEL_BUCKET[level];
      arr = arr.filter((l) => classifyLine(l) === bucket);
    }
    const q = query.trim().toLowerCase();
    if (q) arr = arr.filter((l) => l.toLowerCase().includes(q));
    return arr;
  }, [lines, level, query]);

  // Collapse consecutive identical lines (e.g. repeated auxiliary_client WARN).
  const groups = useMemo<LineGroup[]>(() => {
    if (!dedupe) {
      return filteredLines.map((line, i) => ({
        line,
        level: classifyLine(line),
        count: 1,
        key: i,
      }));
    }
    const out: LineGroup[] = [];
    for (let i = 0; i < filteredLines.length; i++) {
      const line = filteredLines[i];
      const last = out[out.length - 1];
      if (last && last.line === line) {
        last.count += 1;
      } else {
        out.push({ line, level: classifyLine(line), count: 1, key: i });
      }
    }
    return out;
  }, [filteredLines, dedupe]);

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    setFollow(nearBottom);
  }, []);

  const jumpToBottom = useCallback(() => {
    setFollow(true);
    scrollToBottom();
  }, [scrollToBottom]);

  // Keep pinned to the tail while following.
  useEffect(() => {
    if (!follow) return;
    const id = requestAnimationFrame(scrollToBottom);
    return () => cancelAnimationFrame(id);
  }, [groups, follow, wrap, scrollToBottom]);

  const onCopy = useCallback(() => {
    const text = filteredLines.join("\n");
    void navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 1500);
    });
  }, [filteredLines]);

  const onDownload = useCallback(() => {
    const text = filteredLines.join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const a = document.createElement("a");
    a.href = url;
    a.download = `${file}-${level.toLowerCase()}-${stamp}.log`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, [filteredLines, file, level]);

  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
    },
    [],
  );

  useLayoutEffect(() => {
    setAfterTitle(
      <span className="flex items-center gap-1.5">
        <Badge tone="secondary" className="text-xs">
          {formatFilterLabel(file)} · {formatFilterLabel(level)} ·{" "}
          {formatFilterLabel(component)}
        </Badge>
        <Button
          type="button"
          ghost
          size="icon"
          className="text-muted-foreground hover:text-foreground"
          onClick={fetchLogs}
          disabled={loading}
          aria-label={t.common.refresh}
        >
          {loading ? <Spinner /> : <RefreshCw />}
        </Button>
      </span>,
    );
    setEnd(
      <div className="flex w-full min-w-0 flex-wrap items-center justify-start gap-2 sm:justify-end sm:gap-3">
        <div className="flex items-center gap-2">
          <Label htmlFor="logs-auto-refresh" className="text-xs cursor-pointer">
            {t.logs.autoRefresh}
          </Label>
          <Switch
            checked={autoRefresh}
            onCheckedChange={setAutoRefresh}
            id="logs-auto-refresh"
          />
          {autoRefresh && (
            <Badge tone="success" className="text-xs">
              <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
              {t.common.live}
            </Badge>
          )}
        </div>
      </div>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [
    autoRefresh,
    component,
    file,
    level,
    loading,
    setAfterTitle,
    setEnd,
    t.common.live,
    t.common.refresh,
    t.logs.autoRefresh,
    fetchLogs,
  ]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchLogs]);

  const totalCount = lines.length;
  const shownCount = filteredLines.length;
  const isFiltered = level !== "ALL" || query.trim().length > 0;

  return (
    <div className="flex min-w-0 max-w-full flex-col gap-4">
      <PluginSlot name="logs:top" />
      <div
        role="toolbar"
        aria-label={t.logs.title}
        className="flex min-w-0 max-w-full flex-col items-start gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:gap-x-6 sm:gap-y-3"
      >
        <FilterGroup label={t.logs.file} className={filterGroupClass}>
          <Segmented
            className={segmentedClass}
            value={file}
            onChange={setFile}
            options={toSegmentOptions(FILES)}
          />
        </FilterGroup>

        <FilterGroup label={t.logs.level} className={filterGroupClass}>
          <Segmented
            className={segmentedClass}
            value={level}
            onChange={setLevel}
            options={toSegmentOptions(LEVELS)}
          />
        </FilterGroup>

        <FilterGroup label={t.logs.component} className={filterGroupClass}>
          <Segmented
            className={segmentedClass}
            value={component}
            onChange={setComponent}
            options={toSegmentOptions(COMPONENTS)}
          />
        </FilterGroup>

        <FilterGroup label={t.logs.lines} className={filterGroupClass}>
          <Segmented
            className={segmentedClass}
            value={String(lineCount)}
            onChange={(v) =>
              setLineCount(Number(v) as (typeof LINE_COUNTS)[number])
            }
            options={LINE_COUNTS.map((n) => ({
              value: String(n),
              label: String(n),
            }))}
          />
        </FilterGroup>
      </div>

      <Card className="min-w-0 max-w-full overflow-hidden">
        <CardHeader className="gap-3 px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4" />
              {file}.log
              <span className="font-mono-ui text-xs font-normal tabular-nums text-muted-foreground">
                {isFiltered
                  ? `${shownCount} / ${totalCount}`
                  : `${totalCount}`}
              </span>
            </CardTitle>

            <div className="flex min-w-0 flex-wrap items-center gap-1.5">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="h-8 w-40 rounded-none pl-8 pr-7 font-mono-ui text-xs sm:w-52"
                  placeholder={t.common.search}
                  value={query}
                  spellCheck={false}
                  onChange={(e) => setQuery(e.target.value)}
                />
                {query && (
                  <Button
                    ghost
                    size="icon"
                    className="absolute right-0.5 top-1/2 h-6 w-6 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    onClick={() => setQuery("")}
                    aria-label={t.common.clear}
                  >
                    <X />
                  </Button>
                )}
              </div>

              <Button
                size="sm"
                ghost={wrap}
                outlined={!wrap}
                onClick={() => setWrap((w) => !w)}
                aria-pressed={wrap}
                title="Toggle line wrap"
                prefix={<WrapText className="h-3.5 w-3.5" />}
                className="text-xs"
              >
                Wrap
              </Button>

              <Button
                size="sm"
                ghost={dedupe}
                outlined={!dedupe}
                onClick={() => setDedupe((d) => !d)}
                aria-pressed={dedupe}
                title="Collapse consecutive repeated lines"
                prefix={<Layers className="h-3.5 w-3.5" />}
                className="text-xs"
              >
                Dedupe
              </Button>

              <Button
                size="sm"
                ghost={follow}
                outlined={!follow}
                onClick={() => (follow ? setFollow(false) : jumpToBottom())}
                aria-pressed={follow}
                title={follow ? "Pause auto-scroll" : "Resume auto-scroll"}
                prefix={
                  follow ? (
                    <Pause className="h-3.5 w-3.5" />
                  ) : (
                    <Play className="h-3.5 w-3.5" />
                  )
                }
                className="text-xs"
              >
                {follow ? "Following" : "Paused"}
              </Button>

              <Button
                ghost
                size="icon"
                onClick={onCopy}
                disabled={shownCount === 0}
                aria-label="Copy logs"
                title="Copy visible lines"
                className="text-muted-foreground hover:text-foreground"
              >
                {copied ? (
                  <Check className="text-success" />
                ) : (
                  <Copy />
                )}
              </Button>

              <Button
                ghost
                size="icon"
                onClick={onDownload}
                disabled={shownCount === 0}
                aria-label="Download logs"
                title="Download visible lines"
                className="text-muted-foreground hover:text-foreground"
              >
                <Download />
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="relative p-0">
          {error && (
            <div className="border-b border-destructive/20 bg-destructive/10 p-3">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <div
            ref={scrollRef}
            onScroll={onScroll}
            className={cn(
              "max-w-full min-h-[400px] max-h-[calc(100vh-260px)] overflow-auto p-4 font-mono-ui text-xs leading-5",
              wrap ? "" : "whitespace-nowrap",
            )}
          >
            {groups.length === 0 && !loading && (
              <p className="py-8 text-center text-muted-foreground">
                {totalCount === 0 ? t.logs.noLogLines : t.common.noResults}
              </p>
            )}
            {groups.map((g) => (
              <div
                key={g.key}
                className={cn(
                  "-mx-1 border-l-2 px-2 hover:bg-secondary/20",
                  LINE_BORDER[g.level],
                  LINE_COLORS[g.level],
                  wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre",
                )}
              >
                {g.line || "\u00A0"}
                {g.count > 1 && (
                  <span
                    className="ml-2 inline-flex items-center rounded-sm border border-current/30 px-1 align-middle text-[0.6rem] tabular-nums opacity-80"
                    title={`${g.count} consecutive identical lines`}
                  >
                    ×{g.count}
                  </span>
                )}
              </div>
            ))}
          </div>

          {!follow && groups.length > 0 && (
            <Button
              size="sm"
              onClick={jumpToBottom}
              prefix={<ArrowDown className="h-3.5 w-3.5" />}
              className="absolute bottom-3 right-4 shadow-md"
            >
              Jump to bottom
            </Button>
          )}
        </CardContent>
      </Card>
      <PluginSlot name="logs:bottom" />
    </div>
  );
}
