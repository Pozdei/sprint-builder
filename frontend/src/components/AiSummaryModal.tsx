import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { extractError } from "../lib/api-error";
import { useToast } from "./Toast";

interface Props {
  generate: () => Promise<string>;
  onClose: () => void;
}

export function AiSummaryModal({ generate, onClose }: Props) {
  const { t } = useTranslation(["common"]);
  const toast = useToast();
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    generate()
      .then(setSummary)
      .catch((e) => setError(extractError(e)))
      .finally(() => setLoading(false));
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(load, []);

  const handleCopy = async () => {
    if (!summary) return;
    try {
      await navigator.clipboard.writeText(summary);
      toast.success(t("aiSummary.toast.copied"));
    } catch {
      toast.error(t("aiSummary.toast.copyFailed"));
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-bold text-gray-900 text-lg">{t("aiSummary.title")}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="text-center text-gray-400 py-10">
              {t("aiSummary.generating")}
            </div>
          )}
          {!loading && error && (
            <div className="text-center py-10">
              <div className="text-red-600 text-sm mb-3">{error}</div>
              <button
                onClick={load}
                className="border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-semibold px-4 py-2 rounded-lg transition"
              >
                {t("aiSummary.retry")}
              </button>
            </div>
          )}
          {!loading && !error && summary && (
            <div className="w-full border rounded-lg px-3 py-2.5 text-sm leading-relaxed bg-gray-50 whitespace-pre-wrap">
              {summary}
            </div>
          )}
        </div>

        <div className="border-t px-6 py-3 flex items-center justify-between bg-gray-50 rounded-b-2xl">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700">
            {t("close")}
          </button>
          <button
            onClick={handleCopy}
            disabled={!summary}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-semibold"
          >
            {t("aiSummary.copy")}
          </button>
        </div>
      </div>
    </div>
  );
}
