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
      .catch(() => {
        setToken(null);
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
      <header className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold text-gray-800">Sprint Builder</h1>
            <nav className="flex gap-1">
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
          <div className="flex items-center gap-4">
            <ConfigSwitcher onChange={() => setConfigEpoch((e) => e + 1)} />
            <JiraStatusLine status={jiraStatus} />
            <UserMenu user={user} onLogout={handleLogout} />
          </div>
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
      className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
        active ? "bg-blue-100 text-blue-800" : "text-gray-600 hover:bg-gray-100"
      }`}
    >
      {children}
    </button>
  );
}

function JiraStatusLine({ status }: { status: JiraStatus }) {
  if (status.kind === "checking") {
    return <p className="text-xs text-gray-500">Проверка Jira…</p>;
  }
  if (status.kind === "error") {
    return <p className="text-xs text-red-600">Jira: {status.message}</p>;
  }
  return <p className="text-xs text-green-600">Jira: {status.name}</p>;
}

function UserMenu({ user, onLogout }: { user: UserOut; onLogout: () => void }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <div className="text-right">
        <div className="font-semibold text-gray-700">
          {user.display_name || user.email}
        </div>
        <div className="text-xs text-gray-500">{user.role}</div>
      </div>
      <button
        onClick={onLogout}
        className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded"
      >
        Выйти
      </button>
    </div>
  );
}

export default App;
