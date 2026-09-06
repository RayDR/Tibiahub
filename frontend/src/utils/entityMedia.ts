import type { ItemMedia } from '../types';

export type LocalMediaEntityKind =
  | 'creature'
  | 'boss'
  | 'zone';

export type EntityIdentifier =
  | string
  | number
  | null
  | undefined;

/**
 * Resolve numeric database identifiers from values such as:
 *
 * 25
 * "25"
 * "creature:25"
 * "boss:25"
 * "item:103"
 * "hunt_zone:8"
 *
 * Non-numeric identifiers deliberately return null so the UI can
 * fall back to its entity icon without requesting an invalid URL.
 */
export function extractNumericEntityId(
  value: EntityIdentifier,
): number | null {
  if (typeof value === 'number') {
    return Number.isSafeInteger(value) && value > 0
      ? value
      : null;
  }

  if (typeof value !== 'string') {
    return null;
  }

  const raw = value.trim();

  if (!raw) {
    return null;
  }

  const tail = raw.includes(':')
    ? raw.slice(raw.lastIndexOf(':') + 1)
    : raw;

  if (!/^\d+$/.test(tail)) {
    return null;
  }

  const parsed = Number(tail);

  return Number.isSafeInteger(parsed) && parsed > 0
    ? parsed
    : null;
}

export function buildLocalEntityMediaUrl(
  kind: LocalMediaEntityKind,
  identifier: EntityIdentifier,
): string | undefined {
  const id = extractNumericEntityId(identifier);

  if (id === null) {
    return undefined;
  }

  if (kind === 'creature' || kind === 'boss') {
    return (
      `/api/v1/creatures/${id}/image` +
      '?placeholder=false'
    );
  }

  return `/api/v1/hunt-zones/${id}/map-image`;
}

export function availableItemMediaUrl(
  media: ItemMedia | null | undefined,
): string | undefined {
  if (
    media?.status !== 'available'
    || !media.url
    || !media.url.startsWith('/api/v1/items/')
    || !media.url.includes('placeholder=false')
  ) {
    return undefined;
  }
  return media.url;
}
