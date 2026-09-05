import { useEffect } from 'react';

export interface SeoBreadcrumb { name: string; path: string; }
export interface SeoMetadata {
  title: string;
  description: string;
  canonicalPath: string;
  noIndex?: boolean;
  type?: 'website' | 'article';
  image?: string;
  breadcrumbs?: SeoBreadcrumb[];
}

const SITE_NAME = 'TibiaHub';

function absoluteUrl(path: string): string {
  const origin = typeof window === 'undefined' ? 'https://tibiahub.domoforge.com' : window.location.origin;
  return new URL(path, `${origin}/`).toString();
}

function meta(selector: string, attributes: Record<string, string>, content: string): void {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement('meta');
    Object.entries(attributes).forEach(([key, value]) => element!.setAttribute(key, value));
    document.head.appendChild(element);
  }
  element.content = content;
}

export function applySeoMetadata(metadata: SeoMetadata): void {
  const canonical = absoluteUrl(metadata.canonicalPath);
  const fullTitle = metadata.title.includes(SITE_NAME) ? metadata.title : `${metadata.title} | ${SITE_NAME}`;
  document.title = fullTitle;
  meta('meta[name="description"]', { name: 'description' }, metadata.description);
  meta('meta[name="robots"]', { name: 'robots' }, metadata.noIndex ? 'noindex, nofollow' : 'index, follow');
  meta('meta[property="og:title"]', { property: 'og:title' }, fullTitle);
  meta('meta[property="og:description"]', { property: 'og:description' }, metadata.description);
  meta('meta[property="og:url"]', { property: 'og:url' }, canonical);
  meta('meta[property="og:type"]', { property: 'og:type' }, metadata.type || 'website');
  const image = metadata.image ? absoluteUrl(metadata.image) : absoluteUrl('/assets/logo/tibiahub.png');
  meta('meta[property="og:image"]', { property: 'og:image' }, image);

  let canonicalLink = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!canonicalLink) {
    canonicalLink = document.createElement('link');
    canonicalLink.rel = 'canonical';
    document.head.appendChild(canonicalLink);
  }
  canonicalLink.href = canonical;

  document.getElementById('tibiahub-breadcrumb-jsonld')?.remove();
  if (metadata.breadcrumbs?.length) {
    const script = document.createElement('script');
    script.id = 'tibiahub-breadcrumb-jsonld';
    script.type = 'application/ld+json';
    script.text = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: metadata.breadcrumbs.map((entry, index) => ({
        '@type': 'ListItem', position: index + 1, name: entry.name, item: absoluteUrl(entry.path),
      })),
    });
    document.head.appendChild(script);
  }
}

export function useSeoMetadata(metadata: SeoMetadata | null): void {
  useEffect(() => {
    if (metadata) applySeoMetadata(metadata);
  }, [metadata]);
}

export function defaultSeoForPath(pathname: string): SeoMetadata {
  if (pathname === '/') return { title: 'Tibia guides, hunts and Cyclopedia', description: 'Explore Tibia creatures, items, quests, hunt zones, routes and player tools with TibiaHub.', canonicalPath: '/' };
  if (pathname === '/cyclopedia') return { title: 'Tibia Cyclopedia', description: 'Browse TibiaHub knowledge about creatures, bosses, items, quests, hunt zones and NPCs.', canonicalPath: '/cyclopedia', breadcrumbs: [{ name: 'Home', path: '/' }, { name: 'Cyclopedia', path: '/cyclopedia' }] };
  if (pathname === '/map') return { title: 'Interactive Tibia Map', description: 'Search local TibiaHub knowledge and explore mapped hunt zones, creatures, quests, and locations.', canonicalPath: '/map', breadcrumbs: [{ name: 'Home', path: '/' }, { name: 'Map', path: '/map' }] };
  const publicDetail = /^\/(creatures|items|quests|hunt-zones|npcs|locations)\/[^/]+$/.test(pathname);
  if (publicDetail) return { title: 'Tibia knowledge entry', description: 'Explore this Tibia knowledge entry in TibiaHub.', canonicalPath: pathname, type: 'article' };
  return { title: 'TibiaHub', description: 'TibiaHub player and community tools.', canonicalPath: pathname, noIndex: true };
}
