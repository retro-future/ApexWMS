import { describe, expect, it } from "vitest";

import { checkLogo, MAX_LOGO_BYTES, readLogoBase64 } from "@/lib/letterhead";

function file(name: string, type: string, size = 10): File {
  return new File([new Uint8Array(size)], name, { type });
}

describe("checking a letterhead logo", () => {
  it("accepts a PNG and a JPEG", () => {
    expect(checkLogo(file("logo.png", "image/png"))).toBeNull();
    expect(checkLogo(file("logo.jpg", "image/jpeg"))).toBeNull();
  });

  it("refuses an image the page cannot draw", () => {
    // A real image, and still the wrong sort of file.
    expect(checkLogo(file("logo.gif", "image/gif"))).toBe("wrongType");
    expect(checkLogo(file("logo.svg", "image/svg+xml"))).toBe("wrongType");
  });

  it("refuses a file past the cap the server also holds", () => {
    expect(checkLogo(file("big.png", "image/png", MAX_LOGO_BYTES + 1))).toBe(
      "tooLarge",
    );
    expect(checkLogo(file("fits.png", "image/png", MAX_LOGO_BYTES))).toBeNull();
  });

  it("names the type before the size", () => {
    // A 2MB GIF is wrong twice over; the type is the more useful thing to say.
    const wrong = file("big.gif", "image/gif", MAX_LOGO_BYTES + 1);
    expect(checkLogo(wrong)).toBe("wrongType");
  });
});

describe("reading it for the wire", () => {
  it("strips the data-URL prefix the API does not want", async () => {
    const content = await readLogoBase64(
      new File([new Uint8Array([0, 1, 2, 3])], "logo.png", { type: "image/png" }),
    );

    expect(content).not.toContain("base64,");
    expect(content).toBe("AAECAw==");
  });
});
