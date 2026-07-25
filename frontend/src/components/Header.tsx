import React from 'react';
import { Link } from 'react-router-dom';

const Header: React.FC = () => {
  return (
    <header className="ds-panel mb-8">
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center space-x-4">
            <h1 className="text-2xl md:text-3xl text-primary">
              Tibia Cyclopedia
            </h1>
          </Link>

          <nav className="hidden md:flex space-x-6">
            <Link
              to="/"
              className="text-primary hover:text-content-primary transition-colors text-sm"
            >
              Creatures
            </Link>
            <Link
              to="/hunt-zones"
              className="text-primary hover:text-content-primary transition-colors text-sm"
            >
              Hunt Zones
            </Link>
            <Link
              to="/recommendations"
              className="text-primary hover:text-content-primary transition-colors text-sm"
            >
              Hunt Finder
            </Link>
          </nav>

          {/* Mobile menu button */}
          <button className="app-button-secondary app-button-sm md:hidden">
            Menu
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
