import {
  ArrowUpRight,
  Banknote,
  BookOpenCheck,
  CircleEllipsis,
  Compass,
  FlaskConical,
  Info,
  MapPin,
  PackageOpen,
  ScrollText,
  Shield,
  ShoppingCart,
  Sparkles,
  Swords,
  UtensilsCrossed,
} from 'lucide-react';
import { useEffect, useMemo, useState, type ComponentType } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import type { NpcDirectoryItem } from '../types';
import { localNpcMediaUrl } from '../utils/npcCyclopedia';
import BrandCategoryFallbackIcon from './icons/BrandCategoryFallbackIcon';
import { useOptionalCyclopediaPreviewSelection } from './cyclopedia/CyclopediaPreviewSelectionContext';
import './NpcCard.css';

interface NpcCardProps {
  npc: NpcDirectoryItem;
  linkState?: unknown;
  onNavigate?: () => void;
}

type NpcServiceKind =
  | 'trade'
  | 'potions'
  | 'banking'
  | 'depot'
  | 'travel'
  | 'quests'
  | 'blessings'
  | 'food'
  | 'hunting'
  | 'tasks'
  | 'runes'
  | 'weapons'
  | 'armor'
  | 'ammunition'
  | 'information'
  | 'service';

interface NpcServiceDefinition {
  kind: NpcServiceKind;
  label: string;
  tooltip: string;
  Icon: ComponentType<{ className?: string }>;
}

function NpcPortrait({ npc, large = false }: { npc: NpcDirectoryItem; large?: boolean }) {
  const mediaUrl = localNpcMediaUrl(npc.media);
  const [failed, setFailed] = useState(false);

  useEffect(() => setFailed(false), [mediaUrl]);

  return (
    <span className={large ? 'npc-card-portrait npc-card-portrait--large' : 'grid size-20 shrink-0 place-items-center overflow-hidden rounded-xl bg-primary/[0.07] text-primary'}>
      {mediaUrl && !failed ? (
        <img
          src={mediaUrl}
          alt=""
          aria-hidden="true"
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className={large ? 'npc-card-portrait__image [image-rendering:pixelated]' : 'max-h-20 max-w-full object-contain p-1 [image-rendering:pixelated]'}
        />
      ) : (
        <BrandCategoryFallbackIcon category="npcs" className={large ? 'size-14 opacity-80' : 'size-8'} />
      )}
    </span>
  );
}

function inferNpcServices(
  npc: NpcDirectoryItem,
  labels: Record<string, string>,
): NpcServiceDefinition[] {
  const values: NpcServiceDefinition[] = [];
  const seen = new Set<NpcServiceKind>();
  const context = `${npc.title || ''} ${npc.occupation || ''}`.toLowerCase();
  const tradeCount = (npc.buys_count || 0) + (npc.sells_count || 0);

  const add = (
    kind: NpcServiceKind,
    label: string,
    tooltip: string,
    Icon: NpcServiceDefinition['Icon'],
  ) => {
    if (seen.has(kind)) return;
    seen.add(kind);
    values.push({ kind, label, tooltip, Icon });
  };

  if (tradeCount > 0) add('trade', labels.trade, labels.tradeTip, ShoppingCart);
  if (/potion|alchemi|chemist|herbal/.test(context)) add('potions', labels.potions, labels.potionsTip, FlaskConical);
  if (/bank|banker/.test(context)) add('banking', labels.banking, labels.bankingTip, Banknote);
  if (/depot/.test(context)) add('depot', labels.depot, labels.depotTip, PackageOpen);
  if ((npc.destination_count || 0) > 0 || /ferryman|sailor|captain|teleport|transport/.test(context)) {
    add('travel', labels.travel, labels.travelTip, Compass);
  }
  if ((npc.quest_count || 0) > 0) add('quests', labels.quests, labels.questsTip, BookOpenCheck);
  if (/bless|priest|temple/.test(context)) add('blessings', labels.blessings, labels.blessingsTip, Sparkles);
  if (/food|cook|baker|tavern|innkeeper|bartender/.test(context)) add('food', labels.food, labels.foodTip, UtensilsCrossed);
  if (/hunt|hunter/.test(context)) add('hunting', labels.hunting, labels.huntingTip, Compass);
  if (/task/.test(context)) add('tasks', labels.tasks, labels.tasksTip, ScrollText);
  if (/rune/.test(context)) add('runes', labels.runes, labels.runesTip, Sparkles);
  if (/weapon|blacksmith|smith/.test(context)) add('weapons', labels.weapons, labels.weaponsTip, Swords);
  if (/armor|armour/.test(context)) add('armor', labels.armor, labels.armorTip, Shield);
  if (/ammunition|ammo|bowyer/.test(context)) add('ammunition', labels.ammunition, labels.ammunitionTip, Swords);
  if (/spy|inform|guide|scholar|teacher|trainer|librarian/.test(context)) {
    add('information', labels.information, labels.informationTip, Info);
  }

  if (!values.length && (npc.occupation || npc.title)) {
    add(
      'service',
      npc.occupation || npc.title || labels.service,
      labels.occupationTip,
      CircleEllipsis,
    );
  }

  return values;
}

export default function NpcCard({ npc, linkState, onNavigate }: NpcCardProps) {
  const { t } = useTranslation();
  const preview = useOptionalCyclopediaPreviewSelection();
  const isCyclopedia = Boolean(preview);
  const selected = preview?.selection?.kind === 'npc' && preview.selection.identifier === npc.canonical_id;

  const serviceLabels = useMemo(() => ({
    trade: t('npcDetail.trade'),
    tradeTip: t('npcCard.serviceTips.trade', { defaultValue: 'Trades items with players.' }),
    potions: t('npcCard.services.potions', { defaultValue: 'Potions' }),
    potionsTip: t('npcCard.serviceTips.potions', { defaultValue: 'Potion or alchemy service indicated by this NPC’s role.' }),
    banking: t('npcCard.services.banking', { defaultValue: 'Banking' }),
    bankingTip: t('npcCard.serviceTips.banking', { defaultValue: 'Banking service indicated by this NPC’s role.' }),
    depot: t('npcCard.services.depot', { defaultValue: 'Depot' }),
    depotTip: t('npcCard.serviceTips.depot', { defaultValue: 'Depot-related service indicated by this NPC’s role.' }),
    travel: t('npcCard.services.travel', { defaultValue: 'Travel' }),
    travelTip: t('npcCard.serviceTips.travel', { defaultValue: 'Offers travel or transportation.' }),
    quests: t('npcCard.services.quests', { defaultValue: 'Quests' }),
    questsTip: t('npcCard.serviceTips.quests', { defaultValue: 'Has known quest relationships.' }),
    blessings: t('npcCard.services.blessings', { defaultValue: 'Blessings' }),
    blessingsTip: t('npcCard.serviceTips.blessings', { defaultValue: 'Blessing or temple service indicated by this NPC’s role.' }),
    food: t('npcCard.services.food', { defaultValue: 'Food' }),
    foodTip: t('npcCard.serviceTips.food', { defaultValue: 'Food service indicated by this NPC’s role.' }),
    hunting: t('npcCard.services.hunting', { defaultValue: 'Hunting' }),
    huntingTip: t('npcCard.serviceTips.hunting', { defaultValue: 'Hunting-related service indicated by this NPC’s role.' }),
    tasks: t('npcCard.services.tasks', { defaultValue: 'Tasks' }),
    tasksTip: t('npcCard.serviceTips.tasks', { defaultValue: 'Task-related service indicated by this NPC’s role.' }),
    runes: t('npcCard.services.runes', { defaultValue: 'Runes' }),
    runesTip: t('npcCard.serviceTips.runes', { defaultValue: 'Rune-related service indicated by this NPC’s role.' }),
    weapons: t('npcCard.services.weapons', { defaultValue: 'Weapons' }),
    weaponsTip: t('npcCard.serviceTips.weapons', { defaultValue: 'Weapon-related service indicated by this NPC’s role.' }),
    armor: t('npcCard.services.armor', { defaultValue: 'Armor' }),
    armorTip: t('npcCard.serviceTips.armor', { defaultValue: 'Armor-related service indicated by this NPC’s role.' }),
    ammunition: t('npcCard.services.ammunition', { defaultValue: 'Ammunition' }),
    ammunitionTip: t('npcCard.serviceTips.ammunition', { defaultValue: 'Ammunition-related service indicated by this NPC’s role.' }),
    information: t('npcCard.services.information', { defaultValue: 'Information' }),
    informationTip: t('npcCard.serviceTips.information', { defaultValue: 'Information or guidance service indicated by this NPC’s role.' }),
    service: t('npcCard.services.service', { defaultValue: 'Service' }),
    occupationTip: t('npcCard.serviceTips.occupation', { defaultValue: 'NPC role or occupation.' }),
  }), [t]);

  if (!isCyclopedia) {
    return (
      <Link
        data-npc-card
        to={`/npcs/${npc.canonical_id}`}
        state={linkState}
        onClick={onNavigate}
        aria-label={npc.name}
        className="group flex h-full min-h-40 flex-col items-center justify-center rounded-xl border border-line bg-surface-base/70 p-3 text-center shadow-sm transition hover:-translate-y-0.5 hover:border-primary/60 hover:bg-surface-raised hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary motion-reduce:transform-none"
      >
        <NpcPortrait npc={npc} />
        <span className="mt-2 line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-content-primary">
          {npc.name}
        </span>
      </Link>
    );
  }

  const services = inferNpcServices(npc, serviceLabels);

  return (
    <article
      data-npc-card
      data-cyclopedia-npc-card="true"
      data-npc-identifier={npc.canonical_id}
      data-selected={selected ? 'true' : 'false'}
      className="npc-cyclopedia-card"
    >
      <button
        type="button"
        className="npc-cyclopedia-card__select"
        onClick={() => preview?.select({ kind: 'npc', identifier: npc.canonical_id })}
        aria-pressed={selected}
        aria-label={npc.name}
      >
        <div className="npc-cyclopedia-card__media">
          <NpcPortrait npc={npc} large />
          <span className="npc-cyclopedia-card__crest" aria-hidden="true">
            <Sparkles className="size-4" />
          </span>
        </div>

        <div className="npc-cyclopedia-card__identity">
          <strong className="npc-cyclopedia-card__name">{npc.name}</strong>
          <span className="npc-cyclopedia-card__location">
            <MapPin className="size-3.5 shrink-0" />
            <span>{npc.location_name || t('npcDetail.unknownLocation')}</span>
          </span>
        </div>

        {services.length ? (
          <div className="npc-cyclopedia-card__services" aria-label={t('npcPreview.services', { defaultValue: 'Services' })}>
            {services.slice(0, 2).map(({ kind, label, tooltip, Icon }) => (
              <span
                key={kind}
                className="npc-service-chip"
                data-service={kind}
                title={tooltip}
                aria-label={`${label}: ${tooltip}`}
              >
                <Icon className="size-3.5 shrink-0" />
                <span>{label}</span>
              </span>
            ))}
          </div>
        ) : null}
      </button>

      <Link
        to={`/npcs/${npc.canonical_id}`}
        state={linkState}
        onClick={onNavigate}
        className="npc-cyclopedia-card__details"
        aria-label={t('npcDirectory.card.open')}
        title={t('npcDirectory.card.open')}
      >
        <ArrowUpRight className="size-3.5" />
      </Link>
    </article>
  );
}
