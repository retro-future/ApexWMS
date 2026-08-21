import { describe, expect, it } from "vitest";

import { isEditable } from "@/lib/documents";

describe("isEditable", () => {
  it("allows edits only while the document is a draft (§4.4)", () => {
    expect(isEditable("draft")).toBe(true);
    expect(isEditable("confirmed")).toBe(false);
    expect(isEditable("cancelled")).toBe(false);
  });
});
