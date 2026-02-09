/**
 * Generation Components
 *
 * Dialogs for configuring and triggering various generation tasks.
 */

export { GenerateDigestDialog } from "./GenerateDigestDialog"
export type { DigestGenerationParams } from "./GenerateDigestDialog"

export { GenerateScriptDialog } from "./GenerateScriptDialog"
export type { ScriptGenerationParams } from "./GenerateScriptDialog"

export { GenerateSummaryDialog } from "./GenerateSummaryDialog"
export type { SummaryGenerationParams } from "./GenerateSummaryDialog"

/** @deprecated Use IngestContentsDialog instead */
export { IngestNewslettersDialog } from "./IngestNewslettersDialog"
/** @deprecated Use IngestContentParams instead */
export type { IngestParams } from "./IngestNewslettersDialog"

export { IngestContentsDialog } from "./IngestContentsDialog"
export type { IngestContentParams, SaveUrlParams } from "./IngestContentsDialog"

export { GenerateAudioDialog } from "./GenerateAudioDialog"
export type { AudioGenerationParams } from "./GenerateAudioDialog"

export { GenerateAudioDigestDialog } from "./GenerateAudioDigestDialog"
export type { AudioDigestGenerationParams } from "./GenerateAudioDigestDialog"

export { AnalyzeThemesDialog } from "./AnalyzeThemesDialog"
export type { ThemeAnalysisParams } from "./AnalyzeThemesDialog"
