import { useMemo, useRef, useState } from "react";
import { triggerDownload } from "../lib/download";
import { groupBy } from "../lib/group-by";
import type { GanttItem, TaskDependency } from "../types/api";

const HOUR_PX_DEFAULT = 12;
const HOUR_PX_MIN = 6;
const HOUR_PX_MAX = 24;

interface Props {
  items: GanttItem[];
  startDate: string;        // "YYYY-MM-DD"
  hoursPerDay: number;
  dependencies?: TaskDependency[];
  onTaskClick?: (key: string) => void;
  /** Рабочие часы от начала шкалы до «сегодня» — рисует линию-разделитель факт/прогноз. */
  todayHours?: number | null;
  /** Верхняя сводная полоса по User Story (суммарная длительность каждой стори). */
  groupByStory?: boolean;
  /** Сводная полоса по эпикам — рисуется выше полосы стори. */
  groupByEpic?: boolean;
  /** Консолидированная полоса — по непосредственному родителю задачи. */
  groupByParent?: boolean;
  /** Активный спринт — рисуем вертикальные границы спринтов и их номера. */
  sprintInfo?: { sprint_num: number | null; start_date: string; end_date: string } | null;
  /** owner_id → task_key — стартовые задачи сотрудников, отмечаются якорем 📌 на баре. */
  rootTasks?: Record<string, string>;
}

const BUCKET_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  "Анализ":          { bg: "#fef3c7", text: "#92400e", border: "#d97706" },
  "Разработка":      { bg: "#d1fae5", text: "#065f46", border: "#059669" },
  "Разработка фронт": { bg: "#bbf7d0", text: "#14532d", border: "#22c55e" },
  "Разработка бек":   { bg: "#c7d2fe", text: "#312e81", border: "#6366f1" },
  "Код-ревью":    { bg: "#a7f3d0", text: "#064e3b", border: "#047857" },
  "Тестирование": { bg: "#dbeafe", text: "#1e3a5f", border: "#2563eb" },
  "Дизайн":       { bg: "#fce7f3", text: "#831843", border: "#db2777" },
  "Дизайн-ревью": { bg: "#f5d0fe", text: "#581c87", border: "#a855f7" },
  "Релиз":        { bg: "#fef9c3", text: "#713f12", border: "#ca8a04" },
  "Руководство":  { bg: "#ede9fe", text: "#4c1d95", border: "#7c3aed" },
  "Отсутствие":   { bg: "#f3f4f6", text: "#374151", border: "#9ca3af" },
  "Отпуск":       { bg: "#fff7ed", text: "#9a3412", border: "#f97316" },
  "Story":        { bg: "#e0e7ff", text: "#3730a3", border: "#6366f1" },
  "Epic":         { bg: "#ddd6fe", text: "#5b21b6", border: "#7c3aed" },
  "Консолид.":    { bg: "#ccfbf1", text: "#115e59", border: "#14b8a6" },
};
const DEFAULT_COLOR = { bg: "#f3f4f6", text: "#374151", border: "#9ca3af" };

const ROW_H    = 36;   // px высота строки
const ROW_GAP  = 4;    // px между строками
const LABEL_W  = 160;  // px ширина колонки с именем
const HEADER_H = 48;   // px высота шапки дат
const BAND_GAP = 16;   // px разделитель между секциями (полосы сводов / детальная сетка)

function bucketColor(bucket: string) {
  return BUCKET_COLORS[bucket] ?? DEFAULT_COLOR;
}

/** Для бакета «Разработка» различаем фронт/бек по роли исполнителя (developer_frontend / developer_backend). */
function devBucketLabel(item: GanttItem): string {
  if (item.bucket !== "Разработка") return item.bucket;
  const r = (item.role || "").toLowerCase();
  if (r.includes("frontend") || r.includes("фронт")) return "Разработка фронт";
  if (r.includes("backend") || r.includes("бэк") || r.includes("бек")) return "Разработка бек";
  return item.bucket;
}

/** Короткая подпись бакета для бара (чтобы не уезжать за пределы прямоугольника). */
function shortBucketLabel(bucket: string): string {
  if (bucket === "Разработка фронт") return "Фронт";
  if (bucket === "Разработка бек") return "Бек";
  return bucket;
}

/** Обрезать подпись бара под его пиксельную ширину (~5.7px/символ при fontSize=10). */
function truncateForBar(full: string, w: number, padding: number): string {
  const maxChars = Math.max(3, Math.floor((w - padding) / 5.7));
  return full.length > maxChars ? full.slice(0, maxChars - 1) + "…" : full;
}

/** Человекочитаемая роль по имени роли из конфига (analyst/Tester/developer_lead/…). */
function roleLabel(role: string): string {
  const r = (role || "").toLowerCase();
  if (!r) return "";
  if (r.includes("lead") || r.includes("лид")) {
    if (r.includes("design") || r.includes("диз")) return "Лид дизайна";
    if (r.includes("dev") || r.includes("разраб")) return "Лид разработки";
    return "Лид";
  }
  if (r.startsWith("test") || r.includes("qa") || r.includes("тест")) return "Тестировщик";
  if (r.startsWith("analyst") || r.includes("анал")) return "Аналитик";
  if (r.startsWith("design") || r.includes("диз")) return "Дизайнер";
  if (r.startsWith("dev") || r.includes("разраб")) return "Разработчик";
  return role;
}

