"""Единый источник правды по этапам конвейера (bucket'ам).

`bucket` — отображаемое русское имя этапа («Анализ», «Разработка», …).
`work_type` — машинный ключ этапа в направлении (`ConfigDirection.work_types`).

`WORK_TYPE_INFO` — каноническая связь work_type → (bucket, роль-исполнитель
по умолчанию). Все остальные карты в `gantt.py`/`logic.py`/`epic_forecast.py`
(`WORK_TYPE_TO_BUCKET`, порядок пайплайна, допустимые бакеты роли) выводятся
отсюда, чтобы названия этапов не дублировались по модулям. Роль направления
может переопределить дефолтную через `role_overrides`.
"""

# Bucket-имена — отображаемые русские идентификаторы этапов.
ANALYSIS = "Анализ"
DESIGN = "Дизайн"
DEVELOPMENT = "Разработка"
CODE_REVIEW = "Код-ревью"
DESIGN_REVIEW = "Дизайн-ревью"
TESTING = "Тестирование"
RELEASE = "Релиз"

# work_type → {bucket, role}. role — системный дефолт исполнителя этапа.
WORK_TYPE_INFO: dict[str, dict[str, str]] = {
    "analytics":     {"bucket": ANALYSIS,      "role": "analyst"},
    "development":   {"bucket": DEVELOPMENT,   "role": "developer"},
    "testing":       {"bucket": TESTING,       "role": "analyst"},
    "design":        {"bucket": DESIGN,        "role": "designer"},
    "code_review":   {"bucket": CODE_REVIEW,   "role": "developer_lead"},
    "design_review": {"bucket": DESIGN_REVIEW, "role": "designer_lead"},
    "release":       {"bucket": RELEASE,       "role": "developer_lead"},
}

# work_type → bucket (производная от WORK_TYPE_INFO).
WORK_TYPE_TO_BUCKET: dict[str, str] = {
    wt: info["bucket"] for wt, info in WORK_TYPE_INFO.items()
}

# Дефолтный порядок этапов на Ганте / в пайплайне направления.
DEFAULT_BUCKET_PIPELINE = [
    ANALYSIS, DESIGN, DEVELOPMENT, CODE_REVIEW, DESIGN_REVIEW, TESTING, RELEASE,
]

# Бакеты ревью/вехи: время определяется только настроенным дефолтом
# (role_status_default_hours), поля задачи (timeoriginalestimate, sp, …) не учитываются.
REVIEW_BUCKETS = frozenset({CODE_REVIEW, DESIGN_REVIEW, RELEASE})

# Bucket → категория поля часов в Jira.
BUCKET_TO_ROLE_HOURS_FIELD: dict[str, str] = {
    ANALYSIS:    "analyst",
    TESTING:     "tester",
    DESIGN:      "designer",
    DEVELOPMENT: "developer",
}

# prefix роли → допустимые bucket-категории. Защита от несовместимых
# role_overrides (не отдать «Тестирование»/«Анализ» разработчику и т.п.).
ROLE_WORK_CATEGORIES: dict[str, frozenset[str]] = {
    "analyst":   frozenset({ANALYSIS, TESTING}),
    "tester":    frozenset({TESTING}),
    "developer": frozenset({DEVELOPMENT, CODE_REVIEW, RELEASE}),
    "designer":  frozenset({DESIGN, DESIGN_REVIEW}),
}
