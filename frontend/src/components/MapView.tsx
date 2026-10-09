import { useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';

maplibregl.setWorkerUrl(workerUrl);

interface MapViewProps {
  center: [number, number];
  onSelect: (center: [number, number]) => void;
}

const sourceId = 'sample-aoi';

function aoiFeature(center: [number, number]): GeoJSON.Feature<GeoJSON.Polygon> {
  const [longitude, latitude] = center;
  const offset = 0.11;
  return {
    type: 'Feature',
    properties: {},
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [longitude - offset, latitude - offset * 0.7],
        [longitude + offset, latitude - offset * 0.7],
        [longitude + offset, latitude + offset * 0.7],
        [longitude - offset, latitude + offset * 0.7],
        [longitude - offset, latitude - offset * 0.7],
      ]],
    },
  };
}

export default function MapView({ center, onSelect }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center,
      zoom: 8.3,
      attributionControl: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left');
    map.on('load', () => {
      map.addSource(sourceId, { type: 'geojson', data: aoiFeature(center) });
      map.addLayer({
        id: 'sample-aoi-fill',
        type: 'fill',
        source: sourceId,
        paint: { 'fill-color': '#d45f47', 'fill-opacity': 0.2 },
      });
      map.addLayer({
        id: 'sample-aoi-line',
        type: 'line',
        source: sourceId,
        paint: { 'line-color': '#c34835', 'line-width': 2.2, 'line-dasharray': [2, 1.5] },
      });
      markerRef.current = new maplibregl.Marker({ color: '#bf4b35' }).setLngLat(center).addTo(map);
    });
    map.on('click', (event: MapMouseEvent) => onSelectRef.current([event.lngLat.lng, event.lngLat.lat]));
    mapRef.current = map;
    return () => {
      markerRef.current?.remove();
      markerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({ center, duration: 900 });
    markerRef.current?.setLngLat(center);
    const source = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined;
    source?.setData(aoiFeature(center));
  }, [center]);

  return <div className="map-canvas" ref={containerRef} aria-label="Interactive map of the selected area" />;
}