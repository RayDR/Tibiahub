export interface MapSelectionResult {
  canonical_entity_id?: string | null;
  entity_type: string;
  slug?: string | null;
}

export interface RequestedMapSelection {
  canonicalEntityId: string | null;
  entityType: string | null;
  slug: string | null;
}

export function requestedMapSelection(params: URLSearchParams): RequestedMapSelection | null {
  const canonicalEntityId = params.get('entity')?.trim() || null;
  const slug = params.get('slug')?.trim() || null;
  if (!canonicalEntityId && !slug) return null;
  return {
    canonicalEntityId,
    entityType: params.get('entityType')?.trim() || null,
    slug,
  };
}

export function resolveMapSearchSelection<T extends MapSelectionResult>(
  results: readonly T[],
  requested: RequestedMapSelection | null,
): T | null {
  if (!requested) return results[0] || null;
  return results.find((row) => (
    (!requested.entityType || row.entity_type === requested.entityType)
    && (!requested.canonicalEntityId || row.canonical_entity_id === requested.canonicalEntityId)
    && (!requested.slug || row.slug === requested.slug)
  )) || null;
}

export function markersForMapMode<
  TLayerMarkers extends readonly unknown[],
  TSelectedMarkers extends readonly unknown[],
>(
  isolated: boolean,
  layerMarkers: TLayerMarkers,
  selectedMarkers: TSelectedMarkers,
): Array<TLayerMarkers[number] | TSelectedMarkers[number]> {
  return isolated ? [...selectedMarkers] : [...layerMarkers];
}
