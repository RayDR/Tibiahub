import { BookOpen, Eye, Loader2, Package } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import '../../i18n/questEnhancements';
import { itemsApi, questsApi } from '../../services/api';
import type { ItemDetail, QuestDetail, QuestItemValue, QuestNamedValue, QuestRelationship } from '../../types';
import { Dialog } from '../ui/Overlay';

const normalizeName = (value: string) => value.trim().toLocaleLowerCase();

const itemCache = new Map<string, Promise<ItemDetail | null>>();

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
  const [itemLoading, setItemLoading] = useState(kind === 'item');
  const [imageFailed, setImageFailed] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [questPreview, setQuestPreview] = useState<QuestDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewFailed, setPreviewFailed] = useState(false);

  useEffect(() => {
    if (kind !== 'item') return undefined;
    let current = true;
    setItemLoading(true);
    setImageFailed(false);
    void resolveLocalItem(value.name, resolved?.target_slug).then((result) => {
      if (current) setItem(result);
    }).finally(() => {
      if (current) setItemLoading(false);
    });
    return () => { current = false; };
  }, [kind, resolved?.target_slug, value.name]);

  const amount = 'amount' in value ? value.amount : 1;
  const itemIdentifier = item?.slug || item?.id || resolved?.target_slug;
  const route = kind === 'item'
    ? itemIdentifier != null ? `/items/${itemIdentifier}` : null
    : resolved?.target_slug ? `/quests/${resolved.target_slug}` : null;
  const imageUrl = kind === 'item' && item?.id != null
    ? `/api/v1/items/${item.id}/image?placeholder=false`
    : null;

  const openPreview = () => {
    if (!previewable || !route) return;
    setPreviewOpen(true);
    setPreviewFailed(false);
    if (kind === 'item' || questPreview || !resolved?.target_slug) return;
    setPreviewLoading(true);
    void questsApi.getById(resolved.target_slug)
      .then(setQuestPreview)
      .catch(() => setPreviewFailed(true))
      .finally(() => setPreviewLoading(false));
  };

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
          itemLoading ? <Loader2 className="size-4 animate-spin" /> : <Package className="size-4" />
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
          onClick={openPreview}
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
          {kind === 'item' && item ? (
            <div className="space-y-2 text-sm text-content-secondary">
              {item.description ? <p className="leading-6">{item.description}</p> : <p>{t('questDetail.noCompactDetails')}</p>}
              <div className="flex flex-wrap gap-2 text-xs">
                {item.category ? <span className="ds-badge">{item.category}</span> : null}
                {item.item_type ? <span className="ds-badge">{item.item_type}</span> : null}
              </div>
            </div>
          ) : kind === 'quest' ? (
            previewLoading ? <p className="text-sm text-content-secondary">{t('questEnhancement.loadingPreview')}</p>
              : questPreview ? <div className="space-y-3 text-sm text-content-secondary">
                <p className="leading-6">{questPreview.summary || questPreview.description || t('questDetail.noCompactDetails')}</p>
                <div className="flex flex-wrap gap-2 text-xs">
                  {questPreview.min_level != null ? <span className="ds-badge">{t('questDetail.minimumLevel')}: {questPreview.min_level}</span> : null}
                  {questPreview.duration ? <span className="ds-badge">{t('questEnhancement.duration')}: {questPreview.duration}</span> : null}
                </div>
              </div> : <p className="text-sm text-content-secondary">{t('questEnhancement.previewUnavailable')}</p>
          ) : previewFailed || !item ? (
            <p className="text-sm text-content-secondary">{t('questEnhancement.previewUnavailable')}</p>
          ) : null}

          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={() => setPreviewOpen(false)} className="app-button-ghost app-button-sm">{t('common.close')}</button>
            <Link to={route} state={linkState} onClick={() => setPreviewOpen(false)} className="app-button-primary app-button-sm">{t('questDetail.openEntity')}</Link>
          </div>
        </div>
      </Dialog>
    ) : null}
  </>;
}