function fmtDate(d: Date): string {
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}
function fmtDay(d: Date): string {
  return d.toLocaleDateString("ru-RU", { weekday: "short" });
}

interface Tooltip {
  x: number; y: number;
  item: GanttItem;
}

interface Band {
  kind: string;            // bucket-цвет (Epic / Story)
  title: string;           // подпись секции
  items: GanttItem[];      // агрегированные «колбасы»
  y0: number;              // верхняя Y секции в SVG
}

/** Свернуть бары задач/фаз в одну суммарную «колбасу» на группу (по стори/эпику). */
function aggregateBars(
  items: GanttItem[],
  keyOf: (i: GanttItem) => string | null | undefined,
  summaryOf: (i: GanttItem) => string | null | undefined,
  bucket: string,
): GanttItem[] {
  const groups: Record<string, GanttItem[]> = {};
  const order: string[] = [];
  for (const it of items) {
    if (it.is_pseudo) continue;
    const k = keyOf(it);
    if (!k) continue;   // нет предка нужного типа — в свод не попадает
    if (!groups[k]) { groups[k] = []; order.push(k); }
    groups[k].push(it);
  }
  return order.map((k) => {
    const g = groups[k];
    // Веха «Релиз» не растягивает сводную полосу — на своде она не отображается.
    const nonRelease = g.filter((i) => i.bucket !== "Релиз");
    const spanItems = nonRelease.length ? nonRelease : g;
    const startItem = spanItems.reduce((a, b) => (a.start_hours < b.start_hours ? a : b));
    const endItem = spanItems.reduce((a, b) => (a.end_hours > b.end_hours ? a : b));
    const summary = g.map(summaryOf).find(Boolean) || g[0].summary || k;
    // URL самой группы (стори/эпика), а не дочерней задачи: подменяем ключ в /browse/<key>
    const sampleUrl = g.find((i) => i.url)?.url || "";
    const url = sampleUrl ? sampleUrl.replace(/\/browse\/[^/]+$/, `/browse/${k}`) : "";
    return {
      key: k,
      summary,
      bucket,
      role: "",
      owner_id: k,
      owner_file_name: `${k} · ${summary}`,
      hours: g.reduce((s, i) => s + (i.hours || 0), 0),
      is_pseudo: false,
      url,
      direction: null,
      start: startItem.start,
      end: endItem.end,
      start_hours: startItem.start_hours,
      end_hours: endItem.end_hours,
    } as GanttItem;
  });
}

