# Sprint Builder — Frontend

React + Vite + TypeScript + Tailwind CSS.

## Запуск (локально)

Перед стартом фронта должен быть запущен бэкенд на http://localhost:8000.

```bash
# Установка зависимостей (один раз после клонирования)
npm install

# Опционально: настройка адреса бэкенда
cp .env.example .env

# Старт dev-сервера
npm run dev
```

Откроется на http://localhost:5173 (Vite дефолт).

## Структура

```
src/
├── main.tsx              Точка входа React
├── App.tsx               Главный компонент
├── index.css             Tailwind + базовые стили
├── api/client.ts         HTTP-клиент к бэкенду (axios)
├── types/api.ts          TypeScript-типы (зеркало Pydantic-схем бэкенда)
└── components/
    ├── OwnerStats.tsx    Плашки "Загрузка по аналитикам"
    └── SprintTable.tsx   Таблица задач (TanStack Table)
```
