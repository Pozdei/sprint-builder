import { useCallback, useEffect, useState } from "react";
import { checkJira, getMe, getToken, setToken } from "./api/client";
import { extractError } from "./lib/api-error";
import { ConfigSwitcher } from "./components/ConfigSwitcher";
import { AdminPage } from "./pages/AdminPage";
import { DocsPage } from "./pages/DocsPage";
import { EpicForecastPage } from "./pages/EpicForecastPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SprintPage } from "./pages/SprintPage";
import type { UserOut } from "./types/api";

type JiraStatus =
  | { kind: "checking" }
  | { kind: "ok"; name: string }
  | { kind: "error"; message: string };

type LeadPage = "sprint" | "history" | "forecast" | "settings" | "docs";
type AdminPageKind = "admin";
type Page = LeadPage | AdminPageKind;

const PAGES: readonly Page[] = ["sprint", "history", "forecast", "settings", "docs", "admin"];

/** Распарсить текущий hash в страницу. Неизвестное → "sprint". */
function hashToPage(hash: string): Page {
  const seg = hash.replace(/^#\/?/, "").split("/")[0];
  return (PAGES as readonly string[]).includes(seg) ? (seg as Page) : "sprint";
}

/**
 * Страница, синхронизированная с `location.hash` (`#/forecast` и т.п.).
 * Даёт работающие F5, кнопки назад/вперёд и ссылки на конкретный раздел.
 */
function useHashPage(): [Page, (p: Page) => void] {
  const [page, setPageState] = useState<Page>(() => hashToPage(window.location.hash));

  useEffect(() => {
    const onHash = () => setPageState(hashToPage(window.location.hash));
    window.addEventListener("hashchange", onHash);
    // Если зашли без hash — проставим, чтобы URL отражал раздел.
    if (!window.location.hash) window.location.hash = "#/sprint";
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const setPage = useCallback((p: Page) => {
    const target = `#/${p}`;
    if (window.location.hash !== target) {
      window.location.hash = target;  // вызовет hashchange → обновит состояние
    } else {
      setPageState(p);
    }
  }, []);

  return [page, setPage];
}

function App() {
  const [user, setUser] = useState<UserOut | null | undefined>(null);
  const [page, setPage] = useHashPage();
  const [jiraStatus, setJiraStatus] = useState<JiraStatus>({ kind: "checking" });

  // Эпоха активного конфига. Меняется при переключении/создании/удалении —
  // используется в key=, чтобы React пересоздал страницы и они перечитали данные.
  const [configEpoch, setConfigEpoch] = useState(0);

  useEffect(() => {
    if (!getToken()) {
      setUser(undefined);
      return;
    }
    getMe()
      .then((u) => setUser(u))
      .catch((e) => {
        if (e?.response?.status === 401) setToken(null);
        setUser(undefined);
      });
  }, []);

  useEffect(() => {
    if (!user) return;
    checkJira()
      .then((r) => setJiraStatus({ kind: "ok", name: r.display_name }))
      .catch((e) => setJiraStatus({ kind: "error", message: extractError(e) }));
  }, [user]);

  const handleLogout = () => {
    setToken(null);
    setUser(undefined);
    setPage("sprint");
  };

  if (user === null) {
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Загрузка…</div>;
  }
  if (user === undefined) {
    return <LoginPage onLogin={(u) => setUser(u)} />;
  }

  const isAdmin = user.role === "admin";
  // Не-админ по прямой ссылке на #/admin — мягко возвращаем на «Спринт».
  const activePage: Page = page === "admin" && !isAdmin ? "sprint" : page;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        {/* Верхняя строка: бренд + аккаунт/конфиг — служебная информация, не навигация */}
        <div className="max-w-7xl mx-auto px-6 h-11 flex items-center justify-between border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-md bg-indigo-600 flex-none" />
            <span className="text-[15px] font-semibold text-gray-900 tracking-tight">Sprint Builder</span>
          </div>
          <div className="flex items-center gap-3">
            <JiraStatusLine status={jiraStatus} />
            <span className="w-px h-4 bg-gray-200" />
            <ConfigSwitcher onChange={() => setConfigEpoch((e) => e + 1)} />
            <span className="w-px h-4 bg-gray-200" />
            <UserMenu user={user} onLogout={handleLogout} />
          </div>
        </div>

        {/* Нижняя строка: навигация по разделам */}
        <div className="max-w-7xl mx-auto px-6">
          <nav className="flex gap-5">
            <NavTab active={activePage === "sprint"} onClick={() => setPage("sprint")}>
              Спринт
            </NavTab>
            <NavTab active={activePage === "history"} onClick={() => setPage("history")}>
              История
            </NavTab>
            <NavTab active={activePage === "forecast"} onClick={() => setPage("forecast")}>
              Прогноз реализации
            </NavTab>
            <NavTab active={activePage === "settings"} onClick={() => setPage("settings")}>
              Настройки
            </NavTab>
            <NavTab active={activePage === "docs"} onClick={() => setPage("docs")}>
              Справка
            </NavTab>
            {isAdmin && (
              <NavTab active={activePage === "admin"} onClick={() => setPage("admin")}>
                Админка
              </NavTab>
            )}
          </nav>
        </div>
      </header>

      {activePage === "sprint" && (
        <SprintPage key={`sprint-${configEpoch}`} jiraReady={jiraStatus.kind === "ok"} />
      )}
      {activePage === "history" && <HistoryPage key={`history-${configEpoch}`} />}
      {activePage === "forecast" && <EpicForecastPage key={`forecast-${configEpoch}`} isAdmin={isAdmin} />}
      {activePage === "settings" && <SettingsPage key={`settings-${configEpoch}`} />}
      {activePage === "docs" && <DocsPage />}
      {isAdmin && activePage === "admin" && <AdminPage />}

      <AuthorBadge />
    </div>
  );
}

/**
 * Авторский бейдж в углу. В покое — почти невидимый «PS» (не отвлекает от
 * работы). На hover «PS» гаснет, а бейдж раскрывается в градиент с подписью —
 * без нативного title, он не успевает появиться и не стилизуется.
 */
function AuthorBadge() {
  return (
    <div className="fixed bottom-5 right-5 z-50 group">
      <div
        className="relative h-8 w-8 group-hover:w-[208px] rounded-xl overflow-hidden cursor-default select-none
                   bg-gray-100/70 group-hover:bg-gradient-to-br group-hover:from-indigo-600 group-hover:via-violet-600 group-hover:to-fuchsia-600
                   transition-all duration-300 ease-out
                   group-hover:shadow-lg group-hover:shadow-fuchsia-900/30"
      >
        {/* «PS» — видно в покое, гаснет на hover */}
        <span
          className="absolute inset-0 flex items-center justify-center text-[10px] font-bold tracking-wide
                     text-gray-400 opacity-100 group-hover:opacity-0
                     transition-opacity duration-150"
        >
          PS
        </span>
        {/* Подпись — появляется вместо «PS» на hover */}
        <span
          className="absolute inset-0 flex items-center justify-center whitespace-nowrap px-3
                     text-white text-xs font-medium opacity-0 group-hover:opacity-100
                     transition-opacity duration-200 delay-100"
        >
          by Sergey Pozdeev <span className="text-white/60 ml-1.5">© 2026</span>
        </span>
      </div>
    </div>
  );
}

function NavTab({
  active, onClick, children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`relative py-2.5 text-sm font-medium transition border-b-2 ${
        active
          ? "text-indigo-700 border-indigo-600"
          : "text-gray-500 border-transparent hover:text-gray-800 hover:border-gray-200"
      }`}
    >
      {children}
    </button>
  );
}

function JiraStatusLine({ status }: { status: JiraStatus }) {
  const dot = status.kind === "checking"
    ? "bg-gray-300"
    : status.kind === "error" ? "bg-red-500" : "bg-emerald-500";
  const label = status.kind === "checking"
    ? "Проверка…"
    : status.kind === "error" ? status.message : status.name;
  return (
    <span
      className="flex items-center gap-1.5 text-xs text-gray-500 max-w-[160px]"
      title={status.kind === "error" ? `Jira: ${status.message}` : undefined}
    >
      <span className={`w-1.5 h-1.5 rounded-full flex-none ${dot}`} />
      <span className="truncate">{label}</span>
    </span>
  );
}

function UserMenu({ user, onLogout }: { user: UserOut; onLogout: () => void }) {
  const name = user.display_name || user.email;
  const initial = name.trim().charAt(0).toUpperCase();
  return (
    <div className="flex items-center gap-2 group">
      <div className="w-6 h-6 rounded-full bg-gray-200 text-gray-600 text-xs font-semibold flex items-center justify-center flex-none">
        {initial}
      </div>
      <span className="text-xs text-gray-600 max-w-[120px] truncate" title={name}>{name}</span>
      <button
        onClick={onLogout}
        title="Выйти"
        className="text-gray-400 hover:text-red-600 text-xs leading-none transition"
      >
        ⏻
      </button>
    </div>
  );
}

export default App;
