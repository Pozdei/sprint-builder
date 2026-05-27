import { useEffect, useState } from "react";
import {
  adminCreateUser, adminDeleteUser, adminGetAllSalaries, adminListConfigs, adminListSprints,
  adminListUsers, adminResetPassword, adminTransferConfig, adminUpdateAllSalaries, adminUpdateUser,
} from "../api/admin-client";
import { extractError } from "../lib/api-error";
import type {
  AdminConfigSummary, AdminSprintSummary, AdminTeamMember,
} from "../types/admin";
import type { UserOut } from "../types/api";

type DataState = {
  users: UserOut[];
  configs: AdminConfigSummary[];
  sprints: AdminSprintSummary[];
};

export function AdminPage() {
  const [tab, setTab] = useState<"manage" | "salaries">("manage");
  const [data, setData] = useState<DataState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Модалки
  const [createOpen, setCreateOpen] = useState(false);
  const [resetPwForUserId, setResetPwForUserId] = useState<number | null>(null);
  const [transferForConfigId, setTransferForConfigId] = useState<number | null>(null);

  const reload = async () => {
    setLoading(true);
    setError(null);
    try {
      const [users, configs, sprints] = await Promise.all([
        adminListUsers(),
        adminListConfigs(),
        adminListSprints(),
      ]);
      setData({ users, configs, sprints });
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  if (loading) {
    return <div className="text-center text-gray-500 mt-20">Загрузка…</div>;
  }
  if (error && !data) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="bg-red-50 border border-red-300 text-red-800 rounded-lg p-3">
          {error}
        </div>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-gray-800">Админка</h1>
        <div className="flex gap-1">
          <button
            onClick={() => setTab("manage")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              tab === "manage" ? "bg-blue-100 text-blue-800" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            Управление
          </button>
          <button
            onClick={() => setTab("salaries")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              tab === "salaries" ? "bg-emerald-100 text-emerald-800" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            Оклады
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-300 text-red-800 rounded-lg p-3">
          {error}
        </div>
      )}

      {tab === "manage" && (
        <>
          {/* Пользователи */}
          <section className="bg-white rounded-lg border p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-gray-800">
                Пользователи ({data.users.length})
              </h2>
              <button
                onClick={() => setCreateOpen(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-3 py-1.5 rounded"
              >
                + Создать
              </button>
            </div>
            <UsersTable
              users={data.users}
              onUpdate={async (id, body) => {
                await adminUpdateUser(id, body);
                await reload();
              }}
              onResetPassword={(id) => setResetPwForUserId(id)}
              onDelete={async (u) => {
                const ok = window.confirm(
                  `Удалить пользователя ${u.email}?\n\n` +
                  `Вместе с ним удалится его конфиг и все его спринты (CASCADE).`
                );
                if (!ok) return;
                try {
                  await adminDeleteUser(u.id);
                  await reload();
                } catch (e) {
                  setError(extractError(e));
                }
              }}
            />
          </section>

          {/* Конфиги */}
          <section className="bg-white rounded-lg border p-4 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-3">
              Конфиги ({data.configs.length})
            </h2>
            <ConfigsTable
              configs={data.configs}
              onTransfer={(cid) => setTransferForConfigId(cid)}
            />
          </section>

          {/* Спринты (read-only) */}
          <section className="bg-white rounded-lg border p-4 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-3">
              Спринты ({data.sprints.length})
            </h2>
            <SprintsTable sprints={data.sprints} />
          </section>

          {createOpen && (
            <CreateUserModal
              onClose={() => setCreateOpen(false)}
              onCreated={async () => {
                setCreateOpen(false);
                await reload();
              }}
              onError={setError}
            />
          )}

          {resetPwForUserId !== null && (
            <ResetPasswordModal
              user={data.users.find((u) => u.id === resetPwForUserId)!}
              onClose={() => setResetPwForUserId(null)}
              onDone={() => setResetPwForUserId(null)}
              onError={setError}
            />
          )}

          {transferForConfigId !== null && (
            <TransferConfigModal
              config={data.configs.find((c) => c.id === transferForConfigId)!}
              leads={data.users.filter((u) => u.role === "lead")}
              onClose={() => setTransferForConfigId(null)}
              onDone={async () => {
                setTransferForConfigId(null);
                await reload();
              }}
              onError={setError}
            />
          )}
        </>
      )}

      {tab === "salaries" && (
        <SalariesTab />
      )}
    </div>
  );
}

// -------------------- Таблица пользователей --------------------

function UsersTable({
  users, onUpdate, onResetPassword, onDelete,
}: {
  users: UserOut[];
  onUpdate: (id: number, body: { display_name?: string; role?: string; is_active?: boolean }) => Promise<void>;
  onResetPassword: (id: number) => void;
  onDelete: (u: UserOut) => void;
}) {
  return (
    <table className="w-full text-sm">
      <thead className="bg-gray-100 border-b">
        <tr>
          <th className="text-left px-3 py-1.5">ID</th>
          <th className="text-left px-3 py-1.5">Email</th>
          <th className="text-left px-3 py-1.5">Имя</th>
          <th className="text-left px-3 py-1.5 w-32">Роль</th>
          <th className="text-center px-3 py-1.5 w-24">Активен</th>
          <th className="text-right px-3 py-1.5">Действия</th>
        </tr>
      </thead>
      <tbody>
        {users.map((u) => (
          <UserRow
            key={u.id}
            user={u}
            onUpdate={onUpdate}
            onResetPassword={onResetPassword}
            onDelete={onDelete}
          />
        ))}
      </tbody>
    </table>
  );
}

function UserRow({
  user, onUpdate, onResetPassword, onDelete,
}: {
  user: UserOut;
  onUpdate: (id: number, body: { display_name?: string; role?: string; is_active?: boolean }) => Promise<void>;
  onResetPassword: (id: number) => void;
  onDelete: (u: UserOut) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(user.display_name);
  const [role, setRole] = useState(user.role);
  const [isActive, setIsActive] = useState(user.is_active);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await onUpdate(user.id, {
        display_name: displayName !== user.display_name ? displayName : undefined,
        role: role !== user.role ? role : undefined,
        is_active: isActive !== user.is_active ? isActive : undefined,
      });
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => {
    setDisplayName(user.display_name);
    setRole(user.role);
    setIsActive(user.is_active);
    setEditing(false);
  };

  return (
    <tr className="border-b">
      <td className="px-3 py-1.5 font-mono text-xs">{user.id}</td>
      <td className="px-3 py-1.5">{user.email}</td>
      <td className="px-3 py-1.5">
        {editing ? (
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full px-2 py-0.5 border rounded text-sm"
          />
        ) : (
          user.display_name || <span className="text-gray-400">—</span>
        )}
      </td>
      <td className="px-3 py-1.5">
        {editing ? (
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="px-2 py-0.5 border rounded text-sm bg-white"
          >
            <option value="lead">lead</option>
            <option value="admin">admin</option>
          </select>
        ) : (
          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
            user.role === "admin" ? "bg-purple-100 text-purple-800" : "bg-blue-100 text-blue-800"
          }`}>
            {user.role}
          </span>
        )}
      </td>
      <td className="text-center px-3 py-1.5">
        {editing ? (
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
        ) : (
          user.is_active ? "✓" : <span className="text-red-500">✗</span>
        )}
      </td>
      <td className="text-right px-3 py-1.5">
        {editing ? (
          <div className="flex gap-1 justify-end">
            <button
              onClick={save}
              disabled={busy}
              className="text-xs bg-green-600 hover:bg-green-700 text-white px-2 py-1 rounded"
            >
              Сохранить
            </button>
            <button
              onClick={cancel}
              disabled={busy}
              className="text-xs bg-gray-300 hover:bg-gray-400 text-gray-700 px-2 py-1 rounded"
            >
              Отмена
            </button>
          </div>
        ) : (
          <div className="flex gap-1 justify-end">
            <button
              onClick={() => setEditing(true)}
              className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded"
            >
              Редактировать
            </button>
            <button
              onClick={() => onResetPassword(user.id)}
              className="text-xs bg-yellow-500 hover:bg-yellow-600 text-white px-2 py-1 rounded"
            >
              Пароль
            </button>
            <button
              onClick={() => onDelete(user)}
              className="text-xs bg-red-600 hover:bg-red-700 text-white px-2 py-1 rounded"
            >
              Удалить
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

// -------------------- Таблица конфигов --------------------

function ConfigsTable({
  configs, onTransfer,
}: {
  configs: AdminConfigSummary[];
  onTransfer: (configId: number) => void;
}) {
  if (configs.length === 0) {
    return <div className="text-gray-400 text-sm">Конфигов нет.</div>;
  }
  return (
    <table className="w-full text-sm">
      <thead className="bg-gray-100 border-b">
        <tr>
          <th className="text-left px-3 py-1.5">ID</th>
          <th className="text-left px-3 py-1.5">Имя</th>
          <th className="text-left px-3 py-1.5">Владелец</th>
          <th className="text-left px-3 py-1.5">Спринтов</th>
          <th className="text-right px-3 py-1.5">Действия</th>
        </tr>
      </thead>
      <tbody>
        {configs.map((c) => (
          <tr key={c.id} className="border-b">
            <td className="px-3 py-1.5 font-mono text-xs">{c.id}</td>
            <td className="px-3 py-1.5">{c.name}</td>
            <td className="px-3 py-1.5">
              {c.owner_email ? (
                <span>
                  {c.owner_email}
                  {c.owner_display_name && (
                    <span className="text-gray-500 text-xs ml-1">
                      ({c.owner_display_name})
                    </span>
                  )}
                </span>
              ) : (
                <span className="text-red-500 italic">нет владельца</span>
              )}
            </td>
            <td className="px-3 py-1.5">{c.sprints_count}</td>
            <td className="text-right px-3 py-1.5">
              <button
                onClick={() => onTransfer(c.id)}
                className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-2 py-1 rounded"
              >
                Передать
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// -------------------- Таблица спринтов --------------------

function SprintsTable({ sprints }: { sprints: AdminSprintSummary[] }) {
  if (sprints.length === 0) {
    return <div className="text-gray-400 text-sm">Спринтов нет.</div>;
  }
  return (
    <table className="w-full text-sm">
      <thead className="bg-gray-100 border-b">
        <tr>
          <th className="text-left px-3 py-1.5">ID</th>
          <th className="text-left px-3 py-1.5">№</th>
          <th className="text-left px-3 py-1.5">Статус</th>
          <th className="text-left px-3 py-1.5">Конфиг</th>
          <th className="text-left px-3 py-1.5">Владелец</th>
        </tr>
      </thead>
      <tbody>
        {sprints.map((s) => (
          <tr key={s.id} className="border-b">
            <td className="px-3 py-1.5 font-mono text-xs">{s.id}</td>
            <td className="px-3 py-1.5 font-mono">{s.sprint_num}</td>
            <td className="px-3 py-1.5">{s.status}</td>
            <td className="px-3 py-1.5 font-mono text-xs">{s.config_id ?? "—"}</td>
            <td className="px-3 py-1.5 text-gray-600">{s.owner_email || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// -------------------- Модалки --------------------

function ModalShell({ title, children, onClose }: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl border w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-semibold text-gray-800 mb-4">{title}</h3>
        {children}
      </div>
    </div>
  );
}

function CreateUserModal({
  onClose, onCreated, onError,
}: {
  onClose: () => void;
  onCreated: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("lead");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await adminCreateUser({ email, display_name: displayName, role, password });
      await onCreated();
    } catch (err) {
      onError(extractError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell title="Создать пользователя" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="text-sm text-gray-600 block mb-1">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-2 py-1.5 border rounded"
            autoFocus
          />
        </div>
        <div>
          <label className="text-sm text-gray-600 block mb-1">Имя</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full px-2 py-1.5 border rounded"
          />
        </div>
        <div>
          <label className="text-sm text-gray-600 block mb-1">Роль</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full px-2 py-1.5 border rounded bg-white"
          >
            <option value="lead">lead — обычный пользователь</option>
            <option value="admin">admin — управление пользователями</option>
          </select>
        </div>
        <div>
          <label className="text-sm text-gray-600 block mb-1">Пароль</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-2 py-1.5 border rounded"
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-3 py-1.5 rounded text-sm"
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={busy}
            className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-sm font-semibold"
          >
            {busy ? "Создаю…" : "Создать"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function ResetPasswordModal({
  user, onClose, onDone, onError,
}: {
  user: UserOut;
  onClose: () => void;
  onDone: () => void;
  onError: (msg: string) => void;
}) {
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await adminResetPassword(user.id, pw);
      onDone();
    } catch (err) {
      onError(extractError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell title={`Сброс пароля: ${user.email}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-gray-600">
          Введите новый пароль для пользователя. Передайте его лично.
        </p>
        <input
          type="password"
          required
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="w-full px-2 py-1.5 border rounded"
          autoFocus
          placeholder="Новый пароль"
        />
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-3 py-1.5 rounded text-sm"
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={busy}
            className="bg-yellow-500 hover:bg-yellow-600 text-white px-3 py-1.5 rounded text-sm font-semibold"
          >
            {busy ? "Сохраняю…" : "Сменить"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function TransferConfigModal({
  config, leads, onClose, onDone, onError,
}: {
  config: AdminConfigSummary;
  leads: UserOut[];
  onClose: () => void;
  onDone: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const [newOwnerId, setNewOwnerId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newOwnerId === null) return;
    const newOwner = leads.find((u) => u.id === newOwnerId);
    if (!newOwner) return;

    const ok = window.confirm(
      `Передать конфиг "${config.name}" пользователю ${newOwner.email}?\n\n` +
      `Все спринты этого конфига перейдут к нему.\n` +
      `Прошлый владелец останется без конфига — при следующем логине ему будет создан новый пустой.`
    );
    if (!ok) return;

    setBusy(true);
    try {
      await adminTransferConfig(config.id, newOwnerId);
      await onDone();
    } catch (err) {
      onError(extractError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <ModalShell title={`Передать конфиг: ${config.name}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-gray-600">
          Текущий владелец: <b>{config.owner_email || "—"}</b>
          <br/>
          Спринтов в конфиге: <b>{config.sprints_count}</b>
        </p>
        <div>
          <label className="text-sm text-gray-600 block mb-1">Новый владелец (lead)</label>
          <select
            required
            value={newOwnerId ?? ""}
            onChange={(e) => setNewOwnerId(Number(e.target.value))}
            className="w-full px-2 py-1.5 border rounded bg-white"
          >
            <option value="">— выберите —</option>
            {leads.map((u) => (
              <option key={u.id} value={u.id}>
                {u.email} {u.display_name && `(${u.display_name})`}
              </option>
            ))}
          </select>
          {leads.length === 0 && (
            <p className="text-xs text-orange-600 mt-1">
              Нет lead-пользователей. Сначала создай нужного.
            </p>
          )}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-3 py-1.5 rounded text-sm"
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={busy || newOwnerId === null}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
          >
            {busy ? "Передаю…" : "Передать"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function SalariesTab() {
  const [members, setMembers] = useState<AdminTeamMember[] | null>(null);
  const [salaries, setSalaries] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminGetAllSalaries()
      .then((ms) => {
        setMembers(ms);
        const init: Record<string, number> = {};
        ms.forEach((m) => { init[m.account_id] = m.salary; });
        setSalaries(init);
      })
      .catch((e) => setError(extractError(e)))
      .finally(() => setLoading(false));
  }, []);

  const updateSalary = (accId: string, raw: string) => {
    const n = parseInt(raw.replace(/\D/g, ""), 10);
    setSalaries((prev) => ({ ...prev, [accId]: isNaN(n) ? 0 : n }));
    setSavedAt(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await adminUpdateAllSalaries(salaries);
      setSavedAt(new Date());
    } catch (e) {
      setError(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="bg-white rounded-lg border p-4 shadow-sm">
      <h2 className="font-semibold text-gray-800 mb-1">Оклады команды</h2>
      <p className="text-xs text-gray-500 mb-4">
        Оклад в ₽/месяц. Используется для расчёта стоимости проекта в прогнозе реализации.
        Конфиденциально — участники команды не видят эти данные.
      </p>

      {error && (
        <div className="mb-3 bg-red-50 border border-red-300 text-red-800 rounded p-2 text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-gray-400 text-sm py-4">Загрузка…</div>
      ) : members === null ? null : members.length === 0 ? (
        <div className="text-gray-400 text-sm py-4">
          Команда пуста. Добавьте участников в настройках конфига.
        </div>
      ) : (
        <>
          <table className="w-full text-sm mb-4">
            <thead className="bg-gray-100 border-b">
              <tr>
                <th className="text-left px-3 py-1.5">Имя в Jira</th>
                <th className="text-left px-3 py-1.5">Имя для файла</th>
                <th className="text-left px-3 py-1.5 w-32">Роль</th>
                <th className="text-left px-3 py-1.5 w-44">Оклад, ₽/мес</th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.account_id} className="border-b">
                  <td className="px-3 py-1.5">{m.jira_name}</td>
                  <td className="px-3 py-1.5 text-gray-500">{m.file_name || "—"}</td>
                  <td className="px-3 py-1.5 text-gray-500">{m.role}</td>
                  <td className="px-3 py-1.5">
                    <input
                      type="text"
                      inputMode="numeric"
                      value={salaries[m.account_id] ? salaries[m.account_id].toLocaleString("ru-RU") : ""}
                      onChange={(e) => updateSalary(m.account_id, e.target.value)}
                      placeholder="0"
                      className="w-full px-2 py-1 border rounded text-sm text-right"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 text-white px-4 py-2 rounded text-sm font-semibold"
            >
              {saving ? "Сохраняю…" : "Сохранить"}
            </button>
            {savedAt && (
              <span className="text-sm text-green-600">
                Сохранено в {savedAt.toLocaleTimeString()}
              </span>
            )}
          </div>
        </>
      )}
    </section>
  );
}