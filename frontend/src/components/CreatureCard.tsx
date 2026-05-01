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

  return (
    <Link
      to={`/creatures/${creature.id}`}
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
      </div>

      {/* Info Body */}
      <div className="p-4 flex-1 flex flex-col relative">
        <h3 className="text-lg font-bold text-slate-100 group-hover:text-amber-400 transition-colors mb-4 font-serif">
          {creature.name}
        </h3>

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
