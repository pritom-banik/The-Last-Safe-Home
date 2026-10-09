import { useState } from 'react';
import {
  Activity, ArrowDownRight, ArrowUpRight, Clock3, CloudRain, Crosshair,
  Database, Flame, Layers2, Leaf, MapPin, Radio, Search, ShieldAlert,
  SlidersHorizontal, Sparkles, Waves,
} from 'lucide-react';
import MapView from './components/MapView';
import { runAnalysis, searchObservations } from './services/api';
import type { AnalysisResult, ChangeType, Observation } from './types';

const places = [
  { name: 'Coastal Bangladesh', center: [90.3, 22.45] as [number, number] },
  { name: 'Amazonas, Brazil', center: [-62.8, -4.4] as [number, number] },
  { name: 'Northern California', center: [-121.2, 40.1] as [number, number] },
  { name: 'Himalayan foothills', center: [85.3, 27.7] as [number, number] },
];

const changeOptions: { value: ChangeType; label: string; icon: typeof Waves }[] = [
  { value: 'flood', label: 'Surface water', icon: Waves },
  { value: 'wildfire', label: 'Wildfire', icon: Flame },
  { value: 'deforestation', label: 'Vegetation loss', icon: Leaf },
  { value: 'agriculture', label: 'Agriculture', icon: CloudRain },
];

const demoResults: Record<ChangeType, AnalysisResult> = {
  flood: { status: 'illustrative', change_type: 'flood', affected_area_km2: 31.2, change_percent: 68.4, confidence: 0.91, severity: 'High', risk_level: 'High', explanation: 'This sample scenario illustrates how a measured increase in surface water could be summarized. It is not derived from satellite imagery.', is_simulated: true, source_label: 'Illustrative demo scenario' },
  wildfire: { status: 'illustrative', change_type: 'wildfire', affected_area_km2: 18.6, change_percent: 22.1, confidence: 0.84, severity: 'Moderate', risk_level: 'Moderate', explanation: 'This illustrative wildfire scenario is a UI example only and is not derived from active-fire detections or satellite imagery.', is_simulated: true, source_label: 'Illustrative demo scenario' },
  deforestation: { status: 'illustrative', change_type: 'deforestation', affected_area_km2: 12.4, change_percent: -4.8, confidence: 0.79, severity: 'Moderate', risk_level: 'Moderate', explanation: 'This illustrative vegetation-loss scenario is a UI example only and is not derived from satellite imagery.', is_simulated: true, source_label: 'Illustrative demo scenario' },
  agriculture: { status: 'illustrative', change_type: 'agriculture', affected_area_km2: 9.7, change_percent: 13.2, confidence: 0.76, severity: 'Low', risk_level: 'Low', explanation: 'This illustrative agriculture scenario is a UI example only and is not derived from satellite imagery.', is_simulated: true, source_label: 'Illustrative demo scenario' },
};

const dateLabel = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString('en', {
  month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
});

