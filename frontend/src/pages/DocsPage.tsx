import { useState } from "react";

type Section = "concept" | "features";

export function DocsPage() {
  const [active, setActive] = useState<Section>("concept");

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Справка — Sprint Builder</h1>
        <p className="text-gray-500 text-sm">
          Инструмент управления разработкой продукта по методологии SDLC
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
          1. Концепция и логика процесса
        </button>
        <button
          onClick={() => setActive("features")}
          className={`px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition ${
            active === "features"
              ? "border-indigo-600 text-indigo-700"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          2. Функциональность и настройки
        </button>
      </div>

      {active === "concept" && <ConceptSection />}
      {active === "features" && <FeaturesSection />}
    </div>
  );
}

/* ─────────────────────────── РАЗДЕЛ 1: КОНЦЕПЦИЯ ─────────────────────────── */

function ConceptSection() {
  return (
    <div className="space-y-8">

      {/* Что это такое */}
      <DocCard accent="indigo">
        <DocCardTitle icon="🎯">Для чего нужен Sprint Builder</DocCardTitle>
        <p className="text-gray-600 leading-relaxed">
          Sprint Builder — инструмент менеджерского контроля над разработкой продукта. Он
          автоматически распределяет задачи из Jira по исполнителям, строит расписание этапов,
          прогнозирует дату завершения и считает стоимость работ.
        </p>
        <p className="text-gray-600 leading-relaxed mt-3">
          В основе лежит методология <strong>SDLC</strong> (Software Development Life Cycle) —
          каждая задача не «просто делается», а проходит по цепочке фаз: кто-то анализирует,
          кто-то рисует, кто-то разрабатывает, кто-то проверяет. Система знает, кто отвечает за
          каждую фазу, и строит реалистичное расписание с учётом загрузки команды, отпусков и
          зависимостей между задачами.
        </p>
      </DocCard>

      {/* Жизненный цикл задачи */}
      <DocCard accent="violet">
        <DocCardTitle icon="🔄">Жизненный цикл задачи (pipeline)</DocCardTitle>
        <p className="text-gray-600 leading-relaxed mb-5">
          Каждая задача проходит через последовательность этапов — <strong>pipeline</strong>.
          Набор этапов зависит от типа (направления) задачи, но общая логика одна:
        </p>
        <div className="flex flex-wrap items-center gap-2 mb-5">
          {[
            { label: "Анализ", color: "bg-amber-100 text-amber-800 border-amber-300", desc: "Аналитик" },
            { label: "→", color: "text-gray-400 font-bold text-lg", desc: "" },
            { label: "Дизайн", color: "bg-pink-100 text-pink-800 border-pink-300", desc: "Дизайнер" },
            { label: "→", color: "text-gray-400 font-bold text-lg", desc: "" },
            { label: "Разработка", color: "bg-emerald-100 text-emerald-800 border-emerald-300", desc: "Разработчик" },
            { label: "→", color: "text-gray-400 font-bold text-lg", desc: "" },
            { label: "Код-ревью", color: "bg-teal-100 text-teal-800 border-teal-300", desc: "Лид разработки" },
            { label: "→", color: "text-gray-400 font-bold text-lg", desc: "" },
            { label: "Тестирование", color: "bg-blue-100 text-blue-800 border-blue-300", desc: "Аналитик" },
          ].map((s, i) =>
            s.desc ? (
              <div key={i} className="flex flex-col items-center gap-1">
                <span className={`px-2.5 py-1 rounded-lg border text-xs font-semibold ${s.color}`}>
                  {s.label}
                </span>
                <span className="text-xs text-gray-400">{s.desc}</span>
              </div>
            ) : (
              <span key={i} className={s.color}>{s.label}</span>
            )
          )}
        </div>
        <p className="text-gray-600 leading-relaxed text-sm">
          Статусы в Jira автоматически маппируются на эти фазы через таблицу
          «Статус → Бакет» в настройках. Система знает, что задача в статусе
          «В разработке» — это фаза <em>Разработка</em>, а «К тестированию» — это
          <em>Тестирование</em>.
        </p>
      </DocCard>

      {/* Направления */}
      <DocCard accent="emerald">
        <DocCardTitle icon="🗂️">Направления разработки</DocCardTitle>
        <p className="text-gray-600 leading-relaxed mb-5">
          Разные типы задач требуют разных наборов этапов. Поэтому в системе настраиваются
          <strong> Направления</strong> — каждое определяет свой pipeline и ответственных.
          Принадлежность задачи к направлению определяется по{" "}
          <strong>меткам (labels) в Jira</strong>, поиск регистронезависимый.
        </p>
        <div className="space-y-3">
          {[
            {
              name: "Backend",
              labels: "backend, Backend",
              color: "border-emerald-400 bg-emerald-50",
              badge: "bg-emerald-100 text-emerald-800",
              pipeline: ["Анализ", "Разработка", "Код-ревью", "Тестирование"],
              who: "Аналитик → Разработчик backend → Лид разработки → Аналитик",
            },
            {
              name: "Frontend",
              labels: "frontend-web, frontend-mobile, Frontend",
              color: "border-blue-400 bg-blue-50",
              badge: "bg-blue-100 text-blue-800",
              pipeline: ["Анализ", "Разработка", "Код-ревью", "Тестирование"],
              who: "Аналитик → Разработчик frontend → Лид разработки → Аналитик",
            },
            {
              name: "Дизайн",
              labels: "design (метки не заданы — все задачи без меток)",
              color: "border-pink-400 bg-pink-50",
              badge: "bg-pink-100 text-pink-800",
              pipeline: ["Анализ", "Дизайн", "Дизайн-ревью"],
              who: "Аналитик → Дизайнер → Лид дизайна",
            },
          ].map((d) => (
            <div key={d.name} className={`rounded-xl border-l-4 p-4 ${d.color}`}>
              <div className="flex items-center gap-3 mb-2">
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${d.badge}`}>
                  {d.name}
                </span>
                <span className="text-xs text-gray-500">метки: {d.labels}</span>
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
          ))}
        </div>
      </DocCard>

      {/* Роли команды */}
      <DocCard accent="amber">
        <DocCardTitle icon="👥">Роли команды</DocCardTitle>
        <p className="text-gray-600 leading-relaxed mb-5">
          Каждый участник команды имеет <strong>роль</strong>, которая определяет какие этапы
          pipeline он выполняет. Роль задаётся в Настройках → Команда и используется при
          автоматическом назначении исполнителей.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-3 py-2 text-gray-600 font-semibold">Роль</th>
                <th className="text-left px-3 py-2 text-gray-600 font-semibold">Выполняет этапы</th>
                <th className="text-left px-3 py-2 text-gray-600 font-semibold">Приоритет выбора</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {[
                { role: "analyst", label: "Аналитик", phases: "Анализ, Тестирование", priority: "Assignee → Responsible → Reporter" },
                { role: "developer_backend", label: "Разработчик backend", phases: "Разработка", priority: "Поле «Разработчик» → Assignee" },
                { role: "developer_frontend", label: "Разработчик frontend", phases: "Разработка", priority: "Поле «Разработчик» → Assignee" },
                { role: "developer_lead", label: "Лид разработки", phases: "Разработка, Код-ревью", priority: "Поле «Разработчик» → Assignee" },
                { role: "designer", label: "Дизайнер", phases: "Дизайн", priority: "Assignee направления" },
                { role: "designer_lead", label: "Лид дизайна", phases: "Дизайн, Дизайн-ревью", priority: "Первый лид дизайна в команде" },
              ].map((r) => (
                <tr key={r.role} className="hover:bg-gray-50">
                  <td className="px-3 py-2">
                    <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{r.role}</code>
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
          <strong>Важно:</strong> если в задаче явно заполнено поле «Разработчик» (настраивается
          в разделе Настройки) — система всегда берёт именно его, независимо от роли. Это
          позволяет лиду делегировать задачу конкретному разработчику прямо в Jira.
        </div>
      </DocCard>

      {/* Исторический режим — концепция */}
      <DocCard accent="rose">
        <DocCardTitle icon="🕐">Режим «По истории статусов» — как это работает</DocCardTitle>
        <p className="text-gray-600 leading-relaxed mb-4">
          Стандартный прогноз строит только <em>будущее</em>: кто и когда доделает оставшиеся
          этапы. Но часто важно увидеть полную картину — что уже было сделано, кто реально
          работал над каждой фазой, и сколько это стоило.
        </p>
        <p className="text-gray-600 leading-relaxed mb-4">
          Режим «По истории статусов» читает <strong>полный changelog</strong> каждой задачи из
          Jira и восстанавливает реальные фазы:
        </p>
        <ol className="space-y-2 text-sm text-gray-600 mb-4">
          {[
            "Находит все переходы статусов и смены assignee по времени",
            "Для каждого сегмента определяет фазу по статусу и роли исполнителя: developer_lead в статусе «В разработке» → это фаза Разработка, а не Анализ",
            "Если внутри одной фазы assignee сменился — берётся последний (он реально довёл работу)",
            "Фазы с несовместимой ролью пропускаются: разработчик не может быть в Анализе",
            "Прошлые фазы выводятся на Гант-диаграмме приглушённо, красная линия разделяет факт и прогноз",
            "Считается раздельно: «Потрачено» (прошлое) и «Осталось» (будущее) в часах и деньгах",
          ].map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex-none w-5 h-5 rounded-full bg-rose-100 text-rose-700 text-xs font-bold flex items-center justify-center mt-0.5">
                {i + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
        <div className="p-3 bg-rose-50 rounded-lg border border-rose-200 text-sm text-rose-800">
          <strong>Примечание:</strong> режим делает дополнительные запросы к Jira API
          (по одному на каждую задачу эпика), поэтому может работать немного медленнее обычного.
        </div>
      </DocCard>

    </div>
  );
}

/* ──────────────────────── РАЗДЕЛ 2: ФУНКЦИОНАЛЬНОСТЬ ─────────────────────── */

function FeaturesSection() {
  const [open, setOpen] = useState<string | null>("sprint");
  const toggle = (id: string) => setOpen((prev) => (prev === id ? null : id));

  const items: Array<{
    id: string;
    icon: string;
    title: string;
    content: React.ReactNode;
  }> = [
    {
      id: "sprint",
      icon: "📋",
      title: "Формирование спринта",
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            Страница <strong>Спринт</strong> — основной рабочий инструмент. Система запрашивает
            актуальные задачи из Jira и автоматически распределяет их по исполнителям с учётом
            бюджета часов.
          </p>
          <FeatureList items={[
            "Задачи берутся из настроенных Jira-досок для текущего конфига",
            "Каждому участнику выделяется бюджет часов (настраивается в «Часов на человека»)",
            "Лиды дополнительно получают часы на управленческие активности",
            "Задачи, не влезшие в бюджет, попадают в «Переполнение» с указанием причины",
            "Псевдо-задачи (встречи, онбординг) добавляются автоматически и учитываются в бюджете",
            "Черновик спринта можно сохранить и утвердить — после утверждения запись фиксируется",
          ]} />
          <FeatureTip>
            После утверждения спринта активируется кнопка «Стендап» — она показывает актуальное
            расписание задач на текущий день с учётом реального статуса в Jira.
          </FeatureTip>
        </div>
      ),
    },
    {
      id: "forecast",
      icon: "📈",
      title: "Прогноз реализации (Гант)",
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            Страница <strong>Прогноз реализации</strong> строит полное расписание всех оставшихся
            этапов для эпика или задачи и предсказывает дату завершения.
          </p>
          <FeatureList items={[
            "Введите ключ эпика (SHN-1947) или обычной задачи — система найдёт все дочерние",
            "Каждая задача расписывается по pipeline её направления с реальными исполнителями",
            "Гант-диаграмма: по строкам — исполнители, по оси X — рабочие дни",
            "Масштаб диаграммы регулируется кнопками «−» / «+»",
            "Клик по бару — показывает все этапы задачи; двойной клик — открывает Jira",
            "Стоимость считается по формуле: оклад ÷ 160 ч/мес × плановые часы",
            "Недавние эпики сохраняются — можно быстро переключиться",
          ]} />
          <h4 className="font-semibold text-gray-700 mt-4">Зависимости (FS)</h4>
          <p>
            Кнопка <strong>«Зависимости»</strong> позволяет задать порядок выполнения задач:
            задача B не начнётся, пока не закончится задача A (Finish-Start). Зависимости
            сохраняются и учитываются при каждом пересчёте прогноза.
          </p>
          <h4 className="font-semibold text-gray-700 mt-2">Отпуска</h4>
          <p>
            Кнопка <strong>«Отпуска»</strong> позволяет указать периоды отсутствия сотрудников.
            В эти дни система не планирует работу — задачи автоматически сдвигаются.
          </p>
          <h4 className="font-semibold text-gray-700 mt-2">Без оценок</h4>
          <p>
            Если задача не имеет оценки в Jira, система использует дефолтное значение (настраивается).
            Оранжевый индикатор показывает количество таких задач — по клику открывается редактор
            оценок прямо в интерфейсе без перехода в Jira.
          </p>
          <h4 className="font-semibold text-gray-700 mt-2">ROI</h4>
          <p>
            Кнопка <strong>«Посчитать ROI»</strong> рассчитывает окупаемость:
            вводите ожидаемый доход от проекта — система покажет прибыль и ROI в %.
          </p>
        </div>
      ),
    },
    {
      id: "history-mode",
      icon: "🕐",
      title: "Режим «По истории статусов»",
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            Переключатель <strong>«По истории статусов»</strong> на странице Прогноза включает
            расширенный режим: к будущему прогнозу добавляется реконструкция прошлого.
          </p>
          <FeatureList items={[
            "На Ганте показывается вся история: от самой ранней фазы до сегодня (приглушённые бары) и прогноз (яркие бары)",
            "Красная пунктирная линия «сегодня» разделяет факт и прогноз",
            "Владелец исторической фазы — тот, кто был назначен в Jira на момент перехода статуса",
            "Если исполнитель несовместим с типом работы (разработчик в анализе) — фаза пропускается",
            "Если assignee сменился внутри фазы — берётся последний (он и довёл до конца)",
            "Под метриками появляется строка «Потрачено / Осталось» в часах и рублях",
          ]} />
          <FeatureTip>
            Стоимость исторических фаз считается по плановым часам из Jira (не по реально
            затраченному времени), что даёт корректное сравнение план/факт.
          </FeatureTip>
        </div>
      ),
    },
    {
      id: "snapshots",
      icon: "📊",
      title: "Тренд завершения (снапшоты)",
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            Каждый раз при построении прогноза система автоматически сохраняет
            <strong> снапшот</strong> — фиксирует предиктную дату завершения на сегодня.
            Из этих точек строится <strong>график тренда</strong> — видно, сдвигается ли
            дата завершения или остаётся стабильной.
          </p>
          <FeatureList items={[
            "График отображается под Гант-диаграммой автоматически при накоплении данных",
            "Снапшоты можно закреплять (📌) — они не исчезают при очистке старых",
            "Незакреплённые снапшоты хранятся по одному на каждый день",
            "Тренд вверх (дата откладывается) — сигнал о проблемах с прогрессом",
          ]} />
        </div>
      ),
    },
    {
      id: "history-page",
      icon: "📜",
      title: "История спринтов",
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            Страница <strong>История</strong> показывает все сохранённые спринты с возможностью
            просмотра состава и статуса задач.
          </p>
          <FeatureList items={[
            "Фильтрация по статусу: Черновик / Утверждён / Закрыт",
            "Просмотр полного состава задач каждого спринта",
            "Для закрытых спринтов — финальный статус каждой задачи из Jira",
            "Возможность закрыть спринт вручную с фиксацией фактических статусов",
          ]} />
        </div>
      ),
    },
    {
      id: "settings",
      icon: "⚙️",
      title: "Настройки конфига",
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            В системе может быть несколько конфигураций (переключатель в шапке). Каждая конфигурация
            — это отдельный набор настроек для команды или проекта.
          </p>
          <div className="space-y-4">
            {[
              {
                title: "Основные параметры",
                items: [
                  "Ключ проекта Jira — фильтрует задачи по проекту",
                  "Поле спринта (Sprint field) — кастомное поле Jira для привязки к спринту",
                  "Поле разработчика — кастомное поле, в котором указывается ответственный разработчик",
                  "Часов на человека — рабочий бюджет одного участника в спринте",
                  "Дефолтные часы задачи — используются если оценка не заполнена",
                  "Часы руководителя — дополнительное время для лидов на управление",
                ],
              },
              {
                title: "Команда",
                items: [
                  "Список участников: Jira-логин, имя в системе, роль, оклад",
                  "Оклад используется для расчёта стоимости: оклад ÷ 160 ч/мес × часы",
                  "Один человек может быть в нескольких конфигах с разными окладами",
                ],
              },
              {
                title: "Роли",
                items: [
                  "Включение/выключение ролей — отключённые роли не участвуют в планировании",
                  "Роль «Лид» получает дополнительные часы на управление",
                  "Порядок ролей определяет приоритет при автовыборе исполнителя",
                ],
              },
              {
                title: "Маппинг статусов → Бакеты",
                items: [
                  "Задаёт соответствие: статус Jira + роль → этап (бакет)",
                  "Например: «В разработке» + analyst → Тестирование (аналитик контролирует разработку)",
                  "Один статус может иметь разные бакеты для разных ролей",
                ],
              },
              {
                title: "Направления",
                items: [
                  "Название, метки Jira (labels) — по ним задачи привязываются к направлению",
                  "Pipeline (work_types): последовательность этапов для этого направления",
                  "Роли для Разработки, Тестирования, Дизайна — позволяют использовать разные роли в разных направлениях",
                  "Поиск по меткам регистронезависимый: «backend» и «Backend» — одно и то же",
                ],
              },
              {
                title: "Псевдо-задачи",
                items: [
                  "Фиксированные задачи сотрудника (встречи, дежурства, обучение)",
                  "Автоматически добавляются в каждый спринт и учитываются в бюджете часов",
                  "Можно привязать к конкретному номеру спринта или делать повторяющимися",
                ],
              },
            ].map((block) => (
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
      id: "standup",
      icon: "🎙️",
      title: "Стендап",
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            Режим <strong>Стендап</strong> доступен через историю утверждённых спринтов.
            Показывает задачи каждого участника на текущий день с учётом реального статуса в Jira.
          </p>
          <FeatureList items={[
            "Подсвечивает просроченные задачи — те, что должны были завершиться раньше",
            "Показывает плановые часы и период работы по каждой задаче",
            "Одним кликом можно отправить статус задачи в Jira (переключить статус)",
            "Фильтрация по конкретному исполнителю",
          ]} />
        </div>
      ),
    },
    {
      id: "configs",
      icon: "🔀",
      title: "Несколько конфигураций",
      content: (
        <div className="space-y-3 text-sm text-gray-600">
          <p>
            Переключатель конфигурации в правом верхнем углу шапки позволяет работать с
            несколькими проектами или командами из одного интерфейса.
          </p>
          <FeatureList items={[
            "Каждый конфиг — отдельная команда, бюджеты, направления, маппинги статусов",
            "Переключение мгновенное — все страницы обновляются автоматически",
            "Оклады участников синхронизируются между конфигами: если в конфиге A оклад выше — он используется везде",
            "Один человек (по accountId Jira) может быть в нескольких конфигах с разными ролями",
            "Создать новый конфиг или удалить существующий — в разделе Настройки",
          ]} />
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
