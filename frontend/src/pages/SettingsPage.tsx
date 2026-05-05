import { useEffect, useState } from "react";
import { getDefaultConfig, updateConfig } from "../api/client";
import { DictEditor } from "../components/settings/DictEditor";
import { StringListEditor } from "../components/settings/StringListEditor";
import { TeamEditor } from "../components/settings/TeamEditor";
import type { ConfigOut } from "../types/api";

interface Props {
  onSaved?: () => void;
}

export function SettingsPage({ onSaved }: Props) {
  const [config, setConfig] = useState<ConfigOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);

  useEffect(() => {
    getDefaultConfig()
      .then((c) => setConfig(c))
      .catch((e) => setError(extractError(e)))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    setError(null);
    try {
      // Отправляем все поля кроме id и is_default
      const { id, is_default: _isDef, ...body } = config;
      const updated = await updateConfig(id, body);
      setConfig(updated);
      setSavedAt(new Date());
      onSaved?.();
    } catch (e) {
      setError(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="text-center text-gray-500 mt-20">Загрузка конфига…</div>;
  }
  if (error && !config) {
    return (
      <div className="bg-red-50 border border-red-300 text-red-800 rounded-lg p-3">
        Не удалось загрузить конфиг: {error}
      </div>
    );
  }
  if (!config) return null;

  // Хелпер для частичного обновления — вместо setConfig({...config, X})
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
          <Field label="Часов на спринт на человека">
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
        </div>
      </Section>

      <Section title="Команда">
        <TeamEditor value={config.team} onChange={(v) => update("team", v)} />
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
          placeholder="например: 3PL integration hub"
        />
      </Section>

      <Section title="Маппинг статусов → бакет">
        <p className="text-xs text-gray-500 mb-2">
          Статус Jira → к какой фазе в файле относится.
        </p>
        <DictEditor
          value={config.status_bucket}
          onChange={(v) => update("status_bucket", v)}
          keyLabel="Статус Jira"
          valueLabel="Бакет"
          valueOptions={["Анализ", "Тестирование"]}
        />
      </Section>

      <Section title="Приоритеты статусов">
        <p className="text-xs text-gray-500 mb-2">
          Чем меньше число — тем раньше задача попадает в спринт.
        </p>
        <DictEditor
          value={config.status_priority}
          onChange={(v) => update("status_priority", v)}
          keyLabel="Статус Jira"
          valueLabel="Приоритет"
          valueType="number"
        />
      </Section>

      <Section title="Поля часов по бакету">
        <p className="text-xs text-gray-500 mb-2">
          Какое customfield считать оценкой для каждого бакета.
        </p>
        <DictEditor
          value={config.bucket_hours_field}
          onChange={(v) => update("bucket_hours_field", v)}
          keyLabel="Бакет"
          valueLabel="Customfield"
        />
      </Section>

      <Section title="Поля часов по ролям">
        <p className="text-xs text-gray-500 mb-2">
          Соответствие роль → customfield с часами. Пригодится для будущих ролей.
        </p>
        <DictEditor
          value={config.role_hours_fields}
          onChange={(v) => update("role_hours_fields", v)}
          keyLabel="Роль"
          valueLabel="Customfield"
        />
      </Section>

      <Section title="Strict assignee buckets">
        <p className="text-xs text-gray-500 mb-2">
          Бакеты, где владельцем задачи может быть только assignee из команды
          (обычно пусто).
        </p>
        <StringListEditor
          value={config.strict_assignee_buckets}
          onChange={(v) => update("strict_assignee_buckets", v)}
          placeholder="например: Тестирование"
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
        {savedAt && (
          <span className="text-sm text-green-600">
            Сохранено в {savedAt.toLocaleTimeString()}
          </span>
        )}
        {error && <span className="text-sm text-red-600">{error}</span>}
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

function extractError(e: unknown): string {
  if (e && typeof e === "object" && "response" in e) {
    const r = (e as { response?: { data?: { detail?: string } } }).response;
    if (r?.data?.detail) return r.data.detail;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
