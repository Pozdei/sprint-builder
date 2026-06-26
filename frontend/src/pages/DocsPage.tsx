import { useState } from "react";
import { useTranslation } from "react-i18next";

type Section = "concept" | "features";

export function DocsPage() {
  const { t } = useTranslation("docs");
  const [active, setActive] = useState<Section>("concept");

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t("title")}</h1>
        <p className="text-gray-500 text-sm">
          {t("subtitle")}
        </p>
      </div>

      {/* Переключатель разделов */}
      <div className="flex gap-2 mb-8 border-b">
        <button
          onClick={() => setActive("concept")}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition ${
            active === "concept"
              ? "border-indigo-600 text-indigo-700"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {t("tabs.concept")}
        </button>
        <button
          onClick={() => setActive("features")}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition ${
            active === "features"
              ? "border-indigo-600 text-indigo-700"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          {t("tabs.features")}
        </button>
      </div>

      {active === "concept" && <ConceptSection />}
      {active === "features" && <FeaturesSection />}
    </div>
  );
}

/* ─────────────────────────── РАЗДЕЛ 1: КОНЦЕПЦИЯ ─────────────────────────── */

function ConceptSection() {
  const { t } = useTranslation("docs");

  const pipelineStages = t("concept.pipeline.stages", { returnObjects: true }) as Array<{
    label: string;
    desc: string;
  }>;
  const pipelineColors = [
    "bg-amber-100 text-amber-800 border-amber-300",
    "bg-pink-100 text-pink-800 border-pink-300",
    "bg-emerald-100 text-emerald-800 border-emerald-300",
    "bg-teal-100 text-teal-800 border-teal-300",
    "bg-blue-100 text-blue-800 border-blue-300",
    "bg-yellow-100 text-yellow-800 border-yellow-300",
  ];

  const directionItems = t("concept.directions.items", { returnObjects: true }) as Array<{
    name: string;
    labels: string;
    pipeline: string[];
    who: string;
  }>;
  const directionStyles = [
    { color: "border-emerald-400 bg-emerald-50", badge: "bg-emerald-100 text-emerald-800" },
    { color: "border-blue-400 bg-blue-50", badge: "bg-blue-100 text-blue-800" },
    { color: "border-pink-400 bg-pink-50", badge: "bg-pink-100 text-pink-800" },
  ];

  const roleRows = t("concept.roles.rows", { returnObjects: true }) as Array<{
    code: string;
    label: string;
    phases: string;
    priority: string;
  }>;

  const historySteps = t("concept.historyMode.steps", { returnObjects: true }) as string[];

  return (
    <div className="space-y-8">

      {/* Что это такое */}
      <DocCard accent="indigo">
        <DocCardTitle icon="🎯">{t("concept.purpose.title")}</DocCardTitle>
        <p className="text-gray-600 leading-relaxed">
          {t("concept.purpose.p1")}
        </p>
        <p className="text-gray-600 leading-relaxed mt-3">
          {t("concept.purpose.p2Before")} <strong>{t("concept.purpose.p2Sdlc")}</strong>{" "}
          {t("concept.purpose.p2Middle")}
        </p>
      </DocCard>

      {/* Жизненный цикл задачи */}
      <DocCard accent="violet">
        <DocCardTitle icon="🔄">{t("concept.pipeline.title")}</DocCardTitle>
        <p className="text-gray-600 leading-relaxed mb-5">
          {t("concept.pipeline.introBefore")} <strong>{t("concept.pipeline.introBold")}</strong>
          {t("concept.pipeline.introAfter")}
        </p>
        <div className="flex items-start mb-5">
          {pipelineStages.map((s, i) => (
            <div key={i} className="flex items-center flex-1 min-w-0">
              {i > 0 && <span className="text-gray-300 font-bold text-lg flex-none w-5 text-center">→</span>}
              <div className="flex-1 min-w-0 flex flex-col items-center gap-1 text-center">
                <span className={`whitespace-nowrap px-2 py-1 rounded-lg border text-xs font-semibold ${pipelineColors[i]}`}>
                  {s.label}
                </span>
                <span className="text-xs text-gray-400 leading-tight">{s.desc}</span>
              </div>
            </div>
          ))}
        </div>
        <p className="text-gray-600 leading-relaxed text-sm">
          {t("concept.pipeline.statusMappingBefore")}{" "}
          <em>{t("concept.pipeline.statusMappingDevelopment")}</em>
          {t("concept.pipeline.statusMappingMiddle")}{" "}
          <em>{t("concept.pipeline.statusMappingTesting")}</em>
          {t("concept.pipeline.statusMappingEnd")}
        </p>
        <p className="text-gray-600 leading-relaxed text-sm mt-2">
          {t("concept.pipeline.releaseBefore")} <strong>{t("concept.pipeline.releaseBold")}</strong>{" "}
          {t("concept.pipeline.releaseAfter")}
        </p>
        <p className="text-gray-600 leading-relaxed text-sm mt-2">
          {t("concept.pipeline.badgeBefore")} <strong>{t("concept.pipeline.badgeBold")}</strong>
          {t("concept.pipeline.badgeAfter")}
        </p>
      </DocCard>

      {/* Направления */}
      <DocCard accent="emerald">
        <DocCardTitle icon="🗂️">{t("concept.directions.title")}</DocCardTitle>
        <p className="text-gray-600 leading-relaxed mb-5">
          {t("concept.directions.introBefore")}
          <strong> {t("concept.directions.introBold")}</strong> {t("concept.directions.introAfter")}{" "}
          <strong>{t("concept.directions.introLabelsBold")}</strong>
          {t("concept.directions.introEnd")}
        </p>
        <div className="space-y-3">
          {directionItems.map((d, idx) => {
            const style = directionStyles[idx];
            return (
              <div key={d.name} className={`rounded-xl border-l-4 p-4 ${style.color}`}>
                <div className="flex items-center gap-3 mb-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${style.badge}`}>
                    {d.name}
                  </span>
                  <span className="text-xs text-gray-500">{t("concept.directions.labelsPrefix")} {d.labels}</span>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
                  {d.pipeline.map((step, i) => (
                    <span key={i} className="flex items-center gap-1.5">
                      <span className="text-xs bg-white border rounded px-2 py-0.5 font-medium text-gray-700">
                        {step}
                      </span>
                      {i < d.pipeline.length - 1 && (
                        <span className="text-gray-400 text-xs">→</span>
                      )}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-gray-500">{d.who}</p>
              </div>
            );
          })}
        </div>
      </DocCard>

      {/* Роли команды */}
      <DocCard accent="amber">
        <DocCardTitle icon="👥">{t("concept.roles.title")}</DocCardTitle>
        <p className="text-gray-600 leading-relaxed mb-5">
          {t("concept.roles.introBefore")} <strong>{t("concept.roles.introBold")}</strong>
          {t("concept.roles.introAfter")}
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-3 py-2 text-gray-600 font-semibold">{t("concept.roles.table.role")}</th>
                <th className="text-left px-3 py-2 text-gray-600 font-semibold">{t("concept.roles.table.phases")}</th>
                <th className="text-left px-3 py-2 text-gray-600 font-semibold">{t("concept.roles.table.priority")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {roleRows.map((r) => (
                <tr key={r.code} className="hover:bg-gray-50">
                  <td className="px-3 py-2">
                    <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{r.code}</code>
                    <span className="ml-2 text-gray-600">{r.label}</span>
                  </td>
                  <td className="px-3 py-2 text-gray-600">{r.phases}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{r.priority}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 p-3 bg-amber-50 rounded-lg border border-amber-200 text-sm text-amber-800">
          <strong>{t("concept.roles.noteBold")}</strong> {t("concept.roles.noteText")}
        </div>
      </DocCard>

      {/* Исторический режим — концепция */}
      <DocCard accent="rose">
        <DocCardTitle icon="🕐">{t("concept.historyMode.title")}</DocCardTitle>
        <p className="text-gray-600 leading-relaxed mb-4">
          {t("concept.historyMode.p1")}
        </p>
        <p className="text-gray-600 leading-relaxed mb-4">
          {t("concept.historyMode.p2Before")} <strong>{t("concept.historyMode.p2Bold")}</strong>{" "}
          {t("concept.historyMode.p2After")}
        </p>
        <ol className="space-y-2 text-sm text-gray-600 mb-4">
          {historySteps.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex-none w-5 h-5 rounded-full bg-rose-100 text-rose-700 text-xs font-bold flex items-center justify-center mt-0.5">
                {i + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
        <div className="p-3 bg-rose-50 rounded-lg border border-rose-200 text-sm text-rose-800">
          <strong>{t("concept.historyMode.noteBold")}</strong> {t("concept.historyMode.noteText")}
        </div>
      </DocCard>

    </div>
  );
}

/* ──────────────────────── РАЗДЕЛ 2: ФУНКЦИОНАЛЬНОСТЬ ─────────────────────── */

function FeaturesSection() {
  const { t } = useTranslation("docs");
  const [open, setOpen] = useState<string | null>("sprint");
  const toggle = (id: string) => setOpen((prev) => (prev === id ? null : id));

  const settingsBlocks = t("features.settings.blocks", { returnObjects: true }) as Array<{
    title: string;
    items: string[];
  }>;

  const jiraApiRows = t("features.jiraApi.rows", { returnObjects: true }) as Array<{
    method: string;
    path: string;
    desc: string;
  }>;

  const items: Array<{
    id: string;
    icon: string;
    title: string;
    content: React.ReactNode;
  }> = [
    {
      id: "sprint",
      icon: "📋",
      title: t("features.sprint.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.sprint.p1Before")} <strong>{t("features.sprint.p1Bold")}</strong>{" "}
            {t("features.sprint.p1After")}
          </p>
          <FeatureList items={t("features.sprint.list", { returnObjects: true }) as string[]} />
          <FeatureTip>
            {t("features.sprint.tip")}
          </FeatureTip>
        </div>
      ),
    },
    {
      id: "today-export",
      icon: "📤",
      title: t("features.todayExport.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.todayExport.p1Before")} <strong>{t("features.todayExport.p1Bold")}</strong>{" "}
            {t("features.todayExport.p1After")}
          </p>
          <FeatureList items={t("features.todayExport.list", { returnObjects: true }) as string[]} />
        </div>
      ),
    },
    {
      id: "telegram",
      icon: "🤖",
      title: t("features.telegram.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.telegram.p1Before")} <strong>{t("features.telegram.p1Bold")}</strong>{" "}
            {t("features.telegram.p1After")}
          </p>
          <FeatureList items={t("features.telegram.list", { returnObjects: true }) as string[]} />
          <h4 className="font-semibold text-gray-700 mt-4">{t("features.telegram.botHeading")}</h4>
          <ol className="space-y-1.5 text-sm text-gray-600 list-decimal pl-5">
            {(t("features.telegram.botSteps", { returnObjects: true }) as string[]).map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
          <h4 className="font-semibold text-gray-700 mt-4">{t("features.telegram.setupHeading")}</h4>
          <FeatureList items={t("features.telegram.setupList", { returnObjects: true }) as string[]} />
          <FeatureTip>
            {t("features.telegram.tip")}
          </FeatureTip>
        </div>
      ),
    },
    {
      id: "forecast",
      icon: "📈",
      title: t("features.forecast.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.forecast.p1Before")} <strong>{t("features.forecast.p1Bold")}</strong>{" "}
            {t("features.forecast.p1After")}
          </p>
          <FeatureList items={t("features.forecast.list", { returnObjects: true }) as string[]} />
          <h4 className="font-semibold text-gray-700 mt-4">{t("features.forecast.rollupHeading")}</h4>
          <p>
            {t("features.forecast.rollupP1")}
          </p>
          <FeatureList items={t("features.forecast.rollupList", { returnObjects: true }) as string[]} />
          <h4 className="font-semibold text-gray-700 mt-4">{t("features.forecast.depsHeading")}</h4>
          <p>
            {t("features.forecast.depsP1Before")} <strong>{t("features.forecast.depsP1Bold")}</strong>{" "}
            {t("features.forecast.depsP1After")}
          </p>
          <FeatureList items={t("features.forecast.depsList", { returnObjects: true }) as string[]} />
          <h4 className="font-semibold text-gray-700 mt-2">{t("features.forecast.vacationsHeading")}</h4>
          <p>
            {t("features.forecast.vacationsP1Before")} <strong>{t("features.forecast.vacationsP1Bold")}</strong>{" "}
            {t("features.forecast.vacationsP1After")}
          </p>
          <h4 className="font-semibold text-gray-700 mt-2">{t("features.forecast.missingEstimatesHeading")}</h4>
          <p>
            {t("features.forecast.missingEstimatesP1")}
          </p>
          <h4 className="font-semibold text-gray-700 mt-2">{t("features.forecast.roiHeading")}</h4>
          <p>
            {t("features.forecast.roiP1Before")} <strong>{t("features.forecast.roiP1Bold")}</strong>{" "}
            {t("features.forecast.roiP1After")}
          </p>
        </div>
      ),
    },
    {
      id: "root-tasks",
      icon: "📌",
      title: t("features.rootTasks.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.rootTasks.p1Before")} <em>{t("features.rootTasks.p1Em")}</em>{" "}
            {t("features.rootTasks.p1Middle")}
            <strong> {t("features.rootTasks.p1Bold")}</strong>: {t("features.rootTasks.p1After")}
          </p>
          <FeatureList items={t("features.rootTasks.list", { returnObjects: true }) as string[]} />
        </div>
      ),
    },
    {
      id: "missing-assignees",
      icon: "🚩",
      title: t("features.missingAssignees.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.missingAssignees.p1Before")} <strong>{t("features.missingAssignees.p1Bold")}</strong>{" "}
            {t("features.missingAssignees.p1After")}
          </p>
          <FeatureList items={t("features.missingAssignees.list", { returnObjects: true }) as string[]} />
        </div>
      ),
    },
    {
      id: "history-mode",
      icon: "🕐",
      title: t("features.historyMode.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.historyMode.p1Before")} <strong>{t("features.historyMode.p1Bold")}</strong>{" "}
            {t("features.historyMode.p1After")}
          </p>
          <FeatureList items={t("features.historyMode.list", { returnObjects: true }) as string[]} />
          <FeatureTip>
            {t("features.historyMode.tip")}
          </FeatureTip>
        </div>
      ),
    },
    {
      id: "snapshots",
      icon: "📊",
      title: t("features.snapshots.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.snapshots.p1Before")}
            <strong> {t("features.snapshots.p1Bold1")}</strong> {t("features.snapshots.p1Middle")}{" "}
            <strong>{t("features.snapshots.p1Bold2")}</strong> {t("features.snapshots.p1After")}
          </p>
          <FeatureList items={t("features.snapshots.list", { returnObjects: true }) as string[]} />
        </div>
      ),
    },
    {
      id: "history-page",
      icon: "📜",
      title: t("features.historyPage.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.historyPage.p1Before")} <strong>{t("features.historyPage.p1Bold")}</strong>{" "}
            {t("features.historyPage.p1After")}
          </p>
          <FeatureList items={t("features.historyPage.list", { returnObjects: true }) as string[]} />
          <h4 className="font-semibold text-gray-700 mt-4">{t("features.historyPage.snapshotsHeading")}</h4>
          <p>
            {t("features.historyPage.snapshotsP1Before")} <strong>{t("features.historyPage.snapshotsP1Bold")}</strong>
            {" "}{t("features.historyPage.snapshotsP1After")}
          </p>
          <FeatureList items={t("features.historyPage.snapshotsList", { returnObjects: true }) as string[]} />
        </div>
      ),
    },
    {
      id: "settings",
      icon: "⚙️",
      title: t("features.settings.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.settings.p1")}
          </p>
          <div className="space-y-4">
            {settingsBlocks.map((block) => (
              <div key={block.title}>
                <h4 className="font-semibold text-gray-700 mb-1.5">{block.title}</h4>
                <FeatureList items={block.items} />
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      id: "designer-tester-fields",
      icon: "🧩",
      title: t("features.designerTesterFields.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.designerTesterFields.p1")}
          </p>
          <h4 className="font-semibold text-gray-700 mt-2">{t("features.designerTesterFields.designerHeading")}</h4>
          <ol className="space-y-1.5 text-sm text-gray-600 list-decimal pl-5">
            {(t("features.designerTesterFields.designerSteps", { returnObjects: true }) as string[]).map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
          <h4 className="font-semibold text-gray-700 mt-2">{t("features.designerTesterFields.testerHeading")}</h4>
          <ol className="space-y-1.5 text-sm text-gray-600 list-decimal pl-5">
            {(t("features.designerTesterFields.testerSteps", { returnObjects: true }) as string[]).map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
          <FeatureList items={t("features.designerTesterFields.list", { returnObjects: true }) as string[]} />
        </div>
      ),
    },
    {
      id: "standup",
      icon: "🎙️",
      title: t("features.standup.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.standup.p1Before")} <strong>{t("features.standup.p1Bold")}</strong>{" "}
            {t("features.standup.p1After")}
          </p>
          <FeatureList items={t("features.standup.list", { returnObjects: true }) as string[]} />
        </div>
      ),
    },
    {
      id: "configs",
      icon: "🔀",
      title: t("features.configs.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.configs.p1")}
          </p>
          <FeatureList items={t("features.configs.list", { returnObjects: true }) as string[]} />
        </div>
      ),
    },
    {
      id: "jira-api",
      icon: "🔌",
      title: t("features.jiraApi.title"),
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            {t("features.jiraApi.p1")}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left px-3 py-2 text-gray-600 font-semibold">{t("features.jiraApi.table.method")}</th>
                  <th className="text-left px-3 py-2 text-gray-600 font-semibold">{t("features.jiraApi.table.endpoint")}</th>
                  <th className="text-left px-3 py-2 text-gray-600 font-semibold">{t("features.jiraApi.table.description")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {jiraApiRows.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50 align-top">
                    <td className="px-3 py-2">
                      <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                        r.method === "GET" ? "bg-blue-100 text-blue-800"
                          : r.method === "PUT" ? "bg-amber-100 text-amber-800"
                          : "bg-emerald-100 text-emerald-800"
                      }`}>
                        {r.method}
                      </span>
                    </td>
                    <td className="px-3 py-2"><code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{r.path}</code></td>
                    <td className="px-3 py-2 text-gray-600">{r.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <FeatureTip>
            {t("features.jiraApi.tipBefore")} <code>{t("features.jiraApi.tipPutCode")}</code>{" "}
            {t("features.jiraApi.tipMiddle")}
            <code> {t("features.jiraApi.tipPostCode")}</code> {t("features.jiraApi.tipAfter")}
          </FeatureTip>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.id} className="bg-white border rounded-xl overflow-hidden shadow-sm">
          <button
            onClick={() => toggle(item.id)}
            className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition"
          >
            <div className="flex items-center gap-3">
              <span className="text-xl">{item.icon}</span>
              <span className="font-semibold text-gray-800">{item.title}</span>
            </div>
            <span className={`text-gray-400 transition-transform ${open === item.id ? "rotate-180" : ""}`}>
              ▾
            </span>
          </button>
          {open === item.id && (
            <div className="px-5 pb-5 border-t bg-gray-50">
              <div className="pt-4">{item.content}</div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ─────────────────────────── Вспомогательные компоненты ─────────────────────────── */

function DocCard({
  children, accent,
}: {
  children: React.ReactNode;
  accent: "indigo" | "violet" | "emerald" | "amber" | "rose";
}) {
  const border = {
    indigo: "border-indigo-200 bg-indigo-50/30",
    violet: "border-violet-200 bg-violet-50/30",
    emerald: "border-emerald-200 bg-emerald-50/30",
    amber: "border-amber-200 bg-amber-50/30",
    rose: "border-rose-200 bg-rose-50/30",
  }[accent];
  return (
    <div className={`rounded-2xl border p-6 ${border}`}>
      {children}
    </div>
  );
}

function DocCardTitle({ icon, children }: { icon: string; children: React.ReactNode }) {
  return (
    <h2 className="flex items-center gap-2 text-lg font-bold text-gray-900 mb-4">
      <span className="text-2xl">{icon}</span>
      {children}
    </h2>
  );
}

function FeatureList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2">
          <span className="flex-none text-indigo-400 mt-0.5">•</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function FeatureTip({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-2 p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-sm text-indigo-800">
      <span className="flex-none">💡</span>
      <span>{children}</span>
    </div>
  );
}
