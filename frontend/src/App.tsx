import { useEffect, useState } from "react";
import { checkJira } from "./api/client";
import { HistoryPage } from "./pages/HistoryPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SprintPage } from "./pages/SprintPage";

type JiraStatus =
  | { kind: "checking" }
  | { kind: "ok"; name: string }
  | { kind: "error"; message: string };

type Page = "sprint" | "history" | "settings";

function App() {
  const [jiraStatus, setJiraStatus] = useState<JiraStatus>({ kind: "checking" });
  const [page, setPage] = useState<Page>("sprint");

  useEffect(() => {
    checkJira()
      .then((r) => setJiraStatus({ kind: "ok", name: r.display_name }))
      .catch((e) => setJiraStatus({ kind: "error", message: extractError(e) }));
  }, []);

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
              <NavTab active={page === "settings"} onClick={() => setPage("settings")}>
                Настройки
              </NavTab>
            </nav>
          </div>
          <JiraStatusLine status={jiraStatus} />
        </div>
      </header>

      {page === "sprint" && <SprintPage jiraReady={jiraStatus.kind === "ok"} />}
      {page === "history" && <HistoryPage />}
      {page === "settings" && <SettingsPage />}
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
        active
          ? "bg-blue-100 text-blue-800"
          : "text-gray-600 hover:bg-gray-100"
      }`}
    >
      {children}
    </button>
  );
}

function JiraStatusLine({ status }: { status: JiraStatus }) {
  if (status.kind === "checking") {
    return <p className="text-xs text-gray-500">Проверка подключения к Jira…</p>;
  }
  if (status.kind === "error") {
    return <p className="text-xs text-red-600">Jira недоступна: {status.message}</p>;
  }
  return <p className="text-xs text-green-600">Jira: {status.name}</p>;
}

function extractError(e: unknown): string {
  if (e && typeof e === "object" && "response" in e) {
    const r = (e as { response?: { data?: { detail?: string } } }).response;
    if (r?.data?.detail) return r.data.detail;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

export default App;
