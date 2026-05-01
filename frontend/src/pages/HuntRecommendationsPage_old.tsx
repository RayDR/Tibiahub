import React, { useState } from 'react';
import { huntZonesApi } from '../services/api';
import HuntZoneCard from '../components/HuntZoneCard';
import Loading from '../components/Loading';
import ErrorMessage from '../components/ErrorMessage';
import type { HuntRecommendation, Vocation } from '../types';

const HuntRecommendationsPage: React.FC = () => {
  const [recommendations, setRecommendations] = useState<HuntRecommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vocation, setVocation] = useState<Vocation>('knight');
  const [level, setLevel] = useState<number>(50);

  const fetchRecommendations = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await huntZonesApi.getRecommendations(vocation, level);
      setRecommendations(data);
    } catch (err) {
      setError('Failed to load recommendations. Please try again later.');
      console.error('Error fetching recommendations:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchRecommendations();
  };

  return (
    <div className="space-y-6">
      {/* Hunt Finder Form */}
      <div className="tibia-panel p-8">
        <h1 className="text-tibia-gold text-3xl font-bold mb-6">
          Hunt Zone Finder
        </h1>
        <p className="text-tibia-lightgold mb-6">
          Find the best hunting zones for your character!
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Vocation selector */}
            <div>
              <label className="block text-tibia-gold font-bold mb-3">
                Select Your Vocation
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setVocation('knight')}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    vocation === 'knight'
                      ? 'border-tibia-gold bg-tibia-green text-white'
                      : 'border-tibia-green text-tibia-lightgold hover:border-tibia-lightgold'
                  }`}
                >
                  <div className="text-3xl mb-2">⚔️</div>
                  <div className="text-sm font-bold">Knight</div>
                </button>

                <button
                  type="button"
                  onClick={() => setVocation('paladin')}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    vocation === 'paladin'
                      ? 'border-tibia-gold bg-tibia-green text-white'
                      : 'border-tibia-green text-tibia-lightgold hover:border-tibia-lightgold'
                  }`}
                >
                  <div className="text-3xl mb-2">🏹</div>
                  <div className="text-sm font-bold">Paladin</div>
                </button>

                <button
                  type="button"
                  onClick={() => setVocation('sorcerer')}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    vocation === 'sorcerer'
                      ? 'border-tibia-gold bg-tibia-green text-white'
                      : 'border-tibia-green text-tibia-lightgold hover:border-tibia-lightgold'
                  }`}
                >
                  <div className="text-3xl mb-2">🔥</div>
                  <div className="text-sm font-bold">Sorcerer</div>
                </button>

                <button
                  type="button"
                  onClick={() => setVocation('druid')}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    vocation === 'druid'
                      ? 'border-tibia-gold bg-tibia-green text-white'
                      : 'border-tibia-green text-tibia-lightgold hover:border-tibia-lightgold'
                  }`}
                >
                  <div className="text-3xl mb-2">🌿</div>
                  <div className="text-sm font-bold">Druid</div>
                </button>

                <button
                  type="button"
                  onClick={() => setVocation('monk')}
                  className={`p-4 rounded-lg border-2 transition-all col-span-2 ${
                    vocation === 'monk'
                      ? 'border-tibia-gold bg-tibia-green text-white'
                      : 'border-tibia-green text-tibia-lightgold hover:border-tibia-lightgold'
                  }`}
                >
                  <div className="text-3xl mb-2">🧘</div>
                  <div className="text-sm font-bold">Monk (Winter Update 2025)</div>
                </button>
              </div>
            </div>

            {/* Level input */}
            <div>
              <label className="block text-tibia-gold font-bold mb-3">
                Your Level: {level}
              </label>
              <input
                type="range"
                min="1"
                max="500"
                value={level}
                onChange={(e) => setLevel(parseInt(e.target.value))}
                className="w-full h-3 bg-tibia-darkgreen rounded-lg appearance-none cursor-pointer accent-tibia-gold"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-2">
                <span>Level 1</span>
                <span>Level 500</span>
              </div>
              
              <div className="mt-4">
                <input
                  type="number"
                  min="1"
                  max="2000"
                  value={level}
                  onChange={(e) => setLevel(parseInt(e.target.value) || 1)}
                  className="w-full px-4 py-3 bg-tibia-darkgreen border-2 border-tibia-green text-tibia-lightgold rounded focus:border-tibia-gold focus:outline-none text-center text-xl font-bold"
                />
              </div>
            </div>
          </div>

          <button type="submit" className="tibia-button w-full md:w-auto px-12 py-4 text-lg">
            Find Best Hunts
          </button>
        </form>
      </div>

      {/* Loading state */}
      {loading && <Loading message="Finding best hunt zones..." />}

      {/* Error state */}
      {error && <ErrorMessage message={error} onRetry={fetchRecommendations} />}

      {/* Results */}
      {!loading && !error && recommendations.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-tibia-gold text-2xl font-bold">
            Recommended Hunt Zones ({recommendations.length})
          </h2>
          <p className="text-tibia-lightgold text-sm">
            Zones are ranked by suitability for a level {level} {vocation}
          </p>

          <div className="space-y-6">
            {recommendations.map((rec, index) => (
              <div key={rec.zone.id} className="space-y-3">
                {/* Rank badge */}
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center font-bold text-xl ${
                    index === 0 ? 'bg-yellow-600 text-white' :
                    index === 1 ? 'bg-gray-400 text-white' :
                    index === 2 ? 'bg-orange-600 text-white' :
                    'bg-tibia-green text-tibia-gold'
                  }`}>
                    #{index + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-tibia-gold font-bold">
                        Score: {rec.score.toFixed(0)}/100
                      </span>
                      <div className="flex-1 bg-tibia-darkgreen rounded-full h-3 overflow-hidden">
                        <div 
                          className="bg-gradient-to-r from-tibia-green to-tibia-gold h-full transition-all"
                          style={{ width: `${rec.score}%` }}
                        />
                      </div>
                    </div>
                    {rec.reasons.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {rec.reasons.map((reason, idx) => (
                          <span 
                            key={idx}
                            className="text-xs px-2 py-1 bg-tibia-darkbrown text-tibia-lightgold rounded"
                          >
                            ✓ {reason}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Zone card */}
                <HuntZoneCard zone={rec.zone} />

                {/* Main creatures */}
                {rec.creatures.length > 0 && (
                  <div className="tibia-panel p-4">
                    <h4 className="text-tibia-gold font-bold mb-3 text-sm">
                      Main Creatures:
                    </h4>
                    <div className="flex flex-wrap gap-3">
                      {rec.creatures.map((creature) => (
                        <div 
                          key={creature.id}
                          className="px-3 py-2 bg-tibia-darkbrown rounded border border-tibia-green"
                        >
                          <span className="text-tibia-lightgold text-xs font-bold">
                            {creature.name}
                          </span>
                          <span className="text-gray-400 text-xs ml-2">
                            ({creature.experience} exp)
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No results */}
      {!loading && !error && recommendations.length === 0 && (
        <div className="tibia-panel p-12 text-center">
          <p className="text-gray-400 text-lg">
            Click "Find Best Hunts" to get zone recommendations!
          </p>
        </div>
      )}
    </div>
  );
};

export default HuntRecommendationsPage;
