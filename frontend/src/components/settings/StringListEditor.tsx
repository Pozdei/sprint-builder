interface Props {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}

/** Редактор простого списка строк (extra_components, strict_assignee_buckets). */
export function StringListEditor({ value, onChange, placeholder }: Props) {
  const handleChange = (i: number, v: string) => {
    const next = [...value];
    next[i] = v;
    onChange(next);
  };

  const handleAdd = () => onChange([...value, ""]);
  const handleRemove = (i: number) => onChange(value.filter((_, idx) => idx !== i));

  return (
    <div>
      <div className="space-y-1">
        {value.map((v, i) => (
          <div key={i} className="flex gap-2">
            <input
              type="text"
              value={v}
              onChange={(e) => handleChange(i, e.target.value)}
              placeholder={placeholder}
              className="flex-1 px-2 py-1 border rounded text-sm"
            />
            <button
              onClick={() => handleRemove(i)}
              className="text-red-500 hover:text-red-700 px-2"
              title="Удалить"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        onClick={handleAdd}
        className="mt-2 text-sm text-blue-600 hover:text-blue-800"
      >
        + Добавить
      </button>
    </div>
  );
}
