import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { getDefaultConfig, updateConfig } from "../api/client";
import { sendTodayDigest, sendTestMessage } from "../api/telegram-client";
import { useToast } from "../components/Toast";
import { extractError } from "../lib/api-error";
import { DictEditor } from "../components/settings/DictEditor";
import { DirectionsEditor } from "../components/settings/DirectionsEditor";
import { PseudoTasksEditor } from "../components/settings/PseudoTasksEditor";
import { RolesEditor } from "../components/settings/RolesEditor";
import { RoleStatusBucketsEditor } from "../components/settings/RoleStatusBucketsEditor";
import { RoleStatusHoursEditor } from "../components/settings/RoleStatusHoursEditor";
import { StringListEditor } from "../components/settings/StringListEditor";
import { TeamEditor } from "../components/settings/TeamEditor";
import type { ConfigOut } from "../types/api";

type CategoryId = "general" | "team" | "pipeline" | "source";

const CATEGORY_ICONS: Record<CategoryId, string> = {
  general: "⚙️",
  team: "👥",
  pipeline: "🔄",
  source: "🗂️",
};

const CATEGORY_IDS: CategoryId[] = ["general", "team", "pipeline", "source"];

export function SettingsPage() {
  const { t } = useTranslation(["settings", "common"]);
  const toast = useToast();
  const [config, setConfig] = useState<ConfigOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [category, setCategory] = useState<CategoryId>("general");
  // Токен не приходит с сервера (write-only) — отдельное поле, шлём только если ввели новый.
  const [jiraApiToken, setJiraApiToken] = useState("");
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [tgSending, setTgSending] = useState(false);

  useEffect(() => {
    getDefaultConfig()
      .then((c) => setConfig(c))
      .catch((e) => setLoadError(extractError(e)))
      .finally(() => setLoading(false));
  }, []);

  // Список уникальных бакетов — для подсказок в редакторе маппинга
  const knownBuckets = useMemo(() => {
    if (!config) return [];
    const set = new Set<string>();
    config.role_status_buckets.forEach((r) => set.add(r.bucket));
    // Добавим зарезервированные для псевдо-задач
    Object.values(t("page.reservedBuckets", { returnObjects: true }) as Record<string, string>)
      .forEach((b) => set.add(b));
    return Array.from(set).sort();
  }, [config, t]);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      // Передаём team как {accountId: {jira_name, file_name, role, salary}}
      const teamForApi: Record<string, { jira_name: string; file_name: string; role: string; salary: number }> = {};
      Object.entries(config.team).forEach(([accId, m]) => {
        teamForApi[accId] = {
          jira_name: m.jira_name,
          file_name: m.file_name,
          role: m.role,
          salary: m.salary ?? 0,
        };
      });

      const {
        id, is_default: _isDef, jira_api_token_set: _tokenSet,
        telegram_bot_token_set: _tgSet, telegram_bot_configured: _tgBot,
        team: _t, ...rest
      } = config;
      const body: typeof rest & {
        team: typeof teamForApi; jira_api_token?: string; telegram_bot_token?: string;
      } = {
        ...rest, team: teamForApi,
      };
      if (jiraApiToken.trim()) body.jira_api_token = jiraApiToken.trim();
      if (telegramBotToken.trim()) body.telegram_bot_token = telegramBotToken.trim();
      const updated = await updateConfig(id, body);
      setConfig(updated);
      setJiraApiToken("");
      setTelegramBotToken("");
      toast.success(t("page.saveSuccess"));
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  // Дайджест читает chat_id из БД — нужно сначала сохранить изменения.
  const runTelegram = async (action: () => Promise<{ count: number }>, kind: "send" | "test") => {
    setTgSending(true);
    try {
      const res = await action();
      if (kind === "test") toast.success(t("page.telegram.testSent"));
      else toast.success(t("page.telegram.sent", { count: res.count }));
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setTgSending(false);
    }
  };

  if (loading) {
    return <div className="text-center text-gray-500 mt-20">{t("page.loadingConfig")}</div>;
  }
  if (loadError && !config) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="bg-red-50 border border-red-300 text-red-800 rounded-lg p-3">
          {t("page.loadFailed", { error: loadError })}
        </div>
      </div>
    );
  }
  if (!config) return null;

  const update = <K extends keyof ConfigOut>(key: K, val: ConfigOut[K]) =>
    setConfig({ ...config, [key]: val });

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      {/* Заголовок + сохранение — всегда на виду, без скролла до низа */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{t("page.title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t("page.configLabel", { name: config.name })}</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
        >
          {saving ? t("page.saving") : t("page.save")}
        </button>
      </div>

      <div className="flex gap-6">
        {/* Боковая навигация по категориям */}
        <nav className="w-52 flex-none space-y-1">
          {CATEGORY_IDS.map((catId) => (
            <button
              key={catId}
              onClick={() => setCategory(catId)}
              className={`w-full text-left px-3 py-2.5 rounded-lg transition border-l-2 ${
                category === catId
                  ? "bg-indigo-50 border-indigo-600"
                  : "border-transparent hover:bg-gray-50"
              }`}
            >
              <div className={`text-sm font-medium flex items-center gap-2 ${
                category === catId ? "text-indigo-700" : "text-gray-700"
              }`}>
                <span>{CATEGORY_ICONS[catId]}</span> {t(`page.categories.${catId}.label`)}
              </div>
              <div className="text-xs text-gray-400 mt-0.5 leading-snug">
                {t(`page.categories.${catId}.hint`)}
              </div>
            </button>
          ))}
        </nav>

        {/* Контент активной категории */}
        <div className="flex-1 min-w-0 space-y-5">
          {category === "general" && (
            <>
              <Section title={t("page.sections.baseParams")} accent="slate">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Field label={t("page.fields.configName")}>
                    <input
                      type="text"
                      value={config.name}
                      onChange={(e) => update("name", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.projectKey")}>
                    <input
                      type="text"
                      value={config.project_key}
                      onChange={(e) => update("project_key", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.hoursPerPerson")}>
                    <input
                      type="number"
                      value={config.hours_per_person}
                      onChange={(e) => update("hours_per_person", Number(e.target.value))}
                      onWheel={(e) => e.currentTarget.blur()}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.defaultTaskHours")}>
                    <input
                      type="number"
                      value={config.default_task_hours}
                      onChange={(e) => update("default_task_hours", Number(e.target.value))}
                      onWheel={(e) => e.currentTarget.blur()}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.leaderHours")}>
                    <input
                      type="number"
                      value={config.leader_hours}
                      onChange={(e) => update("leader_hours", Number(e.target.value))}
                      onWheel={(e) => e.currentTarget.blur()}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.leaderManagementEnabled")}>
                    <input
                      type="checkbox"
                      checked={config.leader_management_enabled}
                      onChange={(e) => update("leader_management_enabled", e.target.checked)}
                      className="mt-2"
                    />
                  </Field>
                  <Field label={t("page.fields.sprintField")}>
                    <input
                      type="text"
                      value={config.sprint_field}
                      onChange={(e) => update("sprint_field", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.responsibleField")}>
                    <input
                      type="text"
                      value={config.responsible_field}
                      onChange={(e) => update("responsible_field", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.developerField")}>
                    <input
                      type="text"
                      value={config.developer_field ?? ""}
                      onChange={(e) => update("developer_field", e.target.value)}
                      placeholder="customfield_XXXXX"
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.designerField")}>
                    <input
                      type="text"
                      value={config.designer_field ?? ""}
                      onChange={(e) => update("designer_field", e.target.value)}
                      placeholder="customfield_XXXXX"
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.testerField")}>
                    <input
                      type="text"
                      value={config.tester_field ?? ""}
                      onChange={(e) => update("tester_field", e.target.value)}
                      placeholder="customfield_XXXXX"
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                </div>
              </Section>

              <Section title={t("page.sections.jiraConnection")} accent="indigo">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.jiraConnection")}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Field label={t("page.fields.jiraBaseUrl")}>
                    <input
                      type="text"
                      value={config.jira_base_url}
                      onChange={(e) => update("jira_base_url", e.target.value)}
                      placeholder="https://yourcompany.atlassian.net"
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.jiraEmail")}>
                    <input
                      type="text"
                      value={config.jira_email}
                      onChange={(e) => update("jira_email", e.target.value)}
                      placeholder="lead@yourcompany.com"
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.jiraApiToken")}>
                    <input
                      type="password"
                      value={jiraApiToken}
                      onChange={(e) => setJiraApiToken(e.target.value)}
                      placeholder={config.jira_api_token_set
                        ? t("page.fields.jiraApiTokenPlaceholderSet")
                        : t("page.fields.jiraApiTokenPlaceholderUnset")}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                </div>
              </Section>

              <Section title={t("page.sections.telegram")} accent="indigo">
                <p className="text-xs text-gray-500 mb-3">
                  {config.telegram_bot_configured
                    ? t("page.hints.telegram")
                    : t("page.hints.telegramNoToken")}
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Field label={t("page.fields.telegramBotToken")}>
                    <input
                      type="password"
                      value={telegramBotToken}
                      onChange={(e) => setTelegramBotToken(e.target.value)}
                      placeholder={config.telegram_bot_token_set
                        ? t("page.fields.telegramBotTokenPlaceholderSet")
                        : t("page.fields.telegramBotTokenPlaceholderUnset")}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.telegramChatId")}>
                    <input
                      type="text"
                      value={config.telegram_chat_id}
                      onChange={(e) => update("telegram_chat_id", e.target.value)}
                      placeholder="-1001234567890"
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.telegramDailyTime")}>
                    <input
                      type="time"
                      value={config.telegram_daily_time}
                      onChange={(e) => update("telegram_daily_time", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label={t("page.fields.telegramDailyEnabled")}>
                    <input
                      type="checkbox"
                      checked={config.telegram_daily_enabled}
                      onChange={(e) => update("telegram_daily_enabled", e.target.checked)}
                      className="mt-2"
                    />
                  </Field>
                </div>
                <div className="flex items-center gap-3 mt-4">
                  <button
                    type="button"
                    onClick={() => runTelegram(sendTodayDigest, "send")}
                    disabled={tgSending || !config.telegram_bot_configured}
                    className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
                  >
                    {t("page.telegram.sendNow")}
                  </button>
                  <button
                    type="button"
                    onClick={() => runTelegram(sendTestMessage, "test")}
                    disabled={tgSending || !config.telegram_bot_configured}
                    className="border border-gray-300 hover:bg-gray-50 disabled:opacity-50 text-gray-700 text-sm font-semibold px-4 py-2 rounded-lg transition"
                  >
                    {t("page.telegram.test")}
                  </button>
                  <span className="text-xs text-gray-400">{t("page.telegram.saveHint")}</span>
                </div>
              </Section>
            </>
          )}

          {category === "team" && (
            <>
              <Section title={t("page.sections.roles")} accent="amber">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.roles")}
                </p>
                <RolesEditor
                  value={config.roles}
                  onChange={(v) => update("roles", v)}
                />
              </Section>

              <Section title={t("page.sections.team")} accent="amber">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.team")}
                </p>
                <TeamEditor
                  value={config.team}
                  onChange={(v) => update("team", v)}
                  roleOptions={config.roles.map((r) => ({ name: r.name, display_name: r.display_name }))}
                />
              </Section>

              <Section title={t("page.sections.pseudoTasks")} accent="amber">
                <PseudoTasksEditor
                  value={config.pseudo_tasks}
                  onChange={(v) => update("pseudo_tasks", v)}
                  team={config.team}
                />
              </Section>
            </>
          )}

          {category === "pipeline" && (
            <>
              <Section title={t("page.sections.directions")} accent="emerald">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.directions")}
                </p>
                <DirectionsEditor
                  value={config.directions ?? []}
                  onChange={(v) => update("directions", v)}
                  roles={config.roles}
                  team={config.team}
                />
              </Section>

              <Section title={t("page.sections.statusBucketMapping")} accent="emerald">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.statusBucketMapping")}
                </p>
                <RoleStatusBucketsEditor
                  value={config.role_status_buckets}
                  onChange={(v) => update("role_status_buckets", v)}
                  roles={config.roles}
                  buckets={knownBuckets}
                />
              </Section>

              <Section title={t("page.sections.defaultHours")} accent="emerald">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.defaultHours")}
                </p>
                <RoleStatusHoursEditor
                  value={config.role_status_default_hours}
                  onChange={(v) => update("role_status_default_hours", v)}
                  roles={config.roles}
                />
              </Section>

              <Section title={t("page.sections.hoursFields")} accent="emerald">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.hoursFields")}
                </p>
                <DictEditor
                  value={config.role_hours_fields}
                  onChange={(v) => update("role_hours_fields", v)}
                  keyLabel={t("page.dictLabels.category")}
                  valueLabel={t("page.dictLabels.customfield")}
                />
              </Section>
            </>
          )}

          {category === "source" && (
            <>
              <Section title={t("page.sections.boards")} accent="sky">
                <DictEditor
                  value={config.boards}
                  onChange={(v) => update("boards", v)}
                  keyLabel={t("page.dictLabels.boardName")}
                  valueLabel={t("page.dictLabels.boardId")}
                  valueType="number"
                />
              </Section>

              <Section title={t("page.sections.extraComponents")} accent="sky">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.extraComponents")}
                </p>
                <StringListEditor
                  value={config.extra_components}
                  onChange={(v) => update("extra_components", v)}
                />
              </Section>

              <Section title={t("page.sections.statusPriorities")} accent="sky">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.statusPriorities")}
                </p>
                <DictEditor
                  value={config.status_priority}
                  onChange={(v) => update("status_priority", v)}
                  keyLabel={t("page.dictLabels.jiraStatus")}
                  valueLabel={t("page.dictLabels.priority")}
                  valueType="number"
                />
              </Section>

              <Section title={t("page.sections.terminalStatuses")} accent="sky">
                <p className="text-xs text-gray-500 mb-3">
                  {t("page.hints.terminalStatuses")}
                </p>
                <StringListEditor
                  value={config.terminal_statuses}
                  onChange={(v) => update("terminal_statuses", v)}
                  placeholder={t("page.placeholders.terminalStatus")}
                />
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const ACCENTS = {
  slate:   "border-slate-300",
  indigo:  "border-indigo-400",
  amber:   "border-amber-400",
  emerald: "border-emerald-400",
  sky:     "border-sky-400",
} as const;

function Section({
  title, accent = "slate", children,
}: {
  title: string;
  accent?: keyof typeof ACCENTS;
  children: React.ReactNode;
}) {
  return (
    <section className={`bg-white rounded-lg border border-gray-200 border-l-[3px] ${ACCENTS[accent]} p-4`}>
      <h2 className="font-semibold text-gray-800 text-sm mb-3">{title}</h2>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  );
}
