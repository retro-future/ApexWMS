"use client";

import { Text, TextInput, type TextInputProps } from "@mantine/core";

type MoneyInputProps = Omit<TextInputProps, "rightSection" | "rightSectionWidth" | "onChange"> & {
  value: string;
  onChange: (value: string) => void;
  /** Shown as a fixed suffix; omit (or pass a falsy value) while it isn't known yet. */
  currency?: string | null | false;
};

/** A som/dollar amount input with its currency shown as a fixed suffix. */
export function MoneyInput({ value, onChange, currency, ...props }: MoneyInputProps) {
  return (
    <TextInput
      {...props}
      value={value}
      onChange={(event) => onChange(event.currentTarget.value)}
      inputMode="numeric"
      rightSection={
        currency ? (
          <Text size="xs" c="dimmed">
            {currency}
          </Text>
        ) : undefined
      }
      rightSectionWidth={44}
    />
  );
}
