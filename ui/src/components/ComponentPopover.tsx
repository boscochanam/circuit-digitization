"use client";

import { useState, useRef, useEffect } from "react";

interface ComponentPopoverProps {
  name: string;
  type: string;
  currentValue: string;
  onSave: (value: string) => void;
  onClose: () => void;
}

const TYPE_PLACEHOLDERS: Record<string, string> = {
  R: "10k",
  C: "100n",
  L: "10m",
  D: "1N4148",
  Q: "2N2222",
  V: "5V",
  J: "",
  T: "",
};

export default function ComponentPopover({
  name,
  type,
  currentValue,
  onSave,
  onClose,
}: ComponentPopoverProps) {
  const [value, setValue] = useState(currentValue);
  const inputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  const handleSave = () => {
    onSave(value);
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSave();
    }
  };

  const placeholder = TYPE_PLACEHOLDERS[type] ?? "";

  return (
    <div ref={popoverRef} className="component-popover">
      <div className="component-popover-header">
        <span className="component-popover-name">{name}</span>
        <span className="component-popover-type">{type}</span>
      </div>
      <div className="component-popover-body">
        <input
          ref={inputRef}
          className="component-popover-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
        />
        <button className="component-popover-save" onClick={handleSave}>
          Save
        </button>
      </div>
    </div>
  );
}
