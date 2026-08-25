/**
 * What the store's letterhead logo may be (FR-8.1).
 *
 * A courtesy, never enforcement: the server checks the size again and sniffs
 * the file's magic bytes rather than trusting the type the browser reported,
 * so a file that slips past these still comes back a 422. Catching it here
 * only saves the operator a round trip and a less specific message.
 *
 * Pure functions over a `File`, deliberately free of React.
 */

export const MAX_LOGO_BYTES = 512 * 1024;

/** PNG and JPEG only — the two fpdf2 draws on a page. */
export const LOGO_TYPES = ["image/png", "image/jpeg"];

/** A translation key, not a sentence: the screen owns the wording. */
export type LogoProblem = "tooLarge" | "wrongType";

export function checkLogo(file: File): LogoProblem | null {
  if (!LOGO_TYPES.includes(file.type)) return "wrongType";
  if (file.size > MAX_LOGO_BYTES) return "tooLarge";
  return null;
}

/**
 * The file as bare base64, without the `data:image/png;base64,` prefix a data
 * URL carries — the API wants the payload alone.
 */
export function readLogoBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("unreadable file"));
    reader.onload = () => {
      const url = String(reader.result);
      resolve(url.slice(url.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  });
}
