import { useState } from "react";

/**
 * Редактор словаря: показывает таблицу пар ключ-значение с inline-редактированием.
 * Используется для status_bucket, status_priority, bucket_hours_field, role_hours_fields.
 *
 * Хранит локальный буфер изменений; родитель видит только итоговый объект через onChange.
 */
interface Props<V> {
  value: Record<string, V>;
  onChange: (next: Record<string, V>) => void;
  keyLabel: string;
  valueLabel: string;
  /** Если задан — value-поле будет селектом с этими опциями. */
  valueOptions?: string[];
  /** Тип value — string или number. */
  valueType?: "string" | "number";
}

export function DictEditor<V extends string | number>({
  value,
  onChange,
  keyLabel,
  valueLabel,
  valueOptions,
  valueType = "string",
}: Props<V>) {
  // Сохраняем порядок ключей в локальном стейте — иначе при изменении ключа
  // объект перестраивается и порядок строк в таблице прыгает.
  const [keys, setKeys] = useState<string[]>(() => Object.keys(value));

  const handleKeyChange = (i: number, newKey: string) => {
    const oldKey = keys[i];
    const newKeys = [...keys];
    newKeys[i] = newKey;
    setKeys(newKeys);
    const next: Record<string, V> = {};
    newKeys.forEach((k, idx) => {
      const sourceKey = idx === i ? oldKey : k;
      next[k] = value[sourceKey];
    });
    onChange(next);
  };

  const handleValueChange = (i: number, newVal: V) => {
    const k = keys[i];
    onChange({ ...value, [k]: newVal });
  };

  const handleAdd = () => {
    const newKey = "новый_ключ";
    const defaultVal = (valueType === "number" ? 0 : "") as V;
    setKeys([...keys, newKey]);
    onChange({ ...value, [newKey]: defaultVal });
  };

  const handleRemove = (i: number) => {
    const k = keys[i];
    const newKeys = keys.filter((_, idx) => idx !== i);
    setKeys(newKeys);
    const next = { ...value };
    delete next[k];
    onChange(next);
  };

  return (
    <div>
      <table className="w-full text-sm border">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left px-2 py-1 border-b font-semibold">{keyLabel}</th>
            <th className="text-left px-2 py-1 border-b font-semibold">{valueLabel}</th>
            <th className="px-2 py-1 border-b w-12"></th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k, i) => (
            <tr key={i} className="border-b">
              <td className="px-2 py-1">
                <input
                  type="text"
                  value={k}
                  onChange={(e) => handleKeyChange(i, e.target.value)}
                  className="w-full px-2 py-1 border rounded"
                />
              </td>
              <td className="px-2 py-1">
                {valueOptions ? (
                  <select
                    value={String(value[k])}
                    onChange={(e) => handleValueChange(i, e.target.value as V)}
                    className="w-full px-2 py-1 border rounded bg-white"
                  >
                    {valueOptions.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type={valueType === "number" ? "number" : "text"}
                    value={String(value[k])}
                    onChange={(e) => {
                      const v = (
                        valueType === "number" ? Number(e.target.value) : e.target.value
                      ) as V;
                      handleValueChange(i, v);
                    }}
                    className="w-full px-2 py-1 border rounded"
                  />
                )}
              </td>
              <td className="px-2 py-1 text-center">
                <button
                  onClick={() => handleRemove(i)}
                  className="text-red-500 hover:text-red-700 text-lg"
                  title="Удалить"
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        onClick={handleAdd}
        className="mt-2 text-sm text-blue-600 hover:text-blue-800"
      >
        + Добавить
      </button>
    </div>
  );
}
