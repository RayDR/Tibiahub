import { BookOpen, Eye, Loader2, Package } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import '../../i18n/questEnhancements';
import { itemsApi, questsApi } from '../../services/api';
import type { ItemDetail, QuestDetail, QuestItemValue, QuestNamedValue, QuestRelationship } from '../../types';
import { availableItemMediaUrl } from '../../utils/entityMedia';
import { Dialog } from '../ui/Overlay';

const normalizeName = (value: string) => value.trim().toLocaleLowerCase();

const itemCache = new Map<string, Promise<ItemDetail | null>>();
const questCache = new Map<string, Promise<QuestDetail | null>>();

async function resolveLocalItem(name: string, preferredIdentifier?: string): Promise<ItemDetail | null> {
  const cacheKey = `${preferredIdentifier || ''}:${normalizeName(name)}`;
  const existing = itemCache.get(cacheKey);
  if (existing) return existing;

  const lookup = (async () => {
    if (preferredIdentifier) {
      try {
        return await itemsApi.getByIdentifier(preferredIdentifier);
      } catch {
        // Continue with an exact local catalog lookup. Never accept a fuzzy result.
      }
    }
    try {
      const results = await itemsApi.search(name, 12);
      const exact = results.filter((row) => normalizeName(row.item_name) === normalizeName(name));
      if (exact.length !== 1) return null;
      const identifier = exact[0].slug || exact[0].id;
      return identifier != null ? await itemsApi.getByIdentifier(identifier) : null;
    } catch {
      return null;
    }
  })();
  itemCache.set(cacheKey, lookup);
  return lookup;
}

async function resolveLocalQuest(name: string, preferredIdentifier?: string): Promise<QuestDetail | null> {
  const cacheKey = `${preferredIdentifier || ''}:${normalizeName(name)}`;
  const existing = questCache.get(cacheKey);
  if (existing) return existing;

  const lookup = (async () => {
    if (preferredIdentifier) {
      try {
        return await questsApi.getById(preferredIdentifier);
      } catch {
        // Continue with exact canonical-name matching only.
      }
    }
    try {
      const results = await questsApi.search(name, 12);
      const exact = results.filter((row) => normalizeName(row.name) === normalizeName(name));
      if (exact.length !== 1) return null;
      const identifier = exact[0].slug || exact[0].id;
      return identifier != null ? await questsApi.getById(identifier) : null;
    } catch {
      return null;
    }
  })();
  questCache.set(cacheKey, lookup);
  return lookup;
}

function exactRelationship(
  name: string,
  relationships: QuestRelationship[],
  targetTypes: string[],
): QuestRelationship | undefined {
  const normalized = normalizeName(name);
  return relationships.find((relationship) => (
    relationship.resolution_status === 'resolved'
    && Boolean(relationship.target_slug)
    && targetTypes.includes(relationship.target_entity_type)
    && normalizeName(relationship.target_name) === normalized
  ));
}

interface QuestReferenceProps {
  value: QuestNamedValue | QuestItemValue;
  kind: 'item' | 'quest';
  relationships: QuestRelationship[];
  linkState?: unknown;
  previewable?: boolean;
  compact?: boolean;
}

