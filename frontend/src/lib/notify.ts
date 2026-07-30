import { notifications } from "@mantine/notifications";

import { ApiError } from "@/lib/api";

export function notifySuccess(message: string): void {
  notifications.show({ message, color: "teal" });
}

export function notifyError(message: string): void {
  notifications.show({ message, color: "red" });
}

/** Turn a thrown value into something worth showing a user. */
export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.message) return error.message;
  return fallback;
}
