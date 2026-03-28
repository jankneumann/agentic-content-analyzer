import { describe, it, expect } from "vitest"
import { validateShareUrl, extractUrl } from "../url-validator"

describe("validateShareUrl", () => {
  it("accepts valid http URLs", () => {
    expect(validateShareUrl("http://example.com")).toEqual({ valid: true })
    expect(validateShareUrl("http://example.com/path?q=1")).toEqual({
      valid: true,
    })
  })

  it("accepts valid https URLs", () => {
    expect(validateShareUrl("https://example.com")).toEqual({ valid: true })
    expect(validateShareUrl("https://sub.example.com/path/to/page")).toEqual({
      valid: true,
    })
  })

  it("trims whitespace before validation", () => {
    expect(validateShareUrl("  https://example.com  ")).toEqual({ valid: true })
  })

  it("rejects empty strings", () => {
    const result = validateShareUrl("")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/empty/i)
  })

  it("rejects whitespace-only strings", () => {
    const result = validateShareUrl("   ")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/empty/i)
  })

  it("rejects javascript: scheme", () => {
    const result = validateShareUrl("javascript:alert(1)")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/javascript:/i)
  })

  it("rejects JAVASCRIPT: (case-insensitive)", () => {
    const result = validateShareUrl("JAVASCRIPT:alert(1)")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/javascript:/i)
  })

  it("rejects data: scheme", () => {
    const result = validateShareUrl("data:text/html,<h1>XSS</h1>")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/data:/i)
  })

  it("rejects file: scheme", () => {
    const result = validateShareUrl("file:///etc/passwd")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/file:/i)
  })

  it("rejects blob: scheme", () => {
    const result = validateShareUrl("blob:https://example.com/uuid")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/blob:/i)
  })

  it("rejects vbscript: scheme", () => {
    const result = validateShareUrl("vbscript:MsgBox('XSS')")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/vbscript:/i)
  })

  it("rejects ftp: scheme (not in allowlist)", () => {
    const result = validateShareUrl("ftp://files.example.com/file.txt")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/unsupported url scheme/i)
  })

  it("rejects URLs exceeding 2048 characters", () => {
    const longUrl = "https://example.com/" + "a".repeat(2040)
    expect(longUrl.length).toBeGreaterThan(2048)
    const result = validateShareUrl(longUrl)
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/too long/i)
  })

  it("accepts URLs at exactly 2048 characters", () => {
    const url = "https://example.com/" + "a".repeat(2028)
    expect(url.length).toBe(2048)
    expect(validateShareUrl(url)).toEqual({ valid: true })
  })

  it("rejects malformed URLs", () => {
    const result = validateShareUrl("not a url at all")
    expect(result.valid).toBe(false)
    expect(result.error).toMatch(/invalid url/i)
  })

  it("rejects URLs with no protocol", () => {
    const result = validateShareUrl("example.com/page")
    expect(result.valid).toBe(false)
  })
})

describe("extractUrl", () => {
  it("extracts URL from surrounding text", () => {
    expect(extractUrl("Check out https://example.com/article today")).toBe(
      "https://example.com/article",
    )
  })

  it("extracts first URL when multiple present", () => {
    expect(
      extractUrl("See https://first.com and https://second.com"),
    ).toBe("https://first.com")
  })

  it("extracts http URL", () => {
    expect(extractUrl("Visit http://legacy.example.com")).toBe(
      "http://legacy.example.com",
    )
  })

  it("extracts URL with query parameters", () => {
    expect(extractUrl("Link: https://example.com/search?q=test&page=1")).toBe(
      "https://example.com/search?q=test&page=1",
    )
  })

  it("returns null when no URL found", () => {
    expect(extractUrl("No links here, just plain text")).toBeNull()
  })

  it("returns null for empty string", () => {
    expect(extractUrl("")).toBeNull()
  })

  it("ignores javascript: URIs", () => {
    expect(extractUrl("javascript:alert(1)")).toBeNull()
  })

  it("extracts URL even when surrounded by angle brackets", () => {
    expect(extractUrl("See <https://example.com>")).toBe(
      "https://example.com",
    )
  })
})
