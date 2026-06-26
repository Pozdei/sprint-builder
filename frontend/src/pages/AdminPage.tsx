import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  adminCreateUser, adminDeleteUser, adminGetAllSalaries, adminListConfigs, adminListSprints,
  adminListUsers, adminResetPassword, adminTransferConfig, adminUpdateAllSalaries, adminUpdateUser,
} from "../api/admin-client";
import { extractError } from "../lib/api-error";
import { useToast } from "../components/Toast";
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
  const { t } = useTranslation(["admin", "common"]);
  const toast = useToast();
  const [tab, setTab] = useState<"manage" | "salaries">("manage");
  const [data, setData] = useState<DataState | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Модалки
  const [createOpen, setCreateOpen] = useState(false);
  const [resetPwForUserId, setResetPwForUserId] = useState<number | null>(null);
  const [transferForConfigId, setTransferForConfigId] = useState<number | null>(null);

  const reload = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [users, configs, sprints] = await Promise.all([
        adminListUsers(),
        adminListConfigs(),
        adminListSprints(),
      ]);
      setData({ users, configs, sprints });
    } catch (e) {
      setLoadError(extractError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  if (loading) {
    return <div className="text-center text-gray-500 mt-20">{t("common:loading")}</div>;
  }
  if (loadError && !data) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="bg-red-50 border border-red-300 text-red-800 rounded-lg p-3">
          {loadError}
        </div>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-gray-800">{t("admin:title")}</h1>
        <div className="flex gap-1">
          <button
            onClick={() => setTab("manage")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              tab === "manage" ? "bg-blue-100 text-blue-800" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {t("admin:tabs.manage")}
          </button>
          <button
            onClick={() => setTab("salaries")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              tab === "salaries" ? "bg-emerald-100 text-emerald-800" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {t("admin:tabs.salaries")}
          </button>
        </div>
      </div>

      {tab === "manage" && (
        <>
          {/* Пользователи */}
          <section className="bg-white rounded-lg border p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-gray-800">
                {t("admin:users.sectionTitle", { count: data.users.length })}
              </h2>
              <button
                onClick={() => setCreateOpen(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-3 py-1.5 rounded"
              >
                {t("admin:users.createButton")}
              </button>
            </div>
            <UsersTable
              users={data.users}
              onUpdate={async (id, body) => {
                await adminUpdateUser(id, body);
                await reload();
                toast.success(t("admin:users.toast.updated"));
              }}
              onResetPassword={(id) => setResetPwForUserId(id)}
              onDelete={async (u) => {
                const ok = window.confirm(
                  t("admin:users.deleteConfirm", { email: u.email })
                );
                if (!ok) return;
                try {
                  await adminDeleteUser(u.id);
                  await reload();
                  toast.success(t("admin:users.toast.deleted", { email: u.email }));
                } catch (e) {
                  toast.error(extractError(e));
                }
              }}
            />
          </section>

          {/* Конфиги */}
          <section className="bg-white rounded-lg border p-4 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-3">
              {t("admin:configs.sectionTitle", { count: data.configs.length })}
            </h2>
            <ConfigsTable
              configs={data.configs}
              onTransfer={(cid) => setTransferForConfigId(cid)}
            />
          </section>

          {/* Спринты (read-only) */}
          <section className="bg-white rounded-lg border p-4 shadow-sm">
            <h2 className="font-semibold text-gray-800 mb-3">
              {t("admin:sprints.sectionTitle", { count: data.sprints.length })}
            </h2>
            <SprintsTable sprints={data.sprints} />
          </section>

          {createOpen && (
            <CreateUserModal
              onClose={() => setCreateOpen(false)}
              onCreated={async () => {
                setCreateOpen(false);
                await reload();
                toast.success(t("admin:users.toast.created"));
              }}
              onError={toast.error}
            />
          )}

          {resetPwForUserId !== null && (
            <ResetPasswordModal
              user={data.users.find((u) => u.id === resetPwForUserId)!}
              onClose={() => setResetPwForUserId(null)}
              onDone={() => {
                setResetPwForUserId(null);
                toast.success(t("admin:users.toast.passwordChanged"));
              }}
              onError={toast.error}
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
                toast.success(t("admin:configs.toast.transferred"));
              }}
              onError={toast.error}
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
  const { t } = useTranslation(["admin", "common"]);
  return (
    <table className="w-full text-sm">
      <thead className="bg-gray-100 border-b">
        <tr>
          <th className="text-left px-3 py-1.5">{t("admin:users.table.id")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:users.table.email")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:users.table.name")}</th>
          <th className="text-left px-3 py-1.5 w-32">{t("admin:users.table.role")}</th>
          <th className="text-center px-3 py-1.5 w-24">{t("admin:users.table.active")}</th>
          <th className="text-right px-3 py-1.5">{t("common:actions")}</th>
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
  const { t } = useTranslation(["admin", "common"]);
  const toast = useToast();
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
    } catch (e) {
      toast.error(extractError(e));
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
            <option value="lead">{t("admin:users.roleOptions.lead")}</option>
            <option value="admin">{t("admin:users.roleOptions.admin")}</option>
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
              {t("common:save")}
            </button>
            <button
              onClick={cancel}
              disabled={busy}
              className="text-xs bg-gray-300 hover:bg-gray-400 text-gray-700 px-2 py-1 rounded"
            >
              {t("common:cancel")}
            </button>
          </div>
        ) : (
          <div className="flex gap-1 justify-end">
            <button
              onClick={() => setEditing(true)}
              className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded"
            >
              {t("admin:users.actions.edit")}
            </button>
            <button
              onClick={() => onResetPassword(user.id)}
              className="text-xs bg-yellow-500 hover:bg-yellow-600 text-white px-2 py-1 rounded"
            >
              {t("admin:users.actions.password")}
            </button>
            <button
              onClick={() => onDelete(user)}
              className="text-xs bg-red-600 hover:bg-red-700 text-white px-2 py-1 rounded"
            >
              {t("admin:users.actions.delete")}
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
  const { t } = useTranslation(["admin", "common"]);
  if (configs.length === 0) {
    return <div className="text-gray-400 text-sm">{t("admin:configs.empty")}</div>;
  }
  return (
    <table className="w-full text-sm">
      <thead className="bg-gray-100 border-b">
        <tr>
          <th className="text-left px-3 py-1.5">{t("admin:configs.table.id")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:configs.table.name")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:configs.table.owner")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:configs.table.sprintsCount")}</th>
          <th className="text-right px-3 py-1.5">{t("common:actions")}</th>
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
                <span className="text-red-500 italic">{t("admin:configs.noOwner")}</span>
              )}
            </td>
            <td className="px-3 py-1.5">{c.sprints_count}</td>
            <td className="text-right px-3 py-1.5">
              <button
                onClick={() => onTransfer(c.id)}
                className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-2 py-1 rounded"
              >
                {t("admin:configs.transferButton")}
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
  const { t } = useTranslation(["admin", "common"]);
  if (sprints.length === 0) {
    return <div className="text-gray-400 text-sm">{t("admin:sprints.empty")}</div>;
  }
  return (
    <table className="w-full text-sm">
      <thead className="bg-gray-100 border-b">
        <tr>
          <th className="text-left px-3 py-1.5">{t("admin:sprints.table.id")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:sprints.table.num")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:sprints.table.status")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:sprints.table.config")}</th>
          <th className="text-left px-3 py-1.5">{t("admin:sprints.table.owner")}</th>
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
  const { t } = useTranslation(["admin", "common"]);
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
    <ModalShell title={t("admin:createUserModal.title")} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="text-sm text-gray-600 block mb-1">{t("admin:createUserModal.emailLabel")}</label>
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
          <label className="text-sm text-gray-600 block mb-1">{t("admin:createUserModal.nameLabel")}</label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="w-full px-2 py-1.5 border rounded"
          />
        </div>
        <div>
          <label className="text-sm text-gray-600 block mb-1">{t("admin:createUserModal.roleLabel")}</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full px-2 py-1.5 border rounded bg-white"
          >
            <option value="lead">{t("admin:createUserModal.roleOptions.lead")}</option>
            <option value="admin">{t("admin:createUserModal.roleOptions.admin")}</option>
          </select>
        </div>
        <div>
          <label className="text-sm text-gray-600 block mb-1">{t("admin:createUserModal.passwordLabel")}</label>
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
            {t("common:cancel")}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-sm font-semibold"
          >
            {busy ? t("admin:createUserModal.creating") : t("admin:createUserModal.create")}
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
  const { t } = useTranslation(["admin", "common"]);
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
    <ModalShell title={t("admin:resetPasswordModal.title", { email: user.email })} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-gray-600">
          {t("admin:resetPasswordModal.description")}
        </p>
        <input
          type="password"
          required
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          className="w-full px-2 py-1.5 border rounded"
          autoFocus
          placeholder={t("admin:resetPasswordModal.placeholder")}
        />
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-3 py-1.5 rounded text-sm"
          >
            {t("common:cancel")}
          </button>
          <button
            type="submit"
            disabled={busy}
            className="bg-yellow-500 hover:bg-yellow-600 text-white px-3 py-1.5 rounded text-sm font-semibold"
          >
            {busy ? t("admin:resetPasswordModal.saving") : t("admin:resetPasswordModal.change")}
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
  const { t } = useTranslation(["admin", "common"]);
  const [newOwnerId, setNewOwnerId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newOwnerId === null) return;
    const newOwner = leads.find((u) => u.id === newOwnerId);
    if (!newOwner) return;

    const ok = window.confirm(
      t("admin:transferConfigModal.confirmMessage", { name: config.name, email: newOwner.email })
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
    <ModalShell title={t("admin:transferConfigModal.title", { name: config.name })} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-gray-600">
          {t("admin:transferConfigModal.currentOwner")} <b>{config.owner_email || "—"}</b>
          <br/>
          {t("admin:transferConfigModal.sprintsInConfig")} <b>{config.sprints_count}</b>
        </p>
        <div>
          <label className="text-sm text-gray-600 block mb-1">{t("admin:transferConfigModal.newOwnerLabel")}</label>
          <select
            required
            value={newOwnerId ?? ""}
            onChange={(e) => setNewOwnerId(Number(e.target.value))}
            className="w-full px-2 py-1.5 border rounded bg-white"
          >
            <option value="">{t("admin:transferConfigModal.selectPlaceholder")}</option>
            {leads.map((u) => (
              <option key={u.id} value={u.id}>
                {u.email} {u.display_name && `(${u.display_name})`}
              </option>
            ))}
          </select>
          {leads.length === 0 && (
            <p className="text-xs text-orange-600 mt-1">
              {t("admin:transferConfigModal.noLeads")}
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
            {t("common:cancel")}
          </button>
          <button
            type="submit"
            disabled={busy || newOwnerId === null}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
          >
            {busy ? t("admin:transferConfigModal.transferring") : t("admin:transferConfigModal.transfer")}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function SalariesTab() {
  const { t } = useTranslation(["admin", "common"]);
  const toast = useToast();
  const [members, setMembers] = useState<AdminTeamMember[] | null>(null);
  const [salaries, setSalaries] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    adminGetAllSalaries()
      .then((ms) => {
        setMembers(ms);
        const init: Record<string, number> = {};
        ms.forEach((m) => { init[m.account_id] = m.salary; });
        setSalaries(init);
      })
      .catch((e) => toast.error(extractError(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateSalary = (accId: string, raw: string) => {
    const n = parseInt(raw.replace(/\D/g, ""), 10);
    setSalaries((prev) => ({ ...prev, [accId]: isNaN(n) ? 0 : n }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await adminUpdateAllSalaries(salaries);
      toast.success(t("admin:salaries.toast.saved"));
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="bg-white rounded-lg border p-4 shadow-sm">
      <h2 className="font-semibold text-gray-800 mb-1">{t("admin:salaries.title")}</h2>
      <p className="text-xs text-gray-500 mb-4">
        {t("admin:salaries.description")}
      </p>

      {loading ? (
        <div className="text-gray-400 text-sm py-4">{t("common:loading")}</div>
      ) : members === null ? null : members.length === 0 ? (
        <div className="text-gray-400 text-sm py-4">
          {t("admin:salaries.empty")}
        </div>
      ) : (
        <>
          <table className="w-full text-sm mb-4">
            <thead className="bg-gray-100 border-b">
              <tr>
                <th className="text-left px-3 py-1.5">{t("admin:salaries.table.jiraName")}</th>
                <th className="text-left px-3 py-1.5">{t("admin:salaries.table.fileName")}</th>
                <th className="text-left px-3 py-1.5 w-32">{t("admin:salaries.table.role")}</th>
                <th className="text-left px-3 py-1.5 w-44">{t("admin:salaries.table.salary")}</th>
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
              {saving ? t("admin:salaries.saving") : t("common:save")}
            </button>
          </div>
        </>
      )}
    </section>
  );
}