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
import { OnDeviceSTTEngine } from "./on-device-stt-engine"

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
    this.engines.set("on-device", new OnDeviceSTTEngine())
    // "native" engine will be added by Capacitor/Tauri proposals
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
    // Engine selection is async (some engines need async isAvailable checks)
    // so we kick off selection and start as an async IIFE
    void this.selectAndStart(options)
  }

  private async selectAndStart(options: STTStartOptions): Promise<void> {
    const preference = this.config.preferenceOrder ?? DEFAULT_PREFERENCE
    const order = preference.split(",").map((e) => e.trim())

    for (const engineId of order) {
      const engine = this.engines.get(engineId)
      if (!engine) continue

      // Skip cloud if not configured
      if (engineId === "cloud" && !this.config.cloudAvailable) continue

      const available = await engine.isAvailable()
      if (available) {
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
