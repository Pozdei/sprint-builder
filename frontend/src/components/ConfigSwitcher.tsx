import { useEffect, useRef, useState } from "react";
import {
  activateConfig, createConfig, deleteConfigById, listMyConfigs,
} from "../api/configs-client";
import type { ConfigSummary } from "../types/configs";

interface Props {
  /** Колбек при смене активного конфига — нужен, чтобы хост-страница перезагрузила данные. */
  onChange: () => void;
}

/** Dropdown в шапке: показывает текущий активный конфиг, позволяет переключиться,
 *  создать новый (пустой или копией), удалить. */
export function ConfigSwitcher({ onChange }: Props) {
  const [configs, setConfigs] = useState<ConfigSummary[] | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Состояние формы создания
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newFrom, setNewFrom] = useState<number | "empty">("empty");

  const load = async () => {
    setError(null);
    try {
      const r = await listMyConfigs();
      setConfigs(r);
    } catch (e) {
      setError(extractError(e));
    }
  };

  useEffect(() => { load(); }, []);

  // Закрытие dropdown по клику снаружи
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const active = configs?.find((c) => c.is_active);

  const handleActivate = async (id: number) => {
    if (active?.id === id) {
      setOpen(false);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await activateConfig(id);
      await load();
      setOpen(false);
      onChange();
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createConfig({
        name: newName.trim(),
        source_config_id: newFrom === "empty" ? null : newFrom,
      });
      await activateConfig(created.id);
      await load();
      setCreateOpen(false);
      setOpen(false);
      setNewName("");
      setNewFrom("empty");
      onChange();
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (cfg: ConfigSummary) => {
    if (!configs) return;
    if (configs.length === 1) {
      window.alert(
        "Это последний конфиг. Удалить нельзя — после удаления было бы не с чем работать.\n" +
        "Если хочешь — сначала создай новый, потом удали старый."
      );
      return;
    }
    const ok = window.confirm(
      `Удалить конфиг "${cfg.name}"?\n\n` +
      `Все его спринты будут удалены безвозвратно. Это действие не отменить.`
    );
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await deleteConfigById(cfg.id);
      await load();
      onChange();
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="bg-white border rounded px-3 py-1 text-sm font-semibold text-gray-700 hover:bg-gray-50"
      >
        Конфиг: {active?.name || "загрузка…"} ▾
      </button>

      {open && (
        <div className="absolute top-full mt-1 right-0 bg-white border rounded-md shadow-lg min-w-[260px] z-10">
          {error && (
            <div className="bg-red-50 border-b border-red-300 text-red-800 text-xs p-2">
              {error}
            </div>
          )}

          {configs && configs.length > 0 && (
            <div className="border-b">
              {configs.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center hover:bg-gray-50 text-sm"
                >
                  <button
                    onClick={() => handleActivate(c.id)}
                    disabled={busy}
                    className={`flex-1 text-left px-3 py-2 ${
                      c.is_active ? "font-semibold text-blue-700" : "text-gray-700"
                    }`}
                  >
                    {c.is_active && "✓ "}{c.name}
                  </button>
                  <button
                    onClick={() => handleDelete(c)}
                    disabled={busy}
                    title="Удалить конфиг"
                    className="text-red-500 hover:text-red-700 px-2"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {!createOpen ? (
            <button
              onClick={() => setCreateOpen(true)}
              className="w-full text-left px-3 py-2 text-sm text-blue-600 hover:bg-blue-50"
            >
              + Создать новый конфиг
            </button>
          ) : (
            <form onSubmit={handleCreate} className="p-3 space-y-2">
              <div>
                <label className="block text-xs text-gray-600 mb-1">Имя</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                  autoFocus
                  className="w-full px-2 py-1 border rounded text-sm"
                  placeholder="Например: Разработка"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Источник</label>
                <select
                  value={String(newFrom)}
                  onChange={(e) =>
                    setNewFrom(e.target.value === "empty" ? "empty" : Number(e.target.value))
                  }
                  className="w-full px-2 py-1 border rounded text-sm bg-white"
                >
                  <option value="empty">Пустой</option>
                  {configs?.map((c) => (
                    <option key={c.id} value={c.id}>
                      Копия: {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 justify-end pt-1">
                <button
                  type="button"
                  onClick={() => setCreateOpen(false)}
                  disabled={busy}
                  className="text-xs bg-gray-300 hover:bg-gray-400 text-gray-700 px-2 py-1 rounded"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-2 py-1 rounded font-semibold"
                >
                  {busy ? "Создаю…" : "Создать"}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
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
