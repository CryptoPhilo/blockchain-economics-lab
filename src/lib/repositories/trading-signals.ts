import { SupabaseClient } from '@supabase/supabase-js'
import type {
  CreateTradingSignalInput,
  CreateTradingSignalReviewInput,
  CreateTradingSignalRunInput,
  TradingSignal,
  TradingSignalReview,
  TradingSignalRun,
} from '../types'

type TradingSignalsRepositoryMode = 'service_role'

/**
 * Trading signal storage is internal-only for the current beta rollout.
 * Use a service-role Supabase client so repository usage matches the table RLS policy.
 */
export class TradingSignalsRepository {
  constructor(
    private supabase: SupabaseClient,
    private mode: TradingSignalsRepositoryMode = 'service_role'
  ) {}

  private assertServiceRoleAccess(methodName: string) {
    if (this.mode !== 'service_role') {
      throw new Error(`${methodName} requires a service-role Supabase client`)
    }
  }

  async createRun(input: CreateTradingSignalRunInput) {
    this.assertServiceRoleAccess('createRun')

    const { data, error } = await this.supabase
      .from('trading_signal_runs')
      .insert({
        source: input.source ?? 'timesfm',
        model_version: input.modelVersion,
        features_version: input.featuresVersion,
        method: input.method,
        generated_at: input.generatedAt,
        source_window_start: input.sourceWindowStart,
        source_window_end: input.sourceWindowEnd,
        input_uri: input.inputUri,
        metadata: input.metadata ?? {},
      })
      .select('*')
      .single()

    if (error) {
      throw new Error(`Failed to create trading signal run: ${error.message}`)
    }

    return data as TradingSignalRun
  }

  async createSignals(inputs: CreateTradingSignalInput[]) {
    this.assertServiceRoleAccess('createSignals')

    if (inputs.length === 0) {
      return [] as TradingSignal[]
    }

    const { data, error } = await this.supabase
      .from('trading_signals')
      .insert(
        inputs.map((input) => ({
          run_id: input.runId,
          project_id: input.projectId,
          signal_date: input.signalDate,
          horizon_days: input.horizonDays ?? 7,
          direction: input.direction,
          confidence: input.confidence,
          predicted_return_1d: input.predictedReturn1d,
          historical_direction_accuracy: input.historicalDirectionAccuracy,
          last_spot_close: input.lastSpotClose,
          predicted_spot_close_1d: input.predictedSpotClose1d,
        }))
      )
      .select('*')

    if (error) {
      throw new Error(`Failed to create trading signals: ${error.message}`)
    }

    return (data ?? []) as TradingSignal[]
  }

  async createReview(input: CreateTradingSignalReviewInput) {
    this.assertServiceRoleAccess('createReview')

    const { data, error } = await this.supabase
      .from('trading_signal_reviews')
      .insert({
        signal_id: input.signalId,
        action: input.action,
        actor_id: input.actorId,
        note: input.note,
        metadata: input.metadata ?? {},
      })
      .select('*')
      .single()

    if (error) {
      throw new Error(`Failed to create trading signal review: ${error.message}`)
    }

    return data as TradingSignalReview
  }

  async getLatestApprovedSignal(projectId: string) {
    this.assertServiceRoleAccess('getLatestApprovedSignal')

    const { data, error } = await this.supabase
      .from('trading_signals')
      .select(`
        *,
        project:tracked_projects(id, name, slug, symbol, chain, category, status),
        run:trading_signal_runs(*)
      `)
      .eq('project_id', projectId)
      .eq('review_status', 'approved')
      .order('approved_at', { ascending: false, nullsFirst: false })
      .order('created_at', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (error) {
      throw new Error(`Failed to fetch latest approved trading signal: ${error.message}`)
    }

    return data as TradingSignal | null
  }

  async getPendingReviewSignals(limit = 50) {
    this.assertServiceRoleAccess('getPendingReviewSignals')

    const { data, error } = await this.supabase
      .from('trading_signals')
      .select(`
        *,
        project:tracked_projects(id, name, slug, symbol, chain, category, status),
        run:trading_signal_runs(*)
      `)
      .eq('review_status', 'pending_review')
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) {
      throw new Error(`Failed to fetch pending-review trading signals: ${error.message}`)
    }

    return (data ?? []) as TradingSignal[]
  }
}

export function createTradingSignalsAdminRepository(supabase: SupabaseClient) {
  return new TradingSignalsRepository(supabase, 'service_role')
}
