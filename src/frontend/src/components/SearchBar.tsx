/**
 * SearchBar — 搜索输入组件
 */
import React, { useState, useRef, useEffect } from "react";

interface SearchBarProps {
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  onSearch?: (value: string) => void;
  debounceMs?: number;
  fullWidth?: boolean;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  placeholder = "搜索...",
  value,
  onChange,
  onSearch,
  debounceMs = 300,
  fullWidth = true,
}) => {
  const [localValue, setLocalValue] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setLocalValue(newValue);
    onChange(newValue);

    if (onSearch) {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => onSearch(newValue), debounceMs);
    }
  };

  const handleClear = () => {
    setLocalValue("");
    onChange("");
    inputRef.current?.focus();
  };

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      background: "var(--bg-primary)",
      border: "1px solid var(--border)",
      borderRadius: 8,
      padding: "0 12px",
      width: fullWidth ? "100%" : "auto",
      transition: "border-color 150ms ease, box-shadow 150ms ease",
    }}>
      <span style={{ color: "var(--text-muted)", fontSize: 16 }}>🔍</span>
      <input
        ref={inputRef}
        type="text"
        value={localValue}
        onChange={handleChange}
        placeholder={placeholder}
        style={{
          flex: 1, border: "none", outline: "none",
          background: "transparent", padding: "10px 0",
          fontSize: 14, color: "var(--text-primary)",
          fontFamily: "inherit",
        }}
      />
      {localValue && (
        <button
          onClick={handleClear}
          style={{
            background: "none", border: "none", cursor: "pointer",
            color: "var(--text-muted)", fontSize: 16, padding: 4,
          }}
        >
          ✕
        </button>
      )}
    </div>
  );
};
