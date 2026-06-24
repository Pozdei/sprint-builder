import { useEffect, useMemo, useState } from "react";
import { getDefaultConfig, updateConfig } from "../api/client";
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

const CATEGORIES: { id: CategoryId; icon: string; label: string; hint: string }[] = [
  { id: "general",  icon: "⚙️", label: "Основное",     hint: "Проект, бюджет, подключение к Jira" },
  { id: "team",     icon: "👥", label: "Команда",       hint: "Роли, участники, псевдо-задачи" },
  { id: "pipeline", icon: "🔄", label: "Pipeline",      hint: "Направления, статусы, часы по умолчанию" },
  { id: "source",   icon: "🗂️", label: "Источник задач", hint: "Доски, компоненты, приоритеты" },
];

export function SettingsPage() {
  const toast = useToast();
  const [config, setConfig] = useState<ConfigOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [category, setCategory] = useState<CategoryId>("general");
  // Токен не приходит с сервера (write-only) — отдельное поле, шлём только если ввели новый.
  const [jiraApiToken, setJiraApiToken] = useState("");

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
    ["Руководство", "Отсутствие", "Обучение"].forEach((b) => set.add(b));
    return Array.from(set).sort();
  }, [config]);

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

      const { id, is_default: _isDef, jira_api_token_set: _tokenSet, team: _t, ...rest } = config;
      const body: typeof rest & { team: typeof teamForApi; jira_api_token?: string } = {
        ...rest, team: teamForApi,
      };
      if (jiraApiToken.trim()) body.jira_api_token = jiraApiToken.trim();
      const updated = await updateConfig(id, body);
      setConfig(updated);
      setJiraApiToken("");
      toast.success("Настройки сохранены");
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-center text-gray-500 mt-20">Загрузка конфига…</div>;
  }
  if (loadError && !config) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="bg-red-50 border border-red-300 text-red-800 rounded-lg p-3">
          Не удалось загрузить конфиг: {loadError}
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
          <h1 className="text-xl font-bold text-gray-900">Настройки</h1>
          <p className="text-sm text-gray-500 mt-0.5">Конфигурация «{config.name}»</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white text-sm font-semibold px-4 py-2 rounded-lg transition"
        >
          {saving ? "Сохраняю…" : "Сохранить"}
        </button>
      </div>

      <div className="flex gap-6">
        {/* Боковая навигация по категориям */}
        <nav className="w-52 flex-none space-y-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setCategory(cat.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg transition border-l-2 ${
                category === cat.id
                  ? "bg-indigo-50 border-indigo-600"
                  : "border-transparent hover:bg-gray-50"
              }`}
            >
              <div className={`text-sm font-medium flex items-center gap-2 ${
                category === cat.id ? "text-indigo-700" : "text-gray-700"
              }`}>
                <span>{cat.icon}</span> {cat.label}
              </div>
              <div className="text-xs text-gray-400 mt-0.5 leading-snug">{cat.hint}</div>
            </button>
          ))}
        </nav>

        {/* Контент активной категории */}
        <div className="flex-1 min-w-0 space-y-5">
          {category === "general" && (
            <>
              <Section title="Базовые параметры" accent="slate">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Field label="Имя конфига">
                    <input
                      type="text"
                      value={config.name}
                      onChange={(e) => update("name", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label="Project Key (Jira)">
                    <input
                      type="text"
                      value={config.project_key}
                      onChange={(e) => update("project_key", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label="Часов на человека">
                    <input
                      type="number"
                      value={config.hours_per_person}
                      onChange={(e) => update("hours_per_person", Number(e.target.value))}
                      onWheel={(e) => e.currentTarget.blur()}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label="Дефолтная оценка задачи (ч)">
                    <input
                      type="number"
                      value={config.default_task_hours}
                      onChange={(e) => update("default_task_hours", Number(e.target.value))}
                      onWheel={(e) => e.currentTarget.blur()}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label="Часы лидов на руководство">
                    <input
                      type="number"
                      value={config.leader_hours}
                      onChange={(e) => update("leader_hours", Number(e.target.value))}
                      onWheel={(e) => e.currentTarget.blur()}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label="Добавлять «Руководство» лидам автоматически">
                    <input
                      type="checkbox"
                      checked={config.leader_management_enabled}
                      onChange={(e) => update("leader_management_enabled", e.target.checked)}
                      className="mt-2"
                    />
                  </Field>
                  <Field label="Поле Sprint (customfield_)">
                    <input
                      type="text"
                      value={config.sprint_field}
                      onChange={(e) => update("sprint_field", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label="Поле Ответственный (customfield_)">
                    <input
                      type="text"
                      value={config.responsible_field}
                      onChange={(e) => update("responsible_field", e.target.value)}
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label="Поле Разработчик (customfield_)">
                    <input
                      type="text"
                      value={config.developer_field ?? ""}
                      onChange={(e) => update("developer_field", e.target.value)}
                      placeholder="customfield_XXXXX"
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label="Поле Дизайнер (customfield_)">
                    <input
                      type="text"
                      value={config.designer_field ?? ""}
                      onChange={(e) => update("designer_field", e.target.value)}
                      placeholder="customfield_XXXXX"
                      className="w-full px-2 py-1.5 border rounded-md font-mono text-sm"
                    />
                  </Field>
                  <Field label="Поле Тестировщик (customfield_)">
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

              <Section title="Подключение к Jira" accent="indigo">
                <p className="text-xs text-gray-500 mb-3">
                  Пусто = используются настройки сервера (.env). Заполни, если для этого конфига
                  нужен другой Jira-аккаунт или инстанс — например, для прод-эксплуатации с
                  несколькими лидами.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Field label="Jira Base URL">
                    <input
                      type="text"
                      value={config.jira_base_url}
                      onChange={(e) => update("jira_base_url", e.target.value)}
                      placeholder="https://yourcompany.atlassian.net"
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label="Jira Email">
                    <input
                      type="text"
                      value={config.jira_email}
                      onChange={(e) => update("jira_email", e.target.value)}
                      placeholder="lead@yourcompany.com"
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                  <Field label="Jira API Token">
                    <input
                      type="password"
                      value={jiraApiToken}
                      onChange={(e) => setJiraApiToken(e.target.value)}
                      placeholder={config.jira_api_token_set ? "Задан — оставь пустым, чтобы не менять" : "Не задан"}
                      className="w-full px-2 py-1.5 border rounded-md text-sm"
                    />
                  </Field>
                </div>
              </Section>
            </>
          )}

          {category === "team" && (
            <>
              <Section title="Роли" accent="amber">
                <p className="text-xs text-gray-500 mb-3">
                  Чек-бокс «В спринт» включает роль для формирования. «Лид» — флаг для авто-добавления
                  «Руководство».
                </p>
                <RolesEditor
                  value={config.roles}
                  onChange={(v) => update("roles", v)}
                />
              </Section>

              <Section title="Команда" accent="amber">
                <p className="text-xs text-gray-500 mb-3">
                  Один человек — одна роль. Если человек в двух ролях — заведи две записи с одним accountId.
                </p>
                <TeamEditor
                  value={config.team}
                  onChange={(v) => update("team", v)}
                  roleOptions={config.roles.map((r) => ({ name: r.name, display_name: r.display_name }))}
                />
              </Section>

              <Section title="Псевдо-задачи (отпуск, обучение, …)" accent="amber">
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
              <Section title="Направления задач" accent="emerald">
                <p className="text-xs text-gray-500 mb-3">
                  Направление определяется по меткам Jira. Для каждого направления задан pipeline видов
                  работ. Задачи разработчика, завершающиеся в спринте, автоматически порождают тестирование
                  (аналитику) и код-ревью (лиду). Задачи дизайнера — дизайн-ревью лиду.
                </p>
                <DirectionsEditor
                  value={config.directions ?? []}
                  onChange={(v) => update("directions", v)}
                  roles={config.roles}
                  team={config.team}
                />
              </Section>

              <Section title="Маппинг статусов на бакеты (по ролям)" accent="emerald">
                <p className="text-xs text-gray-500 mb-3">
                  Один статус может относиться к разным бакетам у разных ролей. Например,
                  «В разработке» = «Разработка» у разработчика и «Тестирование» у аналитика.
                </p>
                <RoleStatusBucketsEditor
                  value={config.role_status_buckets}
                  onChange={(v) => update("role_status_buckets", v)}
                  roles={config.roles}
                  buckets={knownBuckets}
                />
              </Section>

              <Section title="Дефолтные часы (роль, статус)" accent="emerald">
                <p className="text-xs text-gray-500 mb-3">
                  Если у задачи нет оценки, применяется этот дефолт. Например, для пары
                  (Лид разработки, Код-ревью) = 1 — лид тратит на ревью 1ч по умолчанию.
                </p>
                <RoleStatusHoursEditor
                  value={config.role_status_default_hours}
                  onChange={(v) => update("role_status_default_hours", v)}
                  roles={config.roles}
                />
              </Section>

              <Section title="Поля часов в Jira по «категориям»" accent="emerald">
                <p className="text-xs text-gray-500 mb-3">
                  analyst → Время аналитика, tester → Время тестировщика, developer → Время разработчика,
                  designer → Время дизайнера. Используется для оценки часов по бакету.
                </p>
                <DictEditor
                  value={config.role_hours_fields}
                  onChange={(v) => update("role_hours_fields", v)}
                  keyLabel="Категория"
                  valueLabel="Customfield"
                />
              </Section>
            </>
          )}

          {category === "source" && (
            <>
              <Section title="Доски (Jira board id)" accent="sky">
                <DictEditor
                  value={config.boards}
                  onChange={(v) => update("boards", v)}
                  keyLabel="Имя доски"
                  valueLabel="Jira board ID"
                  valueType="number"
                />
              </Section>

              <Section title="Дополнительные компоненты" accent="sky">
                <p className="text-xs text-gray-500 mb-3">
                  Задачи проекта с этими компонентами берутся в выборку независимо от досок.
                </p>
                <StringListEditor
                  value={config.extra_components}
                  onChange={(v) => update("extra_components", v)}
                />
              </Section>

              <Section title="Приоритеты статусов" accent="sky">
                <p className="text-xs text-gray-500 mb-3">
                  Чем меньше число — тем раньше задача попадает в спринт. Глобально на статус.
                </p>
                <DictEditor
                  value={config.status_priority}
                  onChange={(v) => update("status_priority", v)}
                  keyLabel="Статус Jira"
                  valueLabel="Приоритет"
                  valueType="number"
                />
              </Section>

              <Section title="Терминальные статусы" accent="sky">
                <p className="text-xs text-gray-500 mb-3">
                  Статусы, в которых задача считается выполненной. Используется при закрытии
                  спринта для подсчёта % выполнения.
                </p>
                <StringListEditor
                  value={config.terminal_statuses}
                  onChange={(v) => update("terminal_statuses", v)}
                  placeholder="например: Выполнено"
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
