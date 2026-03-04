/**
 * Auto STT Engine
 *
 * Selects the best available STT engine based on a configurable preference
 * order. Skips unavailable engines automatically.
 *
 * Default preference: cloud -> native -> browser -> on-device
 */

import type { STTEngine, STTStartOptions } from "./engine"
import { BrowserSTTEngine } from "./browser-stt-engine"
import { CloudSTTEngine, type CloudSTTConfig } from "./cloud-stt-engine"

export interface AutoSTTConfig {
  /** Comma-separated engine preference order */
  preferenceOrder?: string
  /** Cloud STT configuration */
  cloudConfig?: CloudSTTConfig
  /** Whether cloud STT is available (API key configured) */
  cloudAvailable?: boolean
}

const DEFAULT_PREFERENCE = "cloud,native,browser,on-device"

export class AutoSTTEngine implements STTEngine {
  readonly id = "browser" as const // Fallback ID
  readonly name = "Auto"

  private config: AutoSTTConfig
  private selectedEngine: STTEngine | null = null
  private engines: Map<string, STTEngine>

  constructor(config: AutoSTTConfig = {}) {
    this.config = config

    // Build engine registry
    this.engines = new Map()
    this.engines.set("browser", new BrowserSTTEngine())
    this.engines.set(
      "cloud",
      new CloudSTTEngine(config.cloudConfig ?? {})
    )
    // "native" and "on-device" engines will be added by future proposals
  }

  async isAvailable(): Promise<boolean> {
    const preference = this.config.preferenceOrder ?? DEFAULT_PREFERENCE
    const order = preference.split(",").map((e) => e.trim())

    for (const engineId of order) {
      const engine = this.engines.get(engineId)
      if (!engine) continue

      // Skip cloud if not configured
      if (engineId === "cloud" && !this.config.cloudAvailable) continue

      const available = await engine.isAvailable()
      if (available) return true
    }
    return false
  }

  start(options: STTStartOptions): void {
    const preference = this.config.preferenceOrder ?? DEFAULT_PREFERENCE
    const order = preference.split(",").map((e) => e.trim())

    for (const engineId of order) {
      const engine = this.engines.get(engineId)
      if (!engine) continue

      // Skip cloud if not configured
      if (engineId === "cloud" && !this.config.cloudAvailable) continue

      if (engine.isAvailable()) {
        this.selectedEngine = engine
        engine.start(options)
        return
      }
    }

    options.events.onError("No STT engine is available")
  }

  stop(): void {
    this.selectedEngine?.stop()
  }

  destroy(): void {
    for (const engine of this.engines.values()) {
      engine.destroy()
    }
    this.selectedEngine = null
  }
}
