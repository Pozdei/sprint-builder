import { useEffect, useState } from "react";
import { checkJira, getMe, getToken, setToken } from "./api/client";
import { extractError } from "./lib/api-error";
import { ConfigSwitcher } from "./components/ConfigSwitcher";
import { AdminPage } from "./pages/AdminPage";
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

type LeadPage = "sprint" | "history" | "forecast" | "settings";
type AdminPageKind = "admin";
type Page = LeadPage | AdminPageKind;

function App() {
  const [user, setUser] = useState<UserOut | null | undefined>(null);
  const [page, setPage] = useState<Page>("sprint");
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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold text-gray-800">Sprint Builder</h1>
            <nav className="flex gap-1">
              <NavTab active={page === "sprint"} onClick={() => setPage("sprint")}>
                Спринт
              </NavTab>
              <NavTab active={page === "history"} onClick={() => setPage("history")}>
                История
              </NavTab>
              <NavTab active={page === "forecast"} onClick={() => setPage("forecast")}>
                Прогноз реализации
              </NavTab>
              <NavTab active={page === "settings"} onClick={() => setPage("settings")}>
                Настройки
              </NavTab>
              {isAdmin && (
                <NavTab active={page === "admin"} onClick={() => setPage("admin")}>
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

      {page === "sprint" && (
        <SprintPage key={`sprint-${configEpoch}`} jiraReady={jiraStatus.kind === "ok"} />
      )}
      {page === "history" && <HistoryPage key={`history-${configEpoch}`} />}
      {page === "forecast" && <EpicForecastPage key={`forecast-${configEpoch}`} isAdmin={isAdmin} />}
      {page === "settings" && <SettingsPage key={`settings-${configEpoch}`} />}
      {isAdmin && page === "admin" && <AdminPage />}
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
