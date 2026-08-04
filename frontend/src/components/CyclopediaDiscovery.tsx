import type { TFunction } from 'i18next';
import type { LucideIcon } from 'lucide-react';
import {
  BookOpenCheck,
  Crown,
  Gem,
  MapPinned,
  Sparkles,
} from 'lucide-react';
import {
  useEffect,
  useMemo,
  useState,
} from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  type CyclopediaDiscovery as DiscoveryPayload,
  type DiscoveryCard,
  discoveryApi,
} from '../services/discovery';
import {
  buildLocalEntityMediaUrl,
} from '../utils/entityMedia';

type DiscoveryMode =
  | 'creatures'
  | 'bosses'
  | 'items'
  | 'quests'
  | 'zones';

type ContextKind =
  | 'creature'
  | 'boss'
  | 'item'
  | 'quest'
  | 'zone';

interface PrimaryPreview {
  id: string;
  name: string;
  subtitle: string;
  to: string;
  imageUrl?: string;
}

interface ContextCard {
  id: string;
  name: string;
  subtitle: string;
  to: string;
  imageUrl?: string;
  kind: ContextKind;
}

interface CyclopediaDiscoveryProps {
  mode: DiscoveryMode;
  primaryItems: PrimaryPreview[];
}

const fallbackIcons: Record<ContextKind, LucideIcon> = {
  creature: Sparkles,
  boss: Crown,
  item: Gem,
  quest: BookOpenCheck,
  zone: MapPinned,
};

const modeKinds: Record<DiscoveryMode, ContextKind> = {
  creatures: 'creature',
  bosses: 'boss',
  items: 'item',
  quests: 'quest',
  zones: 'zone',
};

const modeEntityTypes: Record<DiscoveryMode, string[]> = {
  creatures: ['creature'],
  bosses: ['boss'],
  items: ['item'],
  quests: ['quest'],
  zones: ['hunt_zone'],
};

const normalize = (value: string) =>
  value.trim().toLocaleLowerCase().replace(/\s+/g, ' ');

function contextualImageUrl(
  item: DiscoveryCard,
): string | undefined {
  const type = item.entity_type || '';

  if (type === 'creature' || type === 'boss') {
    return buildLocalEntityMediaUrl(
      type,
      item.id,
    );
  }

  if (type === 'item') {
    return buildLocalEntityMediaUrl(
      'item',
      item.id,
    );
  }

  if (type === 'hunt_zone') {
    return buildLocalEntityMediaUrl(
      'zone',
      item.id,
    );
  }

  return undefined;
}

function contextualLink(item: DiscoveryCard): string {
  const type = item.entity_type || '';

  const tab =
    type === 'quest'
      ? 'quests'
      : type === 'item'
        ? 'items'
        : type === 'hunt_zone'
          ? 'zones'
          : type === 'boss'
            ? 'bosses'
            : 'creatures';

  return (
    `/cyclopedia?tab=${tab}&q=` +
    encodeURIComponent(item.name)
  );
}

function contextualSubtitle(
  item: DiscoveryCard,
  t: TFunction,
): string {
  if (item.search_count) {
    return t('cyclopedia.discovery.searches', {
      count: item.search_count,
    });
  }

  if (item.summary) {
    return item.summary;
  }

  if (
    item.entity_type === 'hunt_zone' &&
    item.recommended_level
  ) {
    return `${item.city || t('common.unknown')} · ${t(
      'cyclopedia.zones.level',
      {
        level: item.recommended_level,
      },
    )}`;
  }

  return t(
    `cyclopedia.discovery.types.${item.entity_type}`,
    {
      defaultValue:
        item.entity_type || t('common.unknown'),
    },
  );
}

function relatedCards(
  data: DiscoveryPayload,
  mode: DiscoveryMode,
  primaryItems: PrimaryPreview[],
  t: TFunction,
): ContextCard[] {
  const expectedTypes = new Set(modeEntityTypes[mode]);

  const candidates: DiscoveryCard[] = [
    ...data.trending,
    ...data.latest_knowledge,
    ...(mode === 'quests'
      ? data.recent_quests.map((item) => ({
          ...item,
          entity_type: 'quest',
        }))
      : []),
    ...(mode === 'zones'
      ? data.popular_hunts.map((item) => ({
          ...item,
          entity_type: 'hunt_zone',
        }))
      : []),
    ...(mode === 'bosses' && data.boosted_boss
      ? [
          {
            ...data.boosted_boss,
            entity_type: 'boss',
          },
        ]
      : []),
  ];

  const primaryNames = new Set(
    primaryItems.map((item) => normalize(item.name)),
  );

  const seen = new Set<string>();
  const cards: ContextCard[] = [];

  for (const item of candidates) {
    const entityType = item.entity_type || '';

    if (!expectedTypes.has(entityType)) {
      continue;
    }

    const normalizedName = normalize(item.name);

    if (
      !normalizedName ||
      primaryNames.has(normalizedName)
    ) {
      continue;
    }

    const key = `${entityType}:${normalizedName}`;

    if (seen.has(key)) {
      continue;
    }

    seen.add(key);

    cards.push({
      id: `${entityType}:${item.id}`,
      name: item.name,
      subtitle: contextualSubtitle(item, t),
      to: contextualLink(item),
      imageUrl: contextualImageUrl(item),
      kind: modeKinds[mode],
    });

    if (cards.length >= 6) {
      break;
    }
  }

  return cards;
}

