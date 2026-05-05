import React from 'react';
import { Link } from 'react-router-dom';
import { CreatureSimple } from '../types';
import { Heart, Star } from 'lucide-react';

interface CreatureCardProps {
  creature: CreatureSimple;
  index: number;
}

const CreatureCard: React.FC<CreatureCardProps> = ({ creature, index }) => {
  // Staggered animation delay
  const style = { animationDelay: `${index * 50}ms` };
  const creaturePath = creature.slug || String(creature.id);

  return (
    <Link
      to={`/creatures/${creaturePath}`}
      className="group relative bg-slate-900/40 border border-slate-700/50 rounded-xl overflow-hidden hover:border-amber-500/50 hover:shadow-lg hover:shadow-amber-500/10 transition-all duration-300 flex flex-col animate-fade-in-up"
      style={style}
    >
      {/* Glow Effect on Hover */}
      <div className="absolute inset-0 bg-gradient-to-b from-amber-500/0 to-amber-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

      {/* Image Container */}
      <div className="h-48 w-full bg-slate-950/50 relative flex items-center justify-center p-4 overflow-hidden">
        {creature.image_url ? (
          <img
            src={`/api/v1/creatures/${creature.id}/image`}
            alt={creature.name}
            className="w-32 h-32 object-contain filter drop-shadow-[0_0_10px_rgba(0,0,0,0.5)] group-hover:scale-110 transition-transform duration-500"
            loading="lazy"
          />
        ) : (
          <div className="text-6xl opacity-20 filter grayscale group-hover:grayscale-0 transition-all">
            🐉
          </div>
        )}

        {/* Difficulty Badge */}
        {creature.difficulty && (
          <div className={`absolute top-3 right-3 px-2 py-1 rounded text-xs font-bold uppercase tracking-wider
            ${creature.difficulty === 'Hard' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
              creature.difficulty === 'Medium' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            }
          `}>
            {creature.difficulty}
          </div>
        )}

        {creature.is_boss && (
          <div className="absolute top-3 left-3 rounded border border-red-500/40 bg-red-500/20 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-red-300">
            Boss
          </div>
        )}
      </div>

      {/* Info Body */}
      <div className="p-4 flex-1 flex flex-col relative">
        <h3 className="text-lg font-bold text-slate-100 group-hover:text-amber-400 transition-colors mb-4 font-serif">
          {creature.name}
        </h3>

        {creature.classification && (
          <div className="mb-3 inline-flex rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-cyan-300">
            {creature.classification}
          </div>
        )}

        {creature.is_boss && creature.related_tasks && creature.related_tasks.length > 0 && (
          <div className="mb-3 line-clamp-2 rounded-lg border border-amber-500/20 bg-amber-500/10 px-2.5 py-2 text-[11px] text-amber-200">
            Req: {creature.related_tasks[0]}
          </div>
        )}

        <div className="space-y-3 mt-auto">
          {/* Stats Grid */}
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-2 text-slate-400 bg-slate-950/30 p-2 rounded">
              <Heart className="w-4 h-4 text-rose-500" />
              <span className="font-mono">{creature.hitpoints.toLocaleString()}</span>
            </div>
            <div className="flex items-center gap-2 text-slate-400 bg-slate-950/30 p-2 rounded">
              <Star className="w-4 h-4 text-amber-400" />
              <span className="font-mono">{creature.experience.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>
    </Link>
  );
};

export default CreatureCard;
