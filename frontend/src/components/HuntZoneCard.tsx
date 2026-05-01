import React from 'react';
import { Link } from 'react-router-dom';
import type { HuntZone } from '../types';

interface HuntZoneCardProps {
  zone: HuntZone;
}

const HuntZoneCard: React.FC<HuntZoneCardProps> = ({ zone }) => {
  const getVocationIcons = () => {
    const vocations = [];
    if (zone.knights_recommended) vocations.push('⚔️');
    if (zone.paladins_recommended) vocations.push('🏹');
    if (zone.sorcerers_recommended) vocations.push('🔥');
    if (zone.druids_recommended) vocations.push('🌿');
    return vocations;
  };

  const getDifficultyColor = (difficulty?: string) => {
    switch (difficulty) {
      case 'Easy':
        return 'text-green-400';
      case 'Medium':
        return 'text-yellow-400';
      case 'Hard':
        return 'text-orange-400';
      case 'Extreme':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  };

  return (
    <Link to={`/hunt-zone/${zone.id}`}>
      <div className="tibia-panel p-6 hover:border-tibia-lightgold transition-all cursor-pointer">
        <div className="space-y-4">
          {/* Zone name and city */}
          <div>
            <h3 className="text-tibia-gold text-lg font-bold mb-1">
              {zone.name}
            </h3>
            {zone.city && (
              <p className="text-sm text-gray-400">
                Near {zone.city}
              </p>
            )}
          </div>

          {/* Level range */}
          <div className="flex items-center space-x-2 text-sm">
            <span className="text-gray-400">Level:</span>
            <span className="text-tibia-lightgold font-bold">
              {zone.min_level} - {zone.max_level || '∞'}
            </span>
            {zone.recommended_level && (
              <span className="text-green-400 text-xs">
                (Rec: {zone.recommended_level})
              </span>
            )}
          </div>

          {/* Difficulty */}
          {zone.difficulty && (
            <div className="flex items-center space-x-2 text-sm">
              <span className="text-gray-400">Difficulty:</span>
              <span className={`font-bold ${getDifficultyColor(zone.difficulty)}`}>
                {zone.difficulty}
              </span>
            </div>
          )}

          {/* Vocations */}
          <div className="flex items-center space-x-2">
            <span className="text-gray-400 text-sm">Vocations:</span>
            <div className="flex space-x-1">
              {getVocationIcons().map((icon, idx) => (
                <span key={idx} className="text-xl">
                  {icon}
                </span>
              ))}
            </div>
          </div>

          {/* Experience and Profit */}
          <div className="grid grid-cols-2 gap-4 text-xs">
            {zone.avg_exp_hour && (
              <div>
                <p className="text-gray-400">Exp/hour:</p>
                <p className="text-blue-400 font-bold">
                  {zone.avg_exp_hour.toLocaleString()}
                </p>
              </div>
            )}
            {zone.avg_profit_hour !== undefined && (
              <div>
                <p className="text-gray-400">Profit/hour:</p>
                <p className={`font-bold ${zone.avg_profit_hour > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {zone.avg_profit_hour.toLocaleString()}k
                </p>
              </div>
            )}
          </div>

          {/* Requirements */}
          {(zone.requires_quest || zone.requires_premium) && (
            <div className="flex flex-wrap gap-2 text-xs">
              {zone.requires_premium && (
                <span className="px-2 py-1 bg-tibia-gold text-tibia-darkbrown rounded">
                  Premium
                </span>
              )}
              {zone.requires_quest && (
                <span className="px-2 py-1 bg-tibia-blue text-white rounded">
                  Quest Required
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
};

export default HuntZoneCard;
