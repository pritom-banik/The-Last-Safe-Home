import type { AnalysisResult, ChangeType, Observation } from '../types';

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function runAnalysis(input: {
  bbox: number[];
  start_date: string;
  end_date: string;
  change_type: ChangeType;
}): Promise<AnalysisResult> {
  const response = await fetch(`${apiBase}/api/analysis`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error('Analysis service is unavailable');
  return response.json() as Promise<AnalysisResult>;
}

export async function searchObservations(input: {
  bbox: number[];
  start_date: string;
  end_date: string;
  keyword: string;
}): Promise<Observation[]> {
  const query = new URLSearchParams({
    bbox: input.bbox.join(','),
    start_date: input.start_date,
    end_date: input.end_date,
    keyword: input.keyword,
  });
  const response = await fetch(`${apiBase}/api/nasa/search?${query}`);
  if (!response.ok) throw new Error('NASA CMR search is unavailable');
  const body = (await response.json()) as { observations: Observation[] };
  return body.observations;
}