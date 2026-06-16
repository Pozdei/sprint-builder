import { useState } from "react";
import {
  type IssueFieldsUpdate,
  updateJiraIssueFields,
} from "../api/jira-client";
import { useToast } from "./Toast";
import { extractError } from "../lib/api-error";
import type { JiraUserSearchResult } from "../types/intrusions";
import type { TaskOut } from "../types/api";
import { JiraUserSearchModal } from "./JiraUserSearchModal";

interface Props {
  task: TaskOut;
  onClose: () => void;
  onSaved: (key: string, update: IssueFieldsUpdate, devName: string | null) => void;
}

function HoursInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-0.5">{label}</label>
      <input
        type="number"
        min={0}
        step={0.5}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="не задано"
        className="w-full px-2 py-1.5 border rounded text-sm"
      />
    </div>
  );
}

export function JiraFieldEditor({ task, onClose, onSaved }: Props) {
  const toast = useToast();
  const [hoursAnalyst, setHoursAnalyst] = useState(
    task.hours_analyst != null ? String(task.hours_analyst) : "",
  );
  const [hoursTester, setHoursTester] = useState(
    task.hours_tester != null ? String(task.hours_tester) : "",
  );
  const [hoursDeveloper, setHoursDeveloper] = useState(
    task.hours_developer != null ? String(task.hours_developer) : "",
  );
  const [developer, setDeveloper] = useState<JiraUserSearchResult | null>(null);
  const [developerDisplay, setDeveloperDisplay] = useState(
    task.developer_name ?? "",
  );
  const [showUserSearch, setShowUserSearch] = useState(false);

  const [saving, setSaving] = useState(false);

  const handlePickUser = (u: JiraUserSearchResult) => {
    setDeveloper(u);
    setDeveloperDisplay(u.display_name);
    setShowUserSearch(false);
  };

  const handleSave = async () => {
    setSaving(true);

    const update: IssueFieldsUpdate = {};
    if (hoursAnalyst !== "") update.hours_analyst = Number(hoursAnalyst);
    if (hoursTester !== "") update.hours_tester = Number(hoursTester);
    if (hoursDeveloper !== "") update.hours_developer = Number(hoursDeveloper);
    if (developer) update.developer_account_id = developer.account_id;

    if (Object.keys(update).length === 0) {
      onClose();
      return;
    }

    try {
      await updateJiraIssueFields(task.key, update);
      onSaved(task.key, update, developer?.display_name ?? null);
      toast.success(`${task.key}: поля обновлены в Jira`);
      onClose();
    } catch (e: unknown) {
      toast.error(extractError(e, "Ошибка сохранения"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-black/40 flex items-center justify-center z-40"
        onClick={onClose}
      >
        <div
          className="bg-white rounded-xl shadow-xl border w-full max-w-md p-6 space-y-4"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Заголовок */}
          <div>
            <h3 className="font-semibold text-gray-800 text-base">
              Редактировать поля в Jira
            </h3>
            <div className="mt-0.5">
              <a
                href={task.url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-blue-600 hover:underline font-mono"
              >
                {task.key}
              </a>
              <span className="text-sm text-gray-500 ml-2 truncate">
                {task.summary}
              </span>
            </div>
          </div>

          {/* Поля часов */}
          <div className="grid grid-cols-3 gap-3">
            <HoursInput
              label="Часы аналитика"
              value={hoursAnalyst}
              onChange={setHoursAnalyst}
            />
            <HoursInput
              label="Часы тестера"
              value={hoursTester}
              onChange={setHoursTester}
            />
            <HoursInput
              label="Часы разработчика"
              value={hoursDeveloper}
              onChange={setHoursDeveloper}
            />
          </div>

          {/* Разработчик */}
          <div>
            <label className="block text-xs text-gray-500 mb-0.5">
              Разработчик
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                readOnly
                value={developerDisplay}
                placeholder="не задан"
                className="flex-1 px-2 py-1.5 border rounded text-sm bg-gray-50"
              />
              <button
                type="button"
                onClick={() => setShowUserSearch(true)}
                className="px-3 py-1.5 border rounded text-sm bg-white hover:bg-gray-50 text-blue-600"
              >
                Выбрать
              </button>
              {developer && (
                <button
                  type="button"
                  onClick={() => { setDeveloper(null); setDeveloperDisplay(task.developer_name ?? ""); }}
                  className="px-2 py-1.5 border rounded text-sm text-red-500 hover:bg-red-50"
                  title="Отменить выбор"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Кнопки */}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="px-4 py-2 text-sm border rounded hover:bg-gray-50 text-gray-600"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded font-medium"
            >
              {saving ? "Сохраняю…" : "Сохранить в Jira"}
            </button>
          </div>
        </div>
      </div>

      {showUserSearch && (
        <JiraUserSearchModal
          onClose={() => setShowUserSearch(false)}
          onPick={handlePickUser}
        />
      )}
    </>
  );
}
