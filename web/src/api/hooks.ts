/** react-query hooks over the API client. Site metadata is cached for the session. */

import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

const forever = { staleTime: Infinity, gcTime: Infinity } as const;

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: api.health, retry: 3, ...forever });

export const useSites = (enabled = true) =>
  useQuery({ queryKey: ["sites"], queryFn: api.sites, enabled, ...forever });

export const useLayers = (site: string | null) =>
  useQuery({ queryKey: ["layers", site], queryFn: () => api.layers(site!), enabled: !!site, ...forever });

export const useStats = (site: string | null) =>
  useQuery({ queryKey: ["stats", site], queryFn: () => api.stats(site!), enabled: !!site, ...forever });

export const useValidation = (site: string | null) =>
  useQuery({ queryKey: ["validation", site], queryFn: () => api.validation(site!), enabled: !!site, ...forever });

export const usePoint = (site: string | null, pt: [number, number] | null) =>
  useQuery({
    queryKey: ["point", site, pt?.[0], pt?.[1]],
    queryFn: () => api.point(site!, pt![0], pt![1]),
    enabled: !!site && !!pt,
    retry: false,
  });

export const usePolygonStats = (site: string | null, polygon: GeoJSON.Polygon | null) =>
  useQuery({
    queryKey: ["polygon", site, polygon ? JSON.stringify(polygon.coordinates) : null],
    queryFn: () => api.polygonStats(site!, polygon!),
    enabled: !!site && !!polygon,
    retry: false,
  });

export const useScenes = (polygon: GeoJSON.Polygon | null) =>
  useQuery({
    queryKey: ["scenes", polygon ? JSON.stringify(polygon.coordinates) : null],
    queryFn: () => api.scenes(polygon!),
    enabled: !!polygon,
    retry: false,
    staleTime: 3_600_000,
  });