function primaryTitle(
  mode: DiscoveryMode,
  t: TFunction,
): string {
  if (mode === 'creatures') {
    return t('cyclopedia.discovery.featuredCreatures');
  }

  if (mode === 'quests') {
    return t('cyclopedia.discovery.recentQuests');
  }

  if (mode === 'zones') {
    return t('cyclopedia.discovery.popularHunts');
  }

  if (mode === 'bosses') {
    return t('nav.bosses');
  }

  return t('nav.loot');
}

function normalizePrimaryImage(
  imageUrl: string | undefined,
  mode: DiscoveryMode,
): string | undefined {
  if (!imageUrl) {
    return undefined;
  }

  if (
    (mode === 'creatures' ||
      mode === 'bosses' ||
      mode === 'items') &&
    !imageUrl.includes('placeholder=')
  ) {
    return `${imageUrl}?placeholder=false`;
  }

  return imageUrl;
}

function normalizePrimaryLink(
  item: PrimaryPreview,
  mode: DiscoveryMode,
): string {
  if (mode === 'items') {
    return (
      '/cyclopedia?tab=items&q=' +
      encodeURIComponent(item.name)
    );
  }

  if (mode === 'zones') {
    return (
      '/cyclopedia?tab=zones&q=' +
      encodeURIComponent(item.name)
    );
  }

  return item.to;
}

export default function CyclopediaDiscovery({
  mode,
  primaryItems,
}: CyclopediaDiscoveryProps) {
  const { t } = useTranslation();
  const [data, setData] =
    useState<DiscoveryPayload | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    void discoveryApi
      .load(controller.signal)
      .then((value) => {
        if (active) {
          setData(value);
        }
      })
      .catch(() => {
        if (active) {
          setData(null);
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  const primaryCards = useMemo<ContextCard[]>(
    () =>
      primaryItems.slice(0, 6).map((item) => ({
        id: item.id,
        name: item.name,
        subtitle: item.subtitle,
        to: normalizePrimaryLink(item, mode),
        imageUrl: normalizePrimaryImage(
          item.imageUrl,
          mode,
        ),
        kind: modeKinds[mode],
      })),
    [mode, primaryItems],
  );

  const related = useMemo(
    () =>
      data
        ? relatedCards(data, mode, primaryItems, t)
        : [],
    [data, mode, primaryItems, t],
  );

  if (
    primaryCards.length === 0 &&
    related.length === 0
  ) {
    return null;
  }

  return (
    <section
      className="mx-auto max-w-6xl space-y-4"
      aria-label={t('cyclopedia.discovery.label')}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
            {t(
              mode === 'items'
                ? 'nav.loot'
                : `nav.${mode}`,
            )}
          </p>
          <h2 className="mt-1 text-xl font-semibold text-content-primary">
            {primaryTitle(mode, t)}
          </h2>
        </div>
      </div>

      <div
        className={`grid gap-4 ${
          related.length
            ? 'lg:grid-cols-[minmax(0,1.35fr)_minmax(18rem,.65fr)]'
            : ''
        }`}
      >
        {primaryCards.length ? (
          <ContextGroup
            items={primaryCards}
            columns="wide"
          />
        ) : null}

        {related.length ? (
          <ContextGroup
            title={t('cyclopedia.discovery.trending')}
            items={related}
            columns="compact"
          />
        ) : null}
      </div>
    </section>
  );
}

function ContextGroup({
  title,
  items,
  columns,
}: {
  title?: string;
  items: ContextCard[];
  columns: 'wide' | 'compact';
}) {
  return (
    <article className="rounded-2xl bg-surface-raised p-5 shadow-sm">
      {title ? (
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-content-secondary">
          {title}
        </h3>
      ) : null}

      <div
        className={
          columns === 'wide'
            ? 'grid gap-2 sm:grid-cols-2'
            : 'grid gap-2'
        }
      >
        {items.map((item) => (
          <Link
            key={item.id}
            to={item.to}
            className="group flex min-w-0 items-center gap-3 rounded-xl bg-surface p-3 transition hover:bg-surface-active"
          >
            <ContextMedia item={item} />

            <span className="min-w-0">
              <strong className="block truncate text-sm text-content-primary">
                {item.name}
              </strong>
              <span className="line-clamp-1 text-xs text-content-muted">
                {item.subtitle}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </article>
  );
}

function ContextMedia({
  item,
}: {
  item: ContextCard;
}) {
  const Icon = fallbackIcons[item.kind];
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [item.imageUrl]);

  return (
    <span className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-xl bg-primary/10 text-primary">
      {item.imageUrl && !failed ? (
        <img
          src={item.imageUrl}
          alt=""
          aria-hidden="true"
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="size-11 object-contain p-0.5 [image-rendering:pixelated]"
        />
      ) : (
        <Icon className="size-5" aria-hidden="true" />
      )}
    </span>
  );
}
