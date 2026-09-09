import { useEffect, useState } from 'react';
import { ArrowRight, ExternalLink, MapPin, Sparkles, Sword } from 'lucide-react';
import { Link } from 'react-router-dom';

import ImageWithFallback from '../ImageWithFallback';
import { creatureBrowserApi, type CreatureCombatModifier, type CreaturePreview } from '../../services/creatureBrowser';

const difficultyClass = (difficulty?: string | null) => {
  const value = (difficulty || '').toLowerCase();
  if (value.includes('hard') || value.includes('extreme') || value.includes('challeng')) return 'creature-difficulty creature-difficulty-danger';
  if (value.includes('medium')) return 'creature-difficulty creature-difficulty-warning';
  return 'creature-difficulty creature-difficulty-success';
};

const modifierValue = (modifier: CreatureCombatModifier) => {
  if (modifier.delta_percent == null) return '—';
  const value = modifier.delta_percent;
  return `${value > 0 ? '+' : ''}${value}%`;
};

export default function CreaturePreviewPanel({ creatureId }: { creatureId: number }) {
  const [preview, setPreview] = useState<CreaturePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    void creatureBrowserApi.getPreview(creatureId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setPreview(data);
      })
      .catch((error: any) => {
        if (error?.name !== 'CanceledError' && error?.code !== 'ERR_CANCELED') {
          setFailed(true);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [creatureId]);

  if (loading && !preview) {
    return <div className="creature-preview-panel creature-preview-loading" role="status"><div className="ds-skeleton h-40 w-full" /><div className="ds-skeleton h-6 w-2/3" /><div className="ds-skeleton h-24 w-full" /></div>;
  }

  if (failed || !preview) {
    return <div className="creature-preview-panel grid min-h-64 place-items-center text-center text-sm text-content-muted">Creature preview unavailable.</div>;
  }

  const mainLocation = preview.locations[0];
  const tags = [preview.classification, preview.bestiary_class, preview.creature_class, preview.primary_type].filter(Boolean).slice(0, 3) as string[];

  return (
    <article className="creature-preview-panel" aria-label={`${preview.name} preview`}>
      <div className="creature-preview-identity">
        <div className="creature-preview-sprite">
          <ImageWithFallback
            src={preview.image_url}
            alt={preview.name}
            className="size-full object-contain [image-rendering:pixelated]"
            containerClassName="size-full"
            fallbackKind="creature"
            fallbackLabel={`${preview.name} image unavailable`}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="creature-preview-name">{preview.name}</h2>
              {preview.difficulty ? <span className={difficultyClass(preview.difficulty)}>{preview.difficulty}</span> : null}
            </div>
            <span className="shrink-0 text-xs text-content-muted">TH #{preview.id}</span>
          </div>
          {tags.length ? <div className="mt-3 flex flex-wrap gap-1.5">{tags.map((tag) => <span key={tag} className="creature-preview-chip">{tag}</span>)}</div> : null}
          {preview.description ? <p className="mt-3 line-clamp-5 text-sm leading-relaxed text-content-secondary">{preview.description}</p> : null}
        </div>
      </div>

      <div className="creature-preview-stats">
        <PreviewStat label="Bestiary" value={preview.bestiary_level || preview.difficulty || '—'} />
        <PreviewStat label="Experience" value={preview.experience?.toLocaleString() ?? '—'} />
        <PreviewStat label="Hit Points" value={preview.hitpoints?.toLocaleString() ?? '—'} />
      </div>

      <div className="creature-preview-columns">
        <section>
          <h3 className="creature-preview-section-title"><Sword className="size-4 text-primary" />Elemental modifiers</h3>
          <div className="creature-preview-list">
            {preview.combat_modifiers.length ? preview.combat_modifiers.slice(0, 7).map((modifier) => (
              <div key={`${modifier.kind}-${modifier.name}`} className="creature-preview-row">
                <span className="truncate">{modifier.name}</span>
                <span className={modifier.kind === 'weakness' ? 'text-danger' : 'text-info'}>{modifierValue(modifier)}</span>
              </div>
            )) : <p className="py-3 text-xs text-content-muted">No documented modifiers.</p>}
          </div>
        </section>

        <section>
          <h3 className="creature-preview-section-title"><Sparkles className="size-4 text-primary" />Loot highlights <span className="text-content-muted">({preview.loot.length})</span></h3>
          <div className="creature-preview-list">
            {preview.loot.slice(0, 5).map((loot) => (
              <div key={loot.id} className="creature-preview-loot-row">
                <ImageWithFallback src={loot.media.url} alt="" className="size-7 object-contain [image-rendering:pixelated]" containerClassName="grid size-8 shrink-0 place-items-center" fallbackKind="item" fallbackLabel={loot.item_name} />
                <span className="min-w-0 flex-1 truncate">{loot.item_name}</span>
                <span className="text-xs text-content-muted">{loot.percentage != null ? `${loot.percentage.toLocaleString()}%` : loot.rarity || ''}</span>
              </div>
            ))}
          </div>
          <Link to={`/creatures/${preview.slug || preview.id}`} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-hover">View full loot and details <ArrowRight className="size-3.5" /></Link>
        </section>
      </div>

      {mainLocation ? (
        <section className="creature-preview-location">
          <div className="min-w-0 flex-1 p-4">
            <h3 className="creature-preview-section-title"><MapPin className="size-4 text-primary" />Common location</h3>
            <Link to={`/hunt-zones/${mainLocation.slug || mainLocation.id}`} className="mt-2 block truncate font-serif text-lg font-semibold text-primary hover:text-primary-hover">{mainLocation.name}</Link>
            <p className="text-xs text-content-muted">{mainLocation.region || mainLocation.city || ''}</p>
          </div>
          {mainLocation.map_image_url ? <div className="creature-preview-map"><ImageWithFallback src={mainLocation.map_image_url} alt={`${mainLocation.name} map`} className="size-full object-cover" containerClassName="size-full" fallbackKind="zone" fallbackLabel={`${mainLocation.name} map unavailable`} /><Link to={`/hunt-zones/${mainLocation.slug || mainLocation.id}`} aria-label={`Open ${mainLocation.name}`} className="absolute right-2 top-2 grid size-8 place-items-center rounded-md border border-line bg-surface-overlay/90 text-content-primary"><ExternalLink className="size-4" /></Link></div> : null}
        </section>
      ) : null}

      {preview.behavior ? (
        <section className="creature-preview-notes">
          <h3 className="creature-preview-section-title"><Sparkles className="size-4 text-primary" />Combat notes</h3>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-content-secondary">{preview.behavior}</p>
        </section>
      ) : null}

      <Link to={`/creatures/${preview.slug || preview.id}`} className="creature-preview-full-link">Open full creature entry <ArrowRight className="size-4" /></Link>
    </article>
  );
}

function PreviewStat({ label, value }: { label: string; value: string }) {
  return <div className="creature-preview-stat"><span>{label}</span><strong>{value}</strong></div>;
}