export default function QuestReference({
  value,
  kind,
  relationships,
  linkState,
  previewable = true,
  compact = false,
}: QuestReferenceProps) {
  const { t } = useTranslation();
  const resolved = useMemo(
    () => exactRelationship(value.name, relationships, kind === 'item' ? ['item'] : ['quest']),
    [kind, relationships, value.name],
  );
  const [item, setItem] = useState<ItemDetail | null>(null);
  const [questTarget, setQuestTarget] = useState<QuestDetail | null>(null);
  const [targetLoading, setTargetLoading] = useState(true);
  const [imageFailed, setImageFailed] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);

  useEffect(() => {
    let current = true;
    setTargetLoading(true);
    setImageFailed(false);

    const request = kind === 'item'
      ? resolveLocalItem(value.name, resolved?.target_slug)
      : resolveLocalQuest(value.name, resolved?.target_slug);

    void request.then((result) => {
      if (!current) return;
      if (kind === 'item') {
        setItem(result as ItemDetail | null);
        setQuestTarget(null);
      } else {
        setQuestTarget(result as QuestDetail | null);
        setItem(null);
      }
    }).finally(() => {
      if (current) setTargetLoading(false);
    });

    return () => { current = false; };
  }, [kind, resolved?.target_slug, value.name]);

  const amount = 'amount' in value ? value.amount : 1;
  const itemIdentifier = item?.slug || item?.id || resolved?.target_slug;
  const questIdentifier = questTarget?.slug || questTarget?.id || resolved?.target_slug;
  const route = kind === 'item'
    ? itemIdentifier != null ? `/items/${itemIdentifier}` : null
    : questIdentifier != null ? `/quests/${questIdentifier}` : null;
  const imageUrl = kind === 'item' ? availableItemMediaUrl(item?.media) : undefined;

  const content = (
    <>
      <span className={`grid shrink-0 place-items-center rounded-md ${compact ? 'size-7' : 'size-9'} quest-codex__reference-icon`}>
        {kind === 'item' && imageUrl && !imageFailed ? (
          <img
            src={imageUrl}
            alt=""
            className={`${compact ? 'size-6' : 'size-8'} object-contain [image-rendering:pixelated]`}
            onError={() => setImageFailed(true)}
          />
        ) : kind === 'item' ? (
          targetLoading ? <Loader2 className="size-4 animate-spin" /> : <Package className="size-4" />
        ) : targetLoading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <BookOpen className="size-4" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{value.name}</span>
        {amount > 1 ? <span className="block text-xs opacity-75">{t('questEnhancement.itemAmount', { amount })}</span> : null}
      </span>
    </>
  );

  return <>
    <div className={`quest-codex__reference flex items-center gap-2 rounded-lg border ${compact ? 'min-h-9 px-2 py-1.5 text-xs' : 'min-h-11 px-3 py-2 text-sm'}`}>
      {route ? (
        <Link to={route} state={linkState} className="flex min-w-0 flex-1 items-center gap-2 hover:underline">
          {content}
        </Link>
      ) : (
        <div className="flex min-w-0 flex-1 items-center gap-2">{content}</div>
      )}
      {previewable && route ? (
        <button
          type="button"
          onClick={() => setPreviewOpen(true)}
          className="app-button-ghost app-button-sm shrink-0 px-2"
          aria-label={t('questDetail.previewEntity', { name: value.name })}
        >
          <Eye className="size-4" />
        </button>
      ) : null}
    </div>

    {previewable && route ? (
      <Dialog
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        label={kind === 'item' ? t('questEnhancement.itemPreview') : t('questEnhancement.questPreview')}
        className="w-[min(92vw,32rem)] p-0"
      >
        <div className="border-b border-line p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            {kind === 'item' ? t('questDetail.entityTypes.item') : t('questDetail.entityTypes.quest')}
          </p>
          <div className="mt-2 flex items-center gap-3">
            {kind === 'item' && imageUrl && !imageFailed ? (
              <img src={imageUrl} alt="" className="size-14 object-contain [image-rendering:pixelated]" onError={() => setImageFailed(true)} />
            ) : null}
            <h3 className="text-xl font-bold text-content-primary">{value.name}</h3>
          </div>
        </div>
        <div className="p-5">
          {targetLoading ? (
            <div className="flex items-center gap-2 text-sm text-content-secondary">
              <Loader2 className="size-4 animate-spin" />
              {t('questEnhancement.loadingPreview')}
            </div>
          ) : kind === 'item' && item ? (
            <div className="space-y-2 text-sm text-content-secondary">
              {item.description ? <p className="leading-6">{item.description}</p> : <p>{t('questDetail.noCompactDetails')}</p>}
              <div className="flex flex-wrap gap-2 text-xs">
                {item.category ? <span className="ds-badge">{item.category}</span> : null}
                {item.item_type ? <span className="ds-badge">{item.item_type}</span> : null}
              </div>
            </div>
          ) : kind === 'quest' && questTarget ? (
            <div className="space-y-3 text-sm text-content-secondary">
              <p className="leading-6">{questTarget.summary || questTarget.description || t('questDetail.noCompactDetails')}</p>
              <div className="flex flex-wrap gap-2 text-xs">
                {questTarget.min_level != null ? <span className="ds-badge">{t('questDetail.minimumLevel')}: {questTarget.min_level}</span> : null}
                {questTarget.duration ? <span className="ds-badge">{t('questEnhancement.duration')}: {questTarget.duration}</span> : null}
              </div>
            </div>
          ) : (
            <p className="text-sm text-content-secondary">{t('questEnhancement.previewUnavailable')}</p>
          )}

          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={() => setPreviewOpen(false)} className="app-button-ghost app-button-sm">{t('common.close')}</button>
            <Link to={route} state={linkState} onClick={() => setPreviewOpen(false)} className="app-button-primary app-button-sm">{t('questDetail.openEntity')}</Link>
          </div>
        </div>
      </Dialog>
    ) : null}
  </>;
}
