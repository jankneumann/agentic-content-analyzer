import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

Object.defineProperties(Element.prototype, {
  hasPointerCapture: { value: () => false },
  setPointerCapture: { value: () => undefined },
  releasePointerCapture: { value: () => undefined },
  scrollIntoView: { value: () => undefined },
})

import { SourcesConfigurator } from "../SourcesConfigurator"

const hooks = vi.hoisted(() => ({
  sources: vi.fn(),
  upsert: vi.fn(),
  remove: vi.fn(),
  setEnabled: vi.fn(),
}))

vi.mock("@/hooks/use-settings", () => ({
  useSources: hooks.sources,
  useUpsertSource: hooks.upsert,
  useDeleteSource: hooks.remove,
  useSetSourceEnabled: hooks.setEnabled,
}))

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const overview = {
  sources: [
    {
      type: "rss",
      name: "Release feed",
      url: "https://example.test/releases.xml",
      enabled: true,
      tags: [],
      origin: "yaml" as const,
      source_key: "rss:https://example.test/releases.xml",
    },
    {
      type: "readwise",
      name: "Readwise Reader",
      url: "readwise",
      enabled: false,
      tags: [],
      origin: "db" as const,
      source_key: "readwise:reader",
    },
    {
      type: "obsidian_vault",
      name: "Private research vault",
      url: "/srv/private/research-vault",
      enabled: true,
      tags: [],
      origin: "db" as const,
      source_key: "src_0123456789abcdefabcd",
    },
  ],
  counts: {},
  total_sources: 3,
  enabled_sources: 2,
}

function mutation(mutate: ReturnType<typeof vi.fn>, isPending = false) {
  return { mutate, isPending }
}

function renderSources() {
  hooks.sources.mockReturnValue({
    data: overview,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  })
  render(<SourcesConfigurator />)
}

async function selectSourceType(
  user: ReturnType<typeof userEvent.setup>,
  label: string
) {
  await user.click(screen.getByRole("combobox", { name: "Type" }))
  await user.click(await screen.findByRole("option", { name: label }))
}

