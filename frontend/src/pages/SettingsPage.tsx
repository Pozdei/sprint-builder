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

export function SettingsPage() {
  const toast = useToast();
  const [config, setConfig] = useState<ConfigOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

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

      const { id, is_default: _isDef, team: _t, ...rest } = config;
      const body = { ...rest, team: teamForApi };
      const updated = await updateConfig(id, body);
      setConfig(updated);
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
    <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      <Section title="Базовые параметры">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Имя конфига">
            <input
              type="text"
              value={config.name}
              onChange={(e) => update("name", e.target.value)}
              className="w-full px-2 py-1 border rounded"
            />
          </Field>
          <Field label="Project Key (Jira)">
            <input
              type="text"
              value={config.project_key}
              onChange={(e) => update("project_key", e.target.value)}
              className="w-full px-2 py-1 border rounded"
            />
          </Field>
          <Field label="Часов на человека">
            <input
              type="number"
              value={config.hours_per_person}
              onChange={(e) => update("hours_per_person", Number(e.target.value))}
              className="w-full px-2 py-1 border rounded"
            />
          </Field>
          <Field label="Дефолтная оценка задачи (ч)">
            <input
              type="number"
              value={config.default_task_hours}
              onChange={(e) => update("default_task_hours", Number(e.target.value))}
              className="w-full px-2 py-1 border rounded"
            />
          </Field>
          <Field label="Часы лидов на руководство">
            <input
              type="number"
              value={config.leader_hours}
              onChange={(e) => update("leader_hours", Number(e.target.value))}
              className="w-full px-2 py-1 border rounded"
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
              className="w-full px-2 py-1 border rounded font-mono text-sm"
            />
          </Field>
          <Field label="Поле Ответственный (customfield_)">
            <input
              type="text"
              value={config.responsible_field}
              onChange={(e) => update("responsible_field", e.target.value)}
              className="w-full px-2 py-1 border rounded font-mono text-sm"
            />
          </Field>
          <Field label="Поле Разработчик (customfield_)">
            <input
              type="text"
              value={config.developer_field ?? ""}
              onChange={(e) => update("developer_field", e.target.value)}
              placeholder="customfield_XXXXX"
              className="w-full px-2 py-1 border rounded font-mono text-sm"
            />
          </Field>
          <Field label="Поле Дизайнер (customfield_)">
            <input
              type="text"
              value={config.designer_field ?? ""}
              onChange={(e) => update("designer_field", e.target.value)}
              placeholder="customfield_XXXXX"
              className="w-full px-2 py-1 border rounded font-mono text-sm"
            />
          </Field>
          <Field label="Поле Тестировщик (customfield_)">
            <input
              type="text"
              value={config.tester_field ?? ""}
              onChange={(e) => update("tester_field", e.target.value)}
              placeholder="customfield_XXXXX"
              className="w-full px-2 py-1 border rounded font-mono text-sm"
            />
          </Field>
        </div>
      </Section>

      <Section title="Роли">
        <p className="text-xs text-gray-500 mb-2">
          Чек-бокс «В спринт» включает роль для формирования. «Лид» — флаг для авто-добавления
          «Руководство».
        </p>
        <RolesEditor
          value={config.roles}
          onChange={(v) => update("roles", v)}
        />
      </Section>

      <Section title="Команда">
        <p className="text-xs text-gray-500 mb-2">
          Один человек — одна роль. Если человек в двух ролях — заведи две записи с одним accountId.
        </p>
        <TeamEditor
          value={config.team}
          onChange={(v) => update("team", v)}
          roleOptions={config.roles.map((r) => ({ name: r.name, display_name: r.display_name }))}
        />
      </Section>

      <Section title="Доски (Jira board id)">
        <DictEditor
          value={config.boards}
          onChange={(v) => update("boards", v)}
          keyLabel="Имя доски"
          valueLabel="Jira board ID"
          valueType="number"
        />
      </Section>

      <Section title="Дополнительные компоненты">
        <p className="text-xs text-gray-500 mb-2">
          Задачи проекта с этими компонентами берутся в выборку независимо от досок.
        </p>
        <StringListEditor
          value={config.extra_components}
          onChange={(v) => update("extra_components", v)}
        />
      </Section>

      <Section title="Маппинг статусов на бакеты (по ролям)">
        <p className="text-xs text-gray-500 mb-2">
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

      <Section title="Приоритеты статусов">
        <p className="text-xs text-gray-500 mb-2">
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

      <Section title="Дефолтные часы (роль, статус)">
        <p className="text-xs text-gray-500 mb-2">
          Если у задачи нет оценки, применяется этот дефолт. Например, для пары
          (Лид разработки, Код-ревью) = 1 — лид тратит на ревью 1ч по умолчанию.
        </p>
        <RoleStatusHoursEditor
          value={config.role_status_default_hours}
          onChange={(v) => update("role_status_default_hours", v)}
          roles={config.roles}
        />
      </Section>

      <Section title="Поля часов в Jira по «категориям»">
        <p className="text-xs text-gray-500 mb-2">
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

      <Section title="Направления задач">
        <p className="text-xs text-gray-500 mb-2">
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

      <Section title="Псевдо-задачи (отпуск, обучение, …)">
        <PseudoTasksEditor
          value={config.pseudo_tasks}
          onChange={(v) => update("pseudo_tasks", v)}
          team={config.team}
        />
      </Section>

      <Section title="Терминальные статусы">
        <p className="text-xs text-gray-500 mb-2">
          Статусы, в которых задача считается выполненной. Используется при закрытии
          спринта для подсчёта % выполнения.
        </p>
        <StringListEditor
          value={config.terminal_statuses}
          onChange={(v) => update("terminal_statuses", v)}
          placeholder="например: Выполнено"
        />
      </Section>

      {/* Сохранение */}
      <div className="sticky bottom-0 bg-white border-t shadow-lg -mx-6 px-6 py-3 flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold px-4 py-2 rounded-lg transition"
        >
          {saving ? "Сохраняю…" : "Сохранить"}
        </button>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-lg border p-4 shadow-sm">
      <h2 className="font-semibold text-gray-800 mb-3">{title}</h2>
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