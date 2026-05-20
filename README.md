# Patch 2.10-fix — фикс TypeScript ошибок

Три файла подменяются (поверх 2.10):
- frontend/src/types/api.ts — TeamMemberOut с id/person_id (не jira_account_id)
- frontend/src/components/settings/TeamEditor.tsx — c roleOptions (как ожидает SettingsPage)
- frontend/src/components/settings/PseudoTasksEditor.tsx — фильтрует свежедобавленных

## Шаги

    cd ~/Dev
    unzip -o ~/Downloads/sprint-builder-patch-2.10-fix.zip -d sprint-builder/
    cd sprint-builder
    docker compose up -d --build frontend

## Особенность

Если добавишь нового человека через "+ Добавить из Jira" — его id будет 0 до
первого сохранения конфига. До сохранения он НЕ доступен в дропдауне
PseudoTasksEditor (там предупреждение жёлтым).

Шаги: 1) добавил → 2) Сохранить → 3) теперь можно завести псевдо-задачу.