export function GanttChart({ items, startDate, hoursPerDay, dependencies = [], onTaskClick, todayHours, groupByStory = false, groupByEpic = false, groupByParent = false, sprintInfo = null, rootTasks = {} }: Props) {
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [hourPx, setHourPx] = useState(HOUR_PX_DEFAULT);
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  // Агрегаты для верхних полос
  const epicItems = useMemo(
    () => aggregateBars(items, (i) => i.epic_key, (i) => i.epic_summary, "Epic"),
    [items],
  );
  const storyItems = useMemo(
    () => aggregateBars(items, (i) => i.story_key, (i) => i.story_summary, "Story"),
    [items],
  );
  const parentItems = useMemo(
    () => aggregateBars(items, (i) => i.parent_key, (i) => i.parent_summary, "Консолид."),
    [items],
  );

  const handleBarClick = (item: GanttItem) => {
    if (item.is_pseudo) return;

    if (clickTimerRef.current) {
      // Второй клик раньше таймера — двойной клик → открываем Jira
      clearTimeout(clickTimerRef.current);
      clickTimerRef.current = null;
      if (item.url) window.open(item.url, "_blank");
    } else {
      // Первый клик — ждём второго
      clickTimerRef.current = setTimeout(() => {
        clickTimerRef.current = null;
        // Одиночный клик → выделяем все этапы задачи/группы
        setSelectedKey((prev) => (prev === item.key ? null : item.key));
        if (onTaskClick) onTaskClick(item.key);
      }, 260);
    }
  };

  const dayPx = hoursPerDay * hourPx;

  // Группировка по исполнителю (нижний грид)
  const owners = useMemo(() => {
    const order: string[] = [];
    const seen = new Set<string>();
    for (const it of items) {
      if (!seen.has(it.owner_file_name)) {
        order.push(it.owner_file_name);
        seen.add(it.owner_file_name);
      }
    }
    return order;
  }, [items]);

  const byOwner = useMemo(() => {
    const m: Record<string, GanttItem[]> = {};
    for (const it of items) {
      (m[it.owner_file_name] ??= []).push(it);
    }
    return m;
  }, [items]);

  // Задачи, чей ТЕКУЩИЙ реальный статус в Jira — «готово к релизу» / «перенесено
  // на PROD», но сама задача ещё не выполнена. Это последняя историчная фаза с
  // bucket «Релиз», которая ещё не закрылась (её конец совпадает с «сейчас»).
  const pendingRelease = useMemo(() => {
    if (todayHours == null) return [];
    return items.filter(
      (i) => i.bucket === "Релиз" && i.is_historical && i.end_hours >= todayHours - 0.05,
    );
  }, [items, todayHours]);

  const pendingByOwner = useMemo(
    () => groupBy(pendingRelease, (i) => i.owner_file_name),
    [pendingRelease],
  );

  // Все вехи «Релиз» исполнителя (и прогнозные, и фактические) — катить можно
  // сразу пачкой, это не часы работы, а секунды. Поэтому на детальной сетке не
  // раскладываем их по индивидуальным датам — сворачиваем в одну полоску на
  // старте графика со списком задач по наведению.
  const releaseByOwner = useMemo(
    () => groupBy(items.filter((i) => i.bucket === "Релиз"), (i) => i.owner_file_name),
    [items],
  );

  // Один и тот же ключ задачи годится для поиска и в Story-, и в Epic-, и в
  // Консолид.-полосах — ключи Jira уникальны в рамках проекта.
  const pendingByGroupKey = useMemo(() => {
    const m: Record<string, GanttItem[]> = {};
    for (const it of pendingRelease) {
      for (const k of [it.story_key, it.epic_key, it.parent_key]) {
        if (!k) continue;
        (m[k] ??= []).push(it);
      }
    }
    return m;
  }, [pendingRelease]);

  const [badgePopover, setBadgePopover] = useState<
    { title: string; items: GanttItem[] } | null
  >(null);

  const renderReleaseBadge = (pending: GanttItem[], title: string) => {
    if (!pending.length) return null;
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setBadgePopover({ title, items: pending });
        }}
        title={`${pending.length} ${pending.length === 1 ? "задача" : "задачи"} готовы к релизу / на проде — но не выполнены`}
        className="inline-flex items-center gap-0.5 px-1 rounded-full text-[9px] font-bold bg-amber-100 text-amber-700 border border-amber-400 hover:bg-amber-200 leading-tight shrink-0"
      >
        🚀{pending.length}
      </button>
    );
  };

  // Роль исполнителя — наиболее частая роль среди его задач
  const ownerRole = useMemo(() => {
    const counts: Record<string, Record<string, number>> = {};
    for (const it of items) {
      (counts[it.owner_file_name] ??= {});
      counts[it.owner_file_name][it.role] = (counts[it.owner_file_name][it.role] ?? 0) + 1;
    }
    const m: Record<string, string> = {};
    for (const [name, c] of Object.entries(counts)) {
      const top = Object.entries(c).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
      m[name] = roleLabel(top);
    }
    return m;
  }, [items]);

  // Полосы сводов (Epic выше, Story ниже) + раскладка по Y
  const bands: Band[] = useMemo(() => {
    const arr: Band[] = [];
    let top = HEADER_H;
    if (groupByEpic && epicItems.length) {
      arr.push({ kind: "Epic", title: "Epic", items: epicItems, y0: top });
      top += epicItems.length * (ROW_H + ROW_GAP) + BAND_GAP;
    }
    if (groupByStory && storyItems.length) {
      arr.push({ kind: "Story", title: "User Story", items: storyItems, y0: top });
      top += storyItems.length * (ROW_H + ROW_GAP) + BAND_GAP;
    }
    if (groupByParent && parentItems.length) {
      arr.push({ kind: "Консолид.", title: "Консолидировано", items: parentItems, y0: top });
      top += parentItems.length * (ROW_H + ROW_GAP) + BAND_GAP;
    }
    return arr;
  }, [groupByEpic, groupByStory, groupByParent, epicItems, storyItems, parentItems]);

  const ownersTop = bands.length
    ? bands[bands.length - 1].y0 + bands[bands.length - 1].items.length * (ROW_H + ROW_GAP) + BAND_GAP
    : HEADER_H;

  // Максимальное время (для ширины графика)
  const maxHours = useMemo(
    () => Math.max(hoursPerDay, ...items.map((i) => i.end_hours)),
    [items, hoursPerDay],
  );

  const totalDays = Math.ceil(maxHours / hoursPerDay);
  const chartW    = totalDays * dayPx;
  const svgH      = ownersTop + owners.length * (ROW_H + ROW_GAP);

  // Даты для шапки
  const startD = new Date(startDate + "T00:00:00");
  const dateLabels = useMemo(() => {
    const labels: { date: Date; x: number; isWeekend: boolean }[] = [];
    let workDay = 0;
    const d = new Date(startD);
    for (let i = 0; labels.length <= totalDays + 2; i++) {
      const cur = new Date(d);
      cur.setDate(d.getDate() + i);
      const isWeekend = cur.getDay() === 0 || cur.getDay() === 6;
      if (!isWeekend) {
        labels.push({ date: cur, x: workDay * dayPx, isWeekend: false });
        workDay++;
      } else {
        labels.push({ date: cur, x: workDay * dayPx, isWeekend: true });
      }
      if (workDay > totalDays + 1) break;
    }
    return labels;
  }, [startDate, totalDays, dayPx]);

  const hoursToX = (h: number) => h * hourPx;
  const ownerY   = (idx: number) => ownersTop + idx * (ROW_H + ROW_GAP);
  const bandRowY = (band: Band, idx: number) => band.y0 + idx * (ROW_H + ROW_GAP);

  // Границы спринтов: вертикальные линии на старте каждого спринта + подпись номера.
  const ymd = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const sprintBoundaries = useMemo(() => {
    if (!sprintInfo) return { lines: [] as { x: number; num: number | null }[], startNum: null as number | null };
    const s = new Date(sprintInfo.start_date + "T00:00:00");
    const e = new Date(sprintInfo.end_date + "T00:00:00");
    const lenDays = Math.round((e.getTime() - s.getTime()) / 86_400_000);
    if (!Number.isFinite(lenDays) || lenDays <= 0) return { lines: [], startNum: null };

    const xByDate = new Map<string, number>();
    let maxLabelTime = 0;
    for (const l of dateLabels) {
      const key = ymd(l.date);
      if (!xByDate.has(key)) xByDate.set(key, l.x);
      maxLabelTime = Math.max(maxLabelTime, l.date.getTime());
    }
    const chartStart = new Date(startDate + "T00:00:00");
    const lines: { x: number; num: number | null }[] = [];
    for (let k = 0; k < 200; k++) {
      const d = new Date(s);
      d.setDate(s.getDate() + k * lenDays);
      if (d.getTime() > maxLabelTime) break;
      if (d < chartStart) continue;
      const x = xByDate.get(ymd(d));
      if (x == null) continue;
      lines.push({ x, num: sprintInfo.sprint_num != null ? sprintInfo.sprint_num + k : null });
    }
    // Номер спринта, в который попадает старт графика (для подписи слева)
    const offset = Math.floor((chartStart.getTime() - s.getTime()) / (lenDays * 86_400_000));
    const startNum = sprintInfo.sprint_num != null ? sprintInfo.sprint_num + Math.max(0, offset) : null;
    return { lines, startNum };
  }, [sprintInfo, dateLabels, startDate]);

  // Вычисляем координаты стрелок зависимостей (нижний грид)
  // В своде по User Story стрелки путают — там видна только агрегированная стори,
  // а не реальные задачи-исполнители, между которыми проведена связь.
  const depArrows = useMemo(() => {
    if (groupByStory) return [];
    return dependencies.flatMap((dep) => {
      // Веха «Релиз» больше не рисуется отдельным баром в детальной сетке (см.
      // ниже) — если стрелка целится в неё, рисовать её некуда, пропускаем.
      const fromItems = items.filter((i) => i.key === dep.from_key && !i.is_pseudo && i.bucket !== "Релиз");
      const toItems = items.filter((i) => i.key === dep.to_key && !i.is_pseudo && i.bucket !== "Релиз");
      if (!fromItems.length || !toItems.length) return [];

      const fromItem = fromItems.reduce((a, b) => (a.end_hours > b.end_hours ? a : b));
      const toItem = toItems.reduce((a, b) => (a.start_hours < b.start_hours ? a : b));

      const fromOwnerIdx = owners.indexOf(fromItem.owner_file_name);
      const toOwnerIdx = owners.indexOf(toItem.owner_file_name);
      if (fromOwnerIdx < 0 || toOwnerIdx < 0) return [];

      const x1 = hoursToX(fromItem.end_hours);
      const y1 = ownerY(fromOwnerIdx) + ROW_H / 2;
      const x2 = hoursToX(toItem.start_hours);
      const y2 = ownerY(toOwnerIdx) + ROW_H / 2;

      return [{ x1, y1, x2, y2, key: `${dep.from_key}→${dep.to_key}` }];
    });
  }, [dependencies, items, owners, groupByStory]);

  const handleExportSvg = () => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const totalW = LABEL_W + chartW + 24;
    const ns = "http://www.w3.org/2000/svg";
    const wrapper = document.createElementNS(ns, "svg");
    wrapper.setAttribute("xmlns", ns);
    wrapper.setAttribute("width", String(totalW));
    wrapper.setAttribute("height", String(svgH));
    wrapper.setAttribute("viewBox", `0 0 ${totalW} ${svgH}`);

    const bg = document.createElementNS(ns, "rect");
    bg.setAttribute("width", String(totalW));
    bg.setAttribute("height", String(svgH));
    bg.setAttribute("fill", "white");
    wrapper.appendChild(bg);

    const headerRect = document.createElementNS(ns, "rect");
    headerRect.setAttribute("x", "0");
    headerRect.setAttribute("y", "0");
    headerRect.setAttribute("width", String(LABEL_W));
    headerRect.setAttribute("height", String(HEADER_H));
    headerRect.setAttribute("fill", "#f9fafb");
    wrapper.appendChild(headerRect);

    const headerText = document.createElementNS(ns, "text");
    headerText.setAttribute("x", "12");
    headerText.setAttribute("y", String(HEADER_H - 10));
    headerText.setAttribute("font-size", "11");
    headerText.setAttribute("fill", "#6b7280");
    headerText.setAttribute("font-weight", "600");
    headerText.setAttribute("font-family", "system-ui, sans-serif");
    headerText.textContent = bands.length ? bands[0].title : "Исполнитель";
    wrapper.appendChild(headerText);

    // Подписи сводных полос
    for (const band of bands) {
      const col = bucketColor(band.kind);
      band.items.forEach((s, i) => {
        const y = bandRowY(band, i);
        const rowBg = document.createElementNS(ns, "rect");
        rowBg.setAttribute("x", "0");
        rowBg.setAttribute("y", String(y));
        rowBg.setAttribute("width", String(LABEL_W));
        rowBg.setAttribute("height", String(ROW_H));
        rowBg.setAttribute("fill", i % 2 === 0 ? col.bg : "#ffffff");
        wrapper.appendChild(rowBg);

        const label = document.createElementNS(ns, "text");
        label.setAttribute("x", "12");
        label.setAttribute("y", String(y + ROW_H / 2 - 1));
        label.setAttribute("font-size", "12");
        label.setAttribute("fill", col.text);
        label.setAttribute("font-weight", "700");
        label.setAttribute("font-family", "system-ui, sans-serif");
        label.textContent = s.key;
        wrapper.appendChild(label);

        const sub = document.createElementNS(ns, "text");
        sub.setAttribute("x", "12");
        sub.setAttribute("y", String(y + ROW_H / 2 + 11));
        sub.setAttribute("font-size", "9");
        sub.setAttribute("fill", col.border);
        sub.setAttribute("font-family", "system-ui, sans-serif");
        sub.textContent = s.summary.length > 24 ? s.summary.slice(0, 23) + "…" : s.summary;
        wrapper.appendChild(sub);
      });
    }

    // Строки с именами исполнителей
    owners.forEach((name, i) => {
      const rowBg = document.createElementNS(ns, "rect");
      rowBg.setAttribute("x", "0");
      rowBg.setAttribute("y", String(ownerY(i)));
      rowBg.setAttribute("width", String(LABEL_W));
      rowBg.setAttribute("height", String(ROW_H));
      rowBg.setAttribute("fill", i % 2 === 0 ? "#fafafa" : "#ffffff");
      wrapper.appendChild(rowBg);

      const role = ownerRole[name];
      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", "12");
      label.setAttribute("y", String(ownerY(i) + ROW_H / 2 + (role ? -1 : 4)));
      label.setAttribute("font-size", "12");
      label.setAttribute("fill", "#374151");
      label.setAttribute("font-weight", "500");
      label.setAttribute("font-family", "system-ui, sans-serif");
      label.textContent = name.length > 20 ? name.slice(0, 19) + "…" : name;
      wrapper.appendChild(label);

      if (role) {
        const roleEl = document.createElementNS(ns, "text");
        roleEl.setAttribute("x", "12");
        roleEl.setAttribute("y", String(ownerY(i) + ROW_H / 2 + 11));
        roleEl.setAttribute("font-size", "9");
        roleEl.setAttribute("fill", "#9ca3af");
        roleEl.setAttribute("font-family", "system-ui, sans-serif");
        roleEl.textContent = role;
        wrapper.appendChild(roleEl);
      }
    });

    const sep = document.createElementNS(ns, "line");
    sep.setAttribute("x1", String(LABEL_W));
    sep.setAttribute("y1", "0");
    sep.setAttribute("x2", String(LABEL_W));
    sep.setAttribute("y2", String(svgH));
    sep.setAttribute("stroke", "#e5e7eb");
    sep.setAttribute("stroke-width", "1");
    wrapper.appendChild(sep);

    const g = document.createElementNS(ns, "g");
    g.setAttribute("transform", `translate(${LABEL_W}, 0)`);
    g.innerHTML = svgEl.innerHTML;
    wrapper.appendChild(g);

    const blob = new Blob([new XMLSerializer().serializeToString(wrapper)], {
      type: "image/svg+xml",
    });
    triggerDownload(blob, `gantt-${startDate}.svg`);
  };

  return (
    <div className="relative overflow-x-auto border rounded-lg bg-white shadow-sm">
      {/* Панель управления */}
      <div className="flex items-center gap-3 px-3 py-2 border-b bg-gray-50 text-xs text-gray-600">
        <span className="font-medium">Масштаб:</span>
        <button
          onClick={() => setHourPx((v) => Math.max(HOUR_PX_MIN, v - 2))}
          className="w-6 h-6 flex items-center justify-center border rounded hover:bg-gray-200 font-bold"
          title="Уменьшить"
        >−</button>
        <span className="w-14 text-center">{hourPx} px/ч</span>
        <button
          onClick={() => setHourPx((v) => Math.min(HOUR_PX_MAX, v + 2))}
          className="w-6 h-6 flex items-center justify-center border rounded hover:bg-gray-200 font-bold"
          title="Увеличить"
        >+</button>
        <button
          onClick={() => setHourPx(HOUR_PX_DEFAULT)}
          className="text-gray-400 hover:text-gray-600 underline ml-1"
        >сброс</button>
        <button
          onClick={handleExportSvg}
          className="ml-auto border border-gray-300 rounded px-2 py-0.5 hover:bg-gray-100"
          title="Скачать диаграмму как SVG"
        >↓ SVG</button>
      </div>
      <div style={{ display: "flex", minWidth: LABEL_W + chartW + 24 }}>
        {/* Левая колонка: имена / своды */}
        <div
          style={{ width: LABEL_W, minWidth: LABEL_W, flexShrink: 0 }}
          className="sticky left-0 bg-white z-10 border-r"
        >
          {/* Шапка */}
          <div
            style={{ height: HEADER_H }}
            className="border-b flex items-end pb-1 px-3"
          >
            <span className="text-xs font-semibold text-gray-500">
              {bands.length ? bands[0].title : "Исполнитель"}
            </span>
          </div>
          {/* Сводные полосы */}
          {bands.map((band, bi) => {
            const col = bucketColor(band.kind);
            const nextTitle = bi + 1 < bands.length ? bands[bi + 1].title : "Исполнители";
            return (
              <div key={`band-${band.kind}`}>
                {band.items.map((s) => (
                  <div
                    key={`${band.kind}-${s.key}`}
                    style={{ height: ROW_H + ROW_GAP }}
                    className="flex flex-col justify-center px-3 border-b"
                    title={`${s.key} · ${s.summary}`}
                  >
                    <span className="flex items-center gap-1">
                      <span
                        className="text-sm font-semibold truncate leading-tight"
                        style={{ color: col.text }}
                      >{s.key}</span>
                      {renderReleaseBadge(pendingByGroupKey[s.key] ?? [], `${s.key} · ${s.summary}`)}
                    </span>
                    <span
                      className="text-[10px] truncate leading-tight"
                      style={{ color: col.border }}
                    >{s.summary}</span>
                  </div>
                ))}
                <div
                  style={{ height: BAND_GAP }}
                  className="flex items-center px-3 border-b bg-gray-100"
                >
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">{nextTitle}</span>
                </div>
              </div>
            );
          })}
          {/* Строки исполнителей */}
          {owners.map((name) => (
            <div
              key={name}
              style={{ height: ROW_H + ROW_GAP }}
              className="flex flex-col justify-center px-3 border-b"
              title={ownerRole[name] ? `${name} · ${ownerRole[name]}` : name}
            >
              <span className="flex items-center gap-1">
                <span className="text-sm font-medium text-gray-700 truncate leading-tight">{name}</span>
                {renderReleaseBadge(pendingByOwner[name] ?? [], name)}
              </span>
              {ownerRole[name] && (
                <span className="text-[10px] text-gray-400 truncate leading-tight">
                  {ownerRole[name]}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* SVG-область */}
        <div className="relative flex-1 overflow-x-auto">
          <svg
            ref={svgRef}
            width={chartW + 24}
            height={svgH}
            style={{ display: "block" }}
            onClick={() => setSelectedKey(null)}
          >
            {/* Вертикальные линии дней */}
            {dateLabels
              .filter((l) => !l.isWeekend)
              .map((l, i) => (
                <g key={i}>
                  <line
                    x1={l.x}
                    y1={HEADER_H}
                    x2={l.x}
                    y2={svgH}
                    stroke="#e5e7eb"
                    strokeWidth={1}
                  />
                </g>
              ))}

            {/* Фоны строк сводных полос */}
            {bands.map((band) => {
              const col = bucketColor(band.kind);
              return band.items.map((_, rowI) => (
                <rect
                  key={`bandbg-${band.kind}-${rowI}`}
                  x={0}
                  y={bandRowY(band, rowI)}
                  width={chartW + 24}
                  height={ROW_H}
                  fill={rowI % 2 === 0 ? col.bg : "#ffffff"}
                  opacity={0.5}
                />
              ));
            })}
            {/* Разделитель перед нижним гридом */}
            {bands.length > 0 && (
              <line
                x1={0} y1={ownersTop - BAND_GAP / 2}
                x2={chartW + 24} y2={ownersTop - BAND_GAP / 2}
                stroke="#cbd5e1" strokeWidth={1}
              />
            )}

            {/* Горизонтальные полосы строк исполнителей */}
            {owners.map((_, rowI) => (
              <rect
                key={rowI}
                x={0}
                y={ownerY(rowI)}
                width={chartW + 24}
                height={ROW_H}
                fill={rowI % 2 === 0 ? "#fafafa" : "#ffffff"}
              />
            ))}

            {/* Шапка с датами */}
            {dateLabels
              .filter((l) => !l.isWeekend)
              .map((l, i) => (
                <g key={i}>
                  <text
                    x={l.x + 4}
                    y={HEADER_H - 26}
                    fontSize={10}
                    fill="#6b7280"
                    fontWeight="600"
                  >
                    {fmtDay(l.date)}
                  </text>
                  <text
                    x={l.x + 4}
                    y={HEADER_H - 12}
                    fontSize={11}
                    fill="#374151"
                    fontWeight="700"
                  >
                    {fmtDate(l.date)}
                  </text>
                </g>
              ))}

            {/* Границы спринтов */}
            {sprintBoundaries.lines.map((ln, i) => (
              <g key={`sprint-${i}`}>
                <line
                  x1={ln.x} y1={0} x2={ln.x} y2={svgH}
                  stroke="#7c3aed" strokeWidth={1.5} strokeDasharray="2 3" opacity={0.55}
                />
                {ln.num != null && (
                  <text x={ln.x + 3} y={HEADER_H - 2} fontSize={10} fill="#7c3aed" fontWeight="700">
                    {`Спринт ${ln.num}`}
                  </text>
                )}
              </g>
            ))}
            {sprintBoundaries.startNum != null && (
              <text x={6} y={HEADER_H - 2} fontSize={10} fill="#a78bfa" fontWeight="700">
                {`Спринт ${sprintBoundaries.startNum}`}
              </text>
            )}

            {/* Линия «сейчас» */}
            {todayHours != null && todayHours > 0 ? (
              <g>
                <line
                  x1={hoursToX(todayHours)} y1={0}
                  x2={hoursToX(todayHours)} y2={svgH}
                  stroke="#ef4444" strokeWidth={2} strokeDasharray="5 3" opacity={0.7}
                />
                <text
                  x={hoursToX(todayHours) + 4} y={12}
                  fontSize={10} fill="#ef4444" fontWeight="700"
                >
                  сегодня
                </text>
              </g>
            ) : (
              <line x1={0} y1={0} x2={0} y2={svgH} stroke="#3b82f6" strokeWidth={2} opacity={0.4} />
            )}

            {/* Стрелки FS-зависимостей */}
            <defs>
              <marker id="dep-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill="#ef4444" />
              </marker>
            </defs>
            {depArrows.map((a) => {
              const dx = Math.abs(a.x2 - a.x1) * 0.4 + 16;
              return (
                <path
                  key={a.key}
                  d={`M ${a.x1} ${a.y1} C ${a.x1 + dx} ${a.y1}, ${a.x2 - dx} ${a.y2}, ${a.x2} ${a.y2}`}
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  opacity={0.75}
                  markerEnd="url(#dep-arrow)"
                />
              );
            })}

            {/* Бары сводных полос (Epic / User Story) */}
            {bands.map((band) => {
              const col = bucketColor(band.kind);
              return band.items.map((item, idx) => {
                const x = hoursToX(item.start_hours);
                const w = Math.max(2, hoursToX(item.end_hours - item.start_hours));
                const y = bandRowY(band, idx) + 4;
                const h = ROW_H - 8;
                const isSelected = selectedKey === item.key;
                return (
                  <g
                    key={`band-bar-${band.kind}-${item.key}`}
                    onMouseEnter={(e) => {
                      const svgEl = e.currentTarget.closest("svg")!;
                      const rect = svgEl.getBoundingClientRect();
                      setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, item });
                    }}
                    onMouseLeave={() => setTooltip(null)}
                    style={{ cursor: "pointer" }}
                    onClick={(e) => { e.stopPropagation(); handleBarClick(item); }}
                  >
                    <rect
                      x={x} y={y} width={w} height={h} rx={4}
                      fill={col.bg}
                      stroke={isSelected ? col.text : col.border}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                    />
                    {w > 40 && (
                      <text
                        x={x + 6} y={y + h / 2 + 4}
                        fontSize={10} fill={col.text} fontWeight="700"
                      >
                        {truncateForBar(`${item.key} · ${item.summary} · ${item.hours.toFixed(0)}ч`, w, 12)}
                      </text>
                    )}
                  </g>
                );
              });
            })}

            {/* Задачи (детальная сетка) — веха «Релиз» сюда не попадает, см. ниже */}
            {owners.map((name, ownerIdx) => {
              const ownerItems = (byOwner[name] ?? []).filter((i) => i.bucket !== "Релиз");
              return ownerItems.map((item) => {
                const x = hoursToX(item.start_hours);
                const w = Math.max(2, hoursToX(item.end_hours - item.start_hours));
                const y = ownerY(ownerIdx) + 4;
                const h = ROW_H - 8;
                const col = bucketColor(devBucketLabel(item));

                const isSelected   = selectedKey !== null && (
                  selectedKey === item.key ||
                  selectedKey === item.parent_key ||
                  selectedKey === item.story_key ||
                  selectedKey === item.epic_key
                );
                const isDimmed     = selectedKey !== null && !isSelected && !item.is_pseudo;
                const isRootTask   = !item.is_pseudo && rootTasks[item.owner_id] === item.key;

                return (
                  <g
                    key={`${item.key}-${item.bucket}-${item.start_hours}`}
                    onMouseEnter={(e) => {
                      const svgEl = e.currentTarget.closest("svg")!;
                      const rect = svgEl.getBoundingClientRect();
                      setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, item });
                    }}
                    onMouseLeave={() => setTooltip(null)}
                    style={{ cursor: item.is_pseudo ? "default" : "pointer" }}
                    onClick={(e) => { e.stopPropagation(); handleBarClick(item); }}
                    opacity={isDimmed ? 0.25 : 1}
                  >
                    {isSelected && (
                      <rect
                        x={x - 3} y={y - 3}
                        width={w + 6} height={h + 6}
                        rx={5}
                        fill="none"
                        stroke="#3b82f6"
                        strokeWidth={2.5}
                        opacity={0.8}
                      />
                    )}
                    <rect
                      x={x} y={y}
                      width={w} height={h}
                      rx={3}
                      fill={col.bg}
                      fillOpacity={item.is_historical ? 0.5 : 1}
                      stroke={isSelected ? "#2563eb" : col.border}
                      strokeWidth={isSelected ? 2 : 1.5}
                      strokeDasharray={item.is_historical && !isSelected ? "3 2" : undefined}
                    />
                    {w > 40 && (
                      <text
                        x={x + 5}
                        y={y + h / 2 + 4}
                        fontSize={10}
                        fill={col.text}
                        fontWeight={isSelected ? "700" : "600"}
                      >
                        {truncateForBar(
                          item.key.startsWith("__")
                            ? item.bucket
                            : w > 80 ? `${item.key} · ${shortBucketLabel(devBucketLabel(item))}` : item.key,
                          w, 10,
                        )}
                      </text>
                    )}
                    {isRootTask && (
                      <text x={x - 1} y={y + 9} fontSize={11}>
                        <title>Стартовая задача</title>
                        📌
                      </text>
                    )}
                  </g>
                );
              });
            })}

            {/* Свёрнутая веха «Релиз»: маленький флажок на исполнителя на старте
                графика (в зазоре над строкой, не на самом баре — чтобы не
                перекрывать задачи), список задач — по клику (карточка, как у
                бейджа 🚀). Не привязана к расчётным датам — релиз не занимает
                времени по часам, выкатить можно пачкой в любой момент. */}
            {owners.map((name, ownerIdx) => {
              const releaseItems = releaseByOwner[name];
              if (!releaseItems || !releaseItems.length) return null;
              const x = hoursToX(todayHours ?? 0);
              const yTop = ownerY(ownerIdx) + 4;
              const col = bucketColor("Релиз");
              return (
                <g
                  key={`release-marker-${name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setBadgePopover({ title: `Релиз · ${name}`, items: releaseItems });
                  }}
                  style={{ cursor: "pointer" }}
                >
                  <rect x={x - 7} y={yTop - 14} width={14} height={14} fill="transparent" />
                  <path
                    d={`M${x - 5},${yTop - 9} L${x + 5},${yTop - 9} L${x},${yTop} Z`}
                    fill={col.border}
                    stroke={col.text}
                    strokeWidth={0.5}
                  />
                </g>
              );
            })}
          </svg>

          {/* Тултип */}
          {tooltip && (
            <div
              className="absolute pointer-events-none z-20 bg-gray-900 text-white text-xs rounded-lg p-2.5 shadow-xl max-w-xs"
              style={{
                left: tooltip.x + 12,
                top: tooltip.y - 10,
                transform: tooltip.x > chartW * 0.65 ? "translateX(-110%)" : undefined,
              }}
            >
              <div className="font-bold mb-0.5">
                {tooltip.item.key.startsWith("__") ? tooltip.item.bucket : tooltip.item.key}
              </div>
              {!tooltip.item.key.startsWith("__") && (
                <div className="text-gray-300 mb-1 leading-tight">{tooltip.item.summary}</div>
              )}
              <div className="flex gap-2 flex-wrap">
                <span
                  className="px-1.5 py-0.5 rounded text-xs font-medium"
                  style={{
                    background: bucketColor(devBucketLabel(tooltip.item)).bg,
                    color: bucketColor(devBucketLabel(tooltip.item)).text,
                  }}
                >
                  {devBucketLabel(tooltip.item)}
                </span>
                <span className="text-gray-300">{tooltip.item.hours.toFixed(1)} ч</span>
                {tooltip.item.is_historical && (
                  <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-gray-700 text-gray-200">
                    факт{tooltip.item.phase_status ? ` · ${tooltip.item.phase_status}` : ""}
                  </span>
                )}
              </div>
              <div className="text-gray-400 mt-1 text-xs">
                {new Date(tooltip.item.start).toLocaleString("ru-RU", {
                  day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                })}
                {" → "}
                {new Date(tooltip.item.end).toLocaleString("ru-RU", {
                  day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                })}
              </div>
              {!tooltip.item.is_pseudo && (
                <div className="text-gray-500 mt-1.5 text-xs border-t border-gray-700 pt-1.5">
                  клик — все этапы · двойной — Jira
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Попап бейджа «готово к релизу / на проде, не выполнено» — список по статусам.
          Центрированное окно, а не дропдаун от точки клика — иначе при клике в
          нижней части графика список рисовался за пределами видимой области. */}
      {badgePopover && (
        <div
          className="fixed inset-0 z-30 bg-black/30 flex items-center justify-center p-4"
          onClick={() => setBadgePopover(null)}
        >
          <div
            className="bg-white border border-gray-200 shadow-2xl rounded-lg p-4 text-xs w-full max-w-md max-h-[70vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="font-semibold text-gray-800 text-sm truncate">{badgePopover.title}</div>
              <button
                type="button"
                onClick={() => setBadgePopover(null)}
                className="text-gray-400 hover:text-gray-600 leading-none px-1 text-lg"
              >×</button>
            </div>
            {Object.entries(
              groupBy(badgePopover.items, (i) => i.phase_status || (i.is_historical ? "факт" : "прогноз")),
            ).map(([status, list]) => (
              <div key={status} className="mb-3 last:mb-0">
                <div className="text-amber-700 font-semibold text-[11px] mb-1">
                  {status} · {list.length}
                </div>
                <ul className="space-y-1">
                  {list.map((it) => (
                    <li key={it.key} className="flex items-center gap-2">
                      <a
                        href={it.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 hover:underline font-medium whitespace-nowrap"
                      >{it.key}</a>
                      <span className="text-gray-500 truncate">{it.summary}</span>
                      {!it.is_historical && (
                        <span className="text-gray-400 whitespace-nowrap">
                          {it.end.slice(8, 10)}.{it.end.slice(5, 7)}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Легенда */}
      <div className="flex flex-wrap gap-2 px-4 py-2 border-t bg-gray-50 text-xs">
        {Object.entries(BUCKET_COLORS)
          .filter(([bucket]) => {
            if (bucket === "Story") return groupByStory;
            if (bucket === "Epic") return groupByEpic;
            if (bucket === "Консолид.") return groupByParent;
            if (bucket === "Разработка") return false; // показываем только фронт/бек-разбивку
            return true;
          })
          .map(([bucket, col]) => (
            <span
              key={bucket}
              className="flex items-center gap-1 px-2 py-0.5 rounded border"
              style={{ background: col.bg, color: col.text, borderColor: col.border }}
            >
              {bucket}
            </span>
          ))}
      </div>
    </div>
  );
}
