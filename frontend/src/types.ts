export type ChangeType = 'flood' | 'wildfire' | 'deforestation' | 'agriculture';

export interface AnalysisResult {
  status: string;
  change_type: ChangeType;
  affected_area_km2: number;
  change_percent: number;
  confidence: number;
  severity: string;
  risk_level: string;
  explanation: string;
  is_simulated: boolean;
  source_label: string;
}

export interface Observation {
  title: string;
  start_date: string | null;
  end_date: string | null;
  collection_id: string | null;
  producer_id: string | null;
}