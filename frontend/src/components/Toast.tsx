/**
 * Единая система тост-уведомлений (без внешних зависимостей).
 *
 * Использование:
 *   const toast = useToast();
 *   toast.success("Прогноз построен");
 *   toast.error("Не удалось загрузить данные");
 *
 * Провайдер монтируется один раз в main.tsx и оборачивает всё приложение.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import type { ReactNode } from "react";

type ToastKind = "success" | "error" | "info";

type Toast = {
  id: number;
  kind: ToastKind;
  message: string;
};

type ToastApi = {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

/** Доступ к тостам из любого компонента под провайдером. */
// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

const AUTO_DISMISS_MS = 4500;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((kind: ToastKind, message: string) => {
    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, kind, message }]);
  }, []);

  const api = useMemo<ToastApi>(() => ({
    success: (m) => push("success", m),
    error: (m) => push("error", m),
    info: (m) => push("info", m),
  }), [push]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)] pointer-events-none">
        {toasts.map((t) => (
          <ToastCard key={t.id} toast={t} onClose={() => remove(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

const STYLES: Record<ToastKind, { bar: string; icon: ReactNode; ring: string }> = {
  success: {
    bar: "bg-green-500",
    ring: "border-green-200",
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-green-500">
        <path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.1 3.1 6.8-6.8a1 1 0 011.4 0z" clipRule="evenodd" />
      </svg>
    ),
  },
  error: {
    bar: "bg-red-500",
    ring: "border-red-200",
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-red-500">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.7 7.3a1 1 0 00-1.4 1.4L8.6 10l-1.3 1.3a1 1 0 101.4 1.4L10 11.4l1.3 1.3a1 1 0 001.4-1.4L11.4 10l1.3-1.3a1 1 0 00-1.4-1.4L10 8.6 8.7 7.3z" clipRule="evenodd" />
      </svg>
    ),
  },
  info: {
    bar: "bg-indigo-500",
    ring: "border-indigo-200",
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 text-indigo-500">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM11 9a1 1 0 10-2 0v4a1 1 0 102 0V9zm-1-5a1.2 1.2 0 100 2.4A1.2 1.2 0 0010 4z" clipRule="evenodd" />
      </svg>
    ),
  },
};

function ToastCard({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  const [shown, setShown] = useState(false);
  const s = STYLES[toast.kind];

  // Плавный уход: сворачиваем, затем удаляем из списка.
  const dismiss = useCallback(() => {
    setShown(false);
    setTimeout(onClose, 200);
  }, [onClose]);

  useEffect(() => {
    // Запускаем появление на следующем кадре, чтобы сработал transition.
    const raf = requestAnimationFrame(() => setShown(true));
    const timer = setTimeout(dismiss, AUTO_DISMISS_MS);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [dismiss]);

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 bg-white rounded-xl border ${s.ring}
                  shadow-lg overflow-hidden pl-0 pr-3 py-3
                  transition-all duration-200 ease-out
                  ${shown ? "opacity-100 translate-x-0" : "opacity-0 translate-x-6"}`}
    >
      <div className={`w-1 self-stretch ${s.bar}`} />
      <div className="pt-0.5">{s.icon}</div>
      <div className="flex-1 text-sm text-gray-700 leading-snug break-words">{toast.message}</div>
      <button
        onClick={dismiss}
        className="text-gray-300 hover:text-gray-500 transition shrink-0 -mr-1"
        aria-label="Закрыть"
      >
        <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
          <path d="M6.3 6.3a1 1 0 011.4 0L10 8.6l2.3-2.3a1 1 0 111.4 1.4L11.4 10l2.3 2.3a1 1 0 01-1.4 1.4L10 11.4l-2.3 2.3a1 1 0 01-1.4-1.4L8.6 10 6.3 7.7a1 1 0 010-1.4z" />
        </svg>
      </button>
    </div>
  );
}
