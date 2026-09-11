import React, { useEffect } from 'react';
import { ArrowRight, Flame, MapPin, Sword } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { CreatureSimple } from '../types';
import ImageWithFallback from './ImageWithFallback';
import BrandCategoryFallbackIcon from './icons/BrandCategoryFallbackIcon';
import { useBoostedCreature } from './cyclopedia/BoostedCreatureContext';
import { useCreatureBrowser } from './cyclopedia/CreatureBrowserContext';

interface CreatureCardProps {
  creature: CreatureSimple;
  index: number;
  linkState?: unknown;
  onNavigate?: () => void;
}

const difficultyClass = (difficulty?: string | null) => {
  const value = (difficulty || '').toLowerCase();
  if (value.includes('hard') || value.includes('extreme') || value.includes('challeng')) return 'creature-difficulty creature-difficulty-danger';
  if (value.includes('medium')) return 'creature-difficulty creature-difficulty-warning';
  return 'creature-difficulty creature-difficulty-success';
};

const CreatureCard: React.FC<CreatureCardProps> = ({
  creature,
  index,
  linkState,
  onNavigate,
}) => {
  const { t } = useTranslation();
  const location = useLocation();
  const browser = useCreatureBrowser();
  const boosted = useBoostedCreature();
  const enriched = browser?.browseItem(creature.id);
  const selected = browser?.selectedCreatureId === creature.id;
  const isBoosted = boosted?.isBoosted(creature) ?? false;
  const creaturePath = creature.slug || String(creature.id);
  const resolvedLinkState = linkState ?? { from: `${location.pathname}${location.search}` };

  useEffect(() => {
    browser?.registerCreature(creature.id);
  }, [browser, creature.id]);

  const select = () => {
    browser?.selectCreature(creature.id);
  };

  const activate = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      select();
    }
  };

  const bestiary = enriched?.bestiary_level || creature.classification || creature.difficulty || '—';
  const type = enriched?.primary_type || enriched?.creature_class || creature.classification;
  const locationPreview = enriched?.location_preview;
  const loot = enriched?.loot_preview || [];

  return (
    <article
      className="creature-browser-card group"
      data-selected={selected ? 'true' : 'false'}
      data-boosted={isBoosted ? 'true' : 'false'}
      data-creature-card
      data-creature-id={creature.id}
      data-entity-kind={creature.is_boss ? 'boss' : 'creature'}
      role={browser ? 'button' : undefined}
      tabIndex={browser ? 0 : undefined}
      aria-pressed={browser ? selected : undefined}
      onClick={select}
      onKeyDown={activate}
      style={{
        animationDelay: `${Math.min(index, 10) * 35}ms`,
        order: isBoosted ? -1 : undefined,
      }}
    >
      {isBoosted ? (
        <span className="creature-boosted-badge" title={t('home.boosted.badge')}>
          <Flame className="size-3.5" aria-hidden="true" />
          {t('home.boosted.badge')}
        </span>
      ) : null}

      <span className="creature-card-corner creature-card-corner-start"><BrandCategoryFallbackIcon category={creature.is_boss ? 'bosses' : 'creatures'} className="size-4" /></span>
      <Link
        to={`/creatures/${creaturePath}`}
        state={resolvedLinkState}
        onClick={(event) => {
          event.stopPropagation();
          onNavigate?.();
        }}
        className="creature-card-open"
        aria-label={`Open full details for ${creature.name}`}
        title="Open full details"
      ><ArrowRight className="size-4" /></Link>

      <div className="creature-card-media">
        <ImageWithFallback
          src={`/api/v1/creatures/${creature.id}/image?placeholder=false`}
          alt={creature.name}
          className="size-full object-contain [image-rendering:pixelated] transition-transform duration-300 group-hover:scale-105"
          containerClassName="size-full"
          fallbackLabel={`${creature.is_boss ? 'Boss' : 'Creature'} image unavailable: ${creature.name}`}
          fallbackKind={creature.is_boss ? 'boss' : 'creature'}
        />
      </div>

      <div className="creature-card-body">
        <div className="flex min-w-0 items-center gap-2">
          <h3 className="min-w-0 flex-1 truncate font-serif text-lg font-semibold text-content-primary">{creature.name}</h3>
          {creature.difficulty ? <span className={difficultyClass(creature.difficulty)}>{creature.difficulty}</span> : null}
        </div>

        <div className="creature-card-stats">
          <CardStat label="Bestiary" value={bestiary} />
          <CardStat label="XP" value={creature.experience?.toLocaleString() ?? '—'} />
          <CardStat label="HP" value={creature.hitpoints?.toLocaleString() ?? '—'} />
        </div>

        <div className="creature-card-meta">
          <span className="min-w-0"><Sword className="size-4 shrink-0 text-primary" /><span className="truncate">{type || 'Unknown type'}</span></span>
          <span className="min-w-0"><MapPin className="size-4 shrink-0 text-content-muted" /><span className="truncate">{locationPreview?.name || 'Location unknown'}</span></span>
        </div>

        <div className="creature-card-loot" aria-label="Loot highlights">
          {loot.length ? loot.map((item) => (
            <div key={item.id} className="creature-card-loot-row">
              <ImageWithFallback src={item.media.url} alt="" className="size-6 object-contain [image-rendering:pixelated]" containerClassName="grid size-7 shrink-0 place-items-center" fallbackKind="item" fallbackLabel={item.item_name} />
              <span className="min-w-0 flex-1 truncate">{item.item_name}</span>
            </div>
          )) : (
            <div className="creature-card-loot-empty">Loot details loading…</div>
          )}
        </div>
      </div>
    </article>
  );
};

function CardStat({ label, value }: { label: string; value: string }) {
  return <div className="creature-card-stat"><span>{label}</span><strong>{value}</strong></div>;
}

export default CreatureCard;
