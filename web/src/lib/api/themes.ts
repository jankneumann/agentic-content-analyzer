/**
 * Theme Analysis API Client
 */

import { apiClient } from "./client"
import type { ThemeAnalysisResult } from "@/types"

export interface AnalyzeThemesRequest {
  start_date?: string
  end_date?: string
  max_themes?: number
  min_newsletters?: number
  relevance_threshold?: number
  include_historical_context?: boolean
}

export interface AnalyzeThemesResponse {
  status: string
  message: string
  analysis_id: number | null
}

export interface AnalysisStatusResponse {
  status: string
  result: ThemeAnalysisResult | null
}

export interface AnalysisListItem {
  id: number
  status: string
  content_count: number | null
  total_themes: number | null
  analysis_date: string | null
  start_date: string | null
  end_date: string | null
  created_at: string | null
}

/**
 * Trigger theme analysis
 */
export async function analyzeThemes(
  request: AnalyzeThemesRequest
): Promise<AnalyzeThemesResponse> {
  return apiClient.post<AnalyzeThemesResponse>("/themes/analyze", request)
}

/**
 * Get analysis status and results
 */
export async function getAnalysisStatus(
  analysisId: number
): Promise<AnalysisStatusResponse> {
  return apiClient.get<AnalysisStatusResponse>(`/themes/analysis/${analysisId}`)
}

/**
 * Get a single analysis by ID (extracts result from status wrapper)
 */
export async function getAnalysisById(
  id: number
): Promise<ThemeAnalysisResult | null> {
  const response = await apiClient.get<AnalysisStatusResponse>(`/themes/analysis/${id}`)
  return response.result
}

/**
 * Get the latest completed analysis
 */
export async function getLatestAnalysis(): Promise<ThemeAnalysisResult | { message: string }> {
  return apiClient.get<ThemeAnalysisResult | { message: string }>("/themes/latest")
}

/**
 * List recent analyses
 */
export async function listAnalyses(
  limit: number = 10,
  offset: number = 0
): Promise<AnalysisListItem[]> {
  return apiClient.get<AnalysisListItem[]>(`/themes?limit=${limit}&offset=${offset}`)
}