describe("SourcesConfigurator", () => {
  beforeEach(() => {
    hooks.upsert.mockReturnValue(mutation(vi.fn()))
    hooks.remove.mockReturnValue(mutation(vi.fn()))
    hooks.setEnabled.mockReturnValue(mutation(vi.fn()))
  })

  it("renders mixed origins and enabled states without exposing Obsidian private values", () => {
    renderSources()

    expect(screen.getByText("Release feed")).toBeInTheDocument()
    expect(screen.getByText("Readwise Reader")).toBeInTheDocument()
    expect(screen.getAllByText("yaml")).toHaveLength(1)
    expect(screen.getAllByText("db")).toHaveLength(2)
    expect(
      screen.getByRole("switch", { name: "Toggle Release feed" })
    ).toBeChecked()
    expect(
      screen.queryByRole("button", {
        name: "Remove database override for Release feed",
      })
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole("switch", { name: "Toggle Readwise Reader" })
    ).not.toBeChecked()

    expect(screen.getByText("Obsidian vault")).toBeInTheDocument()
    expect(screen.getByText("src_0123456789abcdefabcd")).toBeInTheDocument()
    expect(
      screen.getByRole("switch", { name: "Toggle Obsidian vault" })
    ).toBeChecked()
    expect(
      screen.getByRole("button", {
        name: "Remove database override for Obsidian vault",
      })
    ).toBeInTheDocument()
    expect(screen.queryByText("Private research vault")).not.toBeInTheDocument()
    expect(
      screen.queryByText("/srv/private/research-vault")
    ).not.toBeInTheDocument()
  })

  it("submits Readwise quick-add options inside config without credentials", async () => {
    const user = userEvent.setup()
    const mutate = vi.fn((_request, options) =>
      options.onSuccess({ source_key: "readwise:reader" })
    )
    hooks.upsert.mockReturnValue(mutation(mutate))
    renderSources()

    await user.click(screen.getByRole("button", { name: "Add source" }))
    await selectSourceType(user, "Readwise")
    await user.type(
      screen.getByRole("textbox", { name: "Source types" }),
      "kindle, reader"
    )
    await user.click(
      screen.getByRole("checkbox", { name: "Include deleted items" })
    )
    await user.click(screen.getByRole("button", { name: "Add", hidden: false }))

    expect(mutate).toHaveBeenCalledWith(
      {
        config: {
          type: "readwise",
          source_types: ["kindle", "reader"],
          include_deleted: true,
        },
      },
      expect.any(Object)
    )
    expect(JSON.stringify(mutate.mock.calls[0][0])).not.toMatch(
      /token|secret|credential/i
    )
  })

  it("offers no browser create or edit fields for Obsidian", async () => {
    const user = userEvent.setup()
    renderSources()

    await user.click(screen.getByRole("button", { name: "Add source" }))
    await user.click(screen.getByRole("combobox", { name: "Type" }))

    expect(
      screen.queryByRole("option", { name: /Obsidian/i })
    ).not.toBeInTheDocument()
    await user.keyboard("{Escape}")
    const addDialog = screen.getByRole("dialog", {
      name: "Add ingestion source",
    })
    expect(
      within(addDialog).queryByLabelText(
        /vault path|ingest folder|allowed roots/i
      )
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: /edit obsidian/i })
    ).not.toBeInTheDocument()
  })

  it("redacts and disables a malformed Obsidian management key", () => {
    hooks.sources.mockReturnValue({
      data: {
        ...overview,
        sources: overview.sources.map((source) =>
          source.type === "obsidian_vault"
            ? {
                ...source,
                source_key: "obsidian_vault:/srv/private/research-vault",
              }
            : source
        ),
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })
    render(<SourcesConfigurator />)

    expect(
      screen.getByText("Private source identifier unavailable")
    ).toBeInTheDocument()
    expect(
      screen.queryByText(/obsidian_vault:\/srv\/private/)
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole("switch", { name: "Toggle Obsidian vault" })
    ).toBeDisabled()
    expect(
      screen.getByRole("button", {
        name: "Remove database override for Obsidian vault",
      })
    ).toBeDisabled()
  })

  it("prevents toggle and delete from racing on the same row", () => {
    hooks.setEnabled.mockReturnValue(mutation(vi.fn(), true))
    renderSources()

    expect(
      screen.getByRole("switch", { name: "Toggle Readwise Reader" })
    ).toBeDisabled()
    expect(
      screen.getByRole("button", {
        name: "Remove database override for Readwise Reader",
      })
    ).toBeDisabled()
  })

  it("sends a toggle payload and does not optimistically change rendered state", async () => {
    const user = userEvent.setup()
    const mutate = vi.fn()
    hooks.setEnabled.mockReturnValue(mutation(mutate))
    renderSources()

    const toggle = screen.getByRole("switch", {
      name: "Toggle Readwise Reader",
    })
    await user.click(toggle)

    expect(mutate).toHaveBeenCalledWith(
      { key: "readwise:reader", enabled: true },
      expect.any(Object)
    )
    expect(toggle).not.toBeChecked()
  })

  it("explains database override removal before deleting", async () => {
    const user = userEvent.setup()
    const mutate = vi.fn((_key, options) => options.onSuccess())
    hooks.remove.mockReturnValue(mutation(mutate))
    renderSources()

    await user.click(
      screen.getByRole("button", {
        name: "Remove database override for Readwise Reader",
      })
    )
    const dialog = screen.getByRole("dialog", {
      name: "Remove database override?",
    })
    expect(
      within(dialog).getByText(/a YAML definition may reappear/i)
    ).toBeInTheDocument()
    await user.click(
      within(dialog).getByRole("button", { name: "Remove override" })
    )

    expect(mutate).toHaveBeenCalledWith("readwise:reader", expect.any(Object))
  })

  it.each([
    ["toggle", "Failed to update source"],
    ["delete", "Failed to delete source"],
  ] as const)(
    "surfaces a recoverable %s failure without changing the row",
    async (operation, message) => {
      const user = userEvent.setup()
      const failingMutation = vi.fn((_input, options) =>
        options.onError(new Error("boom"))
      )
      if (operation === "toggle")
        hooks.setEnabled.mockReturnValue(mutation(failingMutation))
      else hooks.remove.mockReturnValue(mutation(failingMutation))
      renderSources()

      const toggle = screen.getByRole("switch", {
        name: "Toggle Readwise Reader",
      })
      if (operation === "toggle") {
        await user.click(toggle)
      } else {
        await user.click(
          screen.getByRole("button", {
            name: "Remove database override for Readwise Reader",
          })
        )
        await user.click(
          screen.getByRole("button", { name: "Remove override" })
        )
      }

      expect(screen.getByRole("alert")).toHaveTextContent(message)
      expect(toggle).not.toBeChecked()
      expect(toggle).toBeEnabled()
    }
  )

  it("keeps the add dialog recoverable after an add failure", async () => {
    const user = userEvent.setup()
    const failingMutation = vi.fn((_request, options) =>
      options.onError(new Error("boom"))
    )
    hooks.upsert.mockReturnValue(mutation(failingMutation))
    renderSources()

    await user.click(screen.getByRole("button", { name: "Add source" }))
    await selectSourceType(user, "Readwise")
    await user.click(screen.getByRole("button", { name: "Add", hidden: false }))

    expect(screen.getByRole("alert")).toHaveTextContent("Failed to add source")
    expect(
      screen.getByRole("dialog", { name: "Add ingestion source" })
    ).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Add", hidden: false })
    ).toBeEnabled()
  })
})