export default function App() {
  const [place, setPlace] = useState(places[0]);
  const [customCenter, setCustomCenter] = useState<[number, number] | null>(null);
  const [changeType, setChangeType] = useState<ChangeType>('flood');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2026-01-01');
  const [result, setResult] = useState(demoResults.flood);
  const [observations, setObservations] = useState<Observation[] | null>(null);
  const [busy, setBusy] = useState<'analysis' | 'search' | null>(null);
  const [notice, setNotice] = useState('');

  const center = customCenter ?? place.center;
  const bbox = [center[0] - 0.11, center[1] - 0.08, center[0] + 0.11, center[1] + 0.08];
  const selectedOption = changeOptions.find((option) => option.value === changeType) ?? changeOptions[0];
  const SelectedIcon = selectedOption.icon;

  async function analyze() {
    setBusy('analysis');
    setNotice('');
    try {
      const response = await runAnalysis({ bbox, start_date: startDate, end_date: endDate, change_type: changeType });
      setResult(response);
      setNotice('Demo response from the local analysis API.');
    } catch {
      setResult(demoResults[changeType]);
      setNotice('API offline. Showing the built-in illustrative scenario.');
    } finally {
      setBusy(null);
    }
  }

  async function discover() {
    setBusy('search');
    setNotice('');
    try {
      setObservations(await searchObservations({ bbox, start_date: startDate, end_date: endDate, keyword: changeType }));
      setNotice('Metadata returned by NASA CMR. Metadata availability does not mean imagery has been processed.');
    } catch {
      setObservations(null);
      setNotice('Could not reach NASA CMR. Check the API and internet connection.');
    } finally {
      setBusy(null);
    }
  }

  function changePlace(name: string) {
    const selected = places.find((item) => item.name === name);
    if (selected) {
      setPlace(selected);
      setCustomCenter(null);
    }
  }

  function changeLayer(value: string) {
    const nextType = value as ChangeType;
    setChangeType(nextType);
    setResult(demoResults[nextType]);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="The Last Safe Home home">
          <span className="brand-mark"><Activity size={19} strokeWidth={2.2} /></span>
          <span className="brand-copy"><strong>THE LAST SAFE HOME</strong><small>EARTH CHANGE INTELLIGENCE</small></span>
        </a>
        <div className="topbar-right">
          <span className="live-status"><i /> DEMO ENVIRONMENT</span>
          <button className="icon-button" title="Analysis settings" aria-label="Analysis settings"><SlidersHorizontal size={17} /></button>
          <div className="avatar" title="Earth observation workspace">EO</div>
        </div>
      </header>

      <section className="workspace" id="top">
        <aside className="control-rail">
          <div className="section-kicker">MONITORING WORKSPACE</div>
          <h1>See change<br />before crisis.</h1>
          <p className="intro">Explore Earth observations across place and time.</p>

          <label className="field-label" htmlFor="location">AREA OF INTEREST</label>
          <div className="select-wrap location-wrap"><MapPin size={16} /><select id="location" value={place.name} onChange={(event) => changePlace(event.target.value)}>{places.map((item) => <option key={item.name}>{item.name}</option>)}</select></div>
          <div className="coord-line"><Crosshair size={13} /> {center[1].toFixed(3)}° N, {Math.abs(center[0]).toFixed(3)}° {center[0] < 0 ? 'W' : 'E'}</div>
          <p className="map-hint">Select a region, or click the map to reposition the sample area.</p>

          <div className="control-divider" />
          <label className="field-label" htmlFor="event">CHANGE LAYER</label>
          <div className="select-wrap"><SelectedIcon size={16} /><select id="event" value={changeType} onChange={(event) => changeLayer(event.target.value)}>{changeOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>

          <div className="control-divider" />
          <div className="field-label">OBSERVATION WINDOW</div>
          <div className="date-fields">
            <label>BEFORE<input type="date" value={startDate} max={endDate} onChange={(event) => setStartDate(event.target.value)} /></label>
            <ArrowDownRight size={15} className="date-arrow" />
            <label>AFTER<input type="date" value={endDate} min={startDate} onChange={(event) => setEndDate(event.target.value)} /></label>
          </div>
          <div className="timeline-label"><Clock3 size={14} /> TEMPORAL COMPARISON</div>
          <div className="timeline"><span /> <i /></div>
          <div className="timeline-dates"><span>{dateLabel(startDate)}</span><span>{dateLabel(endDate)}</span></div>

          <div className="control-divider" />
          <button className="primary-button" onClick={analyze} disabled={busy !== null}>
            <Sparkles size={16} /> {busy === 'analysis' ? 'Analyzing…' : 'Run illustrative analysis'}
          </button>
          <button className="secondary-button" onClick={discover} disabled={busy !== null}>
            <Search size={16} /> {busy === 'search' ? 'Searching CMR…' : 'Find NASA observations'}
          </button>
          <div className="data-foot"><Database size={14} /><span>NASA CMR metadata<br /><b>Raster analysis not connected</b></span></div>
        </aside>

        <section className="map-stage" aria-label="Map and analysis workspace">
          <div className="map-topline"><div><span className="map-eyebrow">SELECTED REGION</span><strong>{customCenter ? 'Custom map location' : place.name}</strong></div><span className="aoi-chip"><i /> AOI SAMPLE</span></div>
          <MapView center={center} onSelect={(point) => setCustomCenter(point)} />
          <div className="map-legend"><span><i className="legend-area" /> Illustrative {selectedOption.label.toLowerCase()} extent</span><span><i className="legend-point" /> Selected area</span></div>
          {observations && <div className="observation-panel">
            <div className="observation-heading"><Radio size={15} /><strong>NASA CMR DISCOVERY</strong><button onClick={() => setObservations(null)} aria-label="Close observation results">×</button></div>
            {observations.length ? observations.slice(0, 3).map((item, index) => <article className="observation-item" key={`${item.collection_id}-${index}`}><b>{item.title}</b><span>{item.start_date ? dateLabel(item.start_date.slice(0, 10)) : 'Date unavailable'}{item.collection_id ? ` · ${item.collection_id}` : ''}</span></article>) : <p className="empty-observations">No matching granule metadata found for this area and date range.</p>}
          </div>}
        </section>

        <aside className="insight-rail">
          <div className="insight-header"><div><span className="section-kicker">CHANGE SUMMARY</span><h2>{selectedOption.label}</h2></div><span className="event-icon"><SelectedIcon size={19} /></span></div>
          <div className="simulation-banner"><span /> ILLUSTRATIVE SCENARIO · NOT SATELLITE-DERIVED</div>
          <div className="metric-primary"><span>ESTIMATED AREA AFFECTED</span><div>{result.affected_area_km2.toFixed(1)}<small> km²</small></div><p>{result.change_percent >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />} {Math.abs(result.change_percent).toFixed(1)}% sample {result.change_percent >= 0 ? 'increase' : 'decrease'}</p></div>
          <div className="metric-grid">
            <div className="metric-cell"><span>CONFIDENCE</span><strong>{Math.round(result.confidence * 100)}<small>%</small></strong><div className="confidence-track"><i style={{ width: `${result.confidence * 100}%` }} /></div></div>
            <div className="metric-cell"><span>RISK INDICATOR</span><strong className="risk-value"><ShieldAlert size={17} /> {result.risk_level.toUpperCase()}</strong><small className="metric-disclaimer">Prototype score</small></div>
          </div>
          <div className="insight-section">
            <div className="section-heading"><span>OBSERVATION PAIR</span><Layers2 size={15} /></div>
            <div className="pair-row"><div className="pair-tile before-tile"><span>BASELINE</span><strong>{new Date(`${startDate}T00:00:00`).getUTCFullYear()}</strong><small>Illustrative</small></div><div className="pair-connector"><ArrowUpRight size={15} /></div><div className="pair-tile after-tile"><span>COMPARISON</span><strong>{new Date(`${endDate}T00:00:00`).getUTCFullYear()}</strong><small>Illustrative</small></div></div>
          </div>
          <div className="insight-section explanation-section">
            <div className="section-heading"><span>FIELD NOTE</span><Sparkles size={14} /></div>
            <p>{result.explanation}</p>
            <span className="source-note">{result.source_label}</span>
          </div>
          <div className="risk-note"><ShieldAlert size={16} /><p><b>Not an official warning.</b> This prototype indicator is illustrative and should not guide emergency decisions.</p></div>
          {notice && <div className="status-note" role="status">{notice}</div>}
          <div className="data-source"><span>DATA DISCOVERY</span><b><span className="nasa-dot">N</span> NASA EARTHDATA · CMR</b><small>Observation metadata only</small></div>
        </aside>
      </section>
      <footer className="footer-bar"><span><i /> SYSTEM READY</span><span>EARTH OBSERVATION PROTOTYPE <b>·</b> v0.1</span><span><Activity size={13} /> {result.is_simulated ? 'SAMPLE DATA' : 'ANALYSIS'}</span></footer>
    </main>
  );
}