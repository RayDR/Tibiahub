import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { CreatureSimple } from '../types';
import { Heart, Star } from 'lucide-react';
import ImageWithFallback from './ImageWithFallback';

interface CreatureCardProps {
  creature: CreatureSimple;
  index: number;
  linkState?: unknown;
  onNavigate?: () => void;
}

const CreatureCard: React.FC<CreatureCardProps> = ({
  creature,
  index,
  linkState,
  onNavigate,
}) => {
  const location = useLocation();
  // Staggered animation delay
  const style = { animationDelay: `${index * 50}ms` };
  const creaturePath = creature.slug || String(creature.id);

  return (
    <Link
      to={`/creatures/${creaturePath}`}
      state={
        linkState ?? {
          from: `${location.pathname}${location.search}`,
        }
      }
      onClick={() => onNavigate?.()}
      className="group relative bg-surface-base/40 border border-line/50 rounded-xl overflow-hidden hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10 transition-all duration-300 flex flex-col animate-fade-in-up"
      style={style}
    >
      {/* Glow Effect on Hover */}
      <div className="absolute inset-0 bg-gradient-to-b from-primary/0 to-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

      {/* Image Container */}
      <div className="h-48 w-full bg-surface-base/50 relative flex items-center justify-center p-4 overflow-hidden">
        <ImageWithFallback
          src={`/api/v1/creatures/${creature.id}/image`}
          alt={creature.name}
          className="w-32 h-32 object-contain filter drop-shadow-lg group-hover:scale-110 transition-transform duration-500"
          containerClassName="w-32 h-32"
          fallbackLabel="Creature"
        />

        {/* Difficulty Badge */}
        {creature.difficulty && (
          <div className={`absolute top-3 right-3 px-2 py-1 rounded text-xs font-bold uppercase tracking-wider
            ${creature.difficulty === 'Hard' ? 'bg-danger/20 text-danger border border-danger/30' :
              creature.difficulty === 'Medium' ? 'bg-primary/20 text-primary border border-primary/30' :
                'bg-success/20 text-success border border-success/30'
            }
          `}>
            {creature.difficulty}
          </div>
        )}

        {creature.is_boss && (
          <div className="absolute top-3 left-3 rounded border border-danger/40 bg-danger/20 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-danger">
            Boss
          </div>
        )}
      </div>

      {/* Info Body */}
      <div className="p-4 flex-1 flex flex-col relative">
        <h3 className="text-lg font-bold text-content-primary group-hover:text-primary transition-colors mb-4 font-serif">
          {creature.name}
        </h3>

        {creature.classification && (
          <div className="mb-3 inline-flex rounded-full border border-info/30 bg-info/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-info">
            {creature.classification}
          </div>
        )}

        {creature.is_boss && creature.related_tasks && creature.related_tasks.length > 0 && (
          <div className="mb-3 line-clamp-2 rounded-lg border border-primary/20 bg-primary/10 px-2.5 py-2 text-[11px] text-primary">
            Req: {creature.related_tasks[0]}
          </div>
        )}

        <div className="space-y-3 mt-auto">
          {/* Stats Grid */}
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-2 text-content-secondary bg-surface-base/30 p-2 rounded">
              <Heart className="w-4 h-4 text-danger" />
              <span className="font-mono">{creature.hitpoints.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-2 text-content-secondary bg-surface-base/30 p-2 rounded">
              <Star className="w-4 h-4 text-primary" />
              <span className="font-mono">{creature.experience.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
};

export default CreatureCard;
