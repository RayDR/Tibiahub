import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import DataSyncPanel from './DataSyncPanel';

interface CreatureForm {
  name: string;
  hitpoints: number;
  experience: number;
  armor: number;
  speed: number;
  difficulty: string;
  level_min: number;
  level_max?: number;
  description?: string;
  image_url?: string;
}

const AdminPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'creatures' | 'zones' | 'sync'>('creatures');
  const [formData, setFormData] = useState<CreatureForm>({
    name: '',
    hitpoints: 100,
    experience: 50,
    armor: 10,
    speed: 100,
    difficulty: 'Easy',
    level_min: 1,
    description: '',
    image_url: ''
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const response = await fetch('/api/v1/admin/creatures/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        alert('✅ Criatura creada exitosamente!');
        setFormData({
          name: '',
          hitpoints: 100,
          experience: 50,
          armor: 10,
          speed: 100,
          difficulty: 'Easy',
          level_min: 1,
          description: '',
          image_url: ''
        });
        navigate('/');
      } else {
        alert('❌ Error al crear criatura');
      }
    } catch (error) {
      console.error('Error:', error);
      alert('❌ Error de conexión');
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'hitpoints' || name === 'experience' || name === 'armor' || name === 'speed' || name === 'level_min' || name === 'level_max'
        ? parseInt(value) || 0
        : value
    }));
  };

  return (
    <div className="min-h-screen py-6 sm:py-12 px-3 sm:px-4">
      <div className="container mx-auto max-w-4xl">
        {/* Header */}
        <div className="text-center mb-8 sm:mb-12 ds-enter">
          <h1 className="text-3xl sm:text-5xl font-bold mb-3 sm:mb-4 bg-gradient-to-r from-accent via-accent to-accent bg-clip-text text-transparent">
            ⚙️ Admin Panel
          </h1>
          <p className="text-content-secondary text-base sm:text-lg">Gestiona criaturas y zonas de hunt</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 sm:gap-4 mb-6 sm:mb-8 justify-center">
          <button
            onClick={() => setActiveTab('creatures')}
            className={`px-4 sm:px-8 py-2 sm:py-3 rounded-xl font-semibold transition-all duration-300 text-sm sm:text-base ${activeTab === 'creatures'
                ? 'bg-gradient-to-r from-primary-hover to-primary-active text-content-on-primary shadow-lg'
                : 'bg-surface/80 border-2 border-line text-content-primary hover:border-primary'
              }`}
          >
            <span className="hidden xs:inline">🐉 Criaturas</span>
            <span className="xs:hidden">🐉</span>
          </button>
          <button
            onClick={() => setActiveTab('zones')}
            className={`px-4 sm:px-8 py-2 sm:py-3 rounded-xl font-semibold transition-all duration-300 text-sm sm:text-base ${activeTab === 'zones'
                ? 'bg-gradient-to-r from-primary-hover to-primary-active text-content-on-primary shadow-lg'
                : 'bg-surface/80 border-2 border-line text-content-primary hover:border-primary'
              }`}
          >
            <span className="hidden xs:inline">🗺️ Zonas</span>
            <span className="xs:hidden">🗺️</span>
          </button>
          <button
            onClick={() => setActiveTab('sync')}
            className={`px-4 sm:px-8 py-2 sm:py-3 rounded-xl font-semibold transition-all duration-300 text-sm sm:text-base ${activeTab === 'sync'
                ? 'bg-gradient-to-r from-primary-hover to-primary-active text-content-on-primary shadow-lg'
                : 'bg-surface/80 border-2 border-line text-content-primary hover:border-info'
              }`}
          >
            <span className="hidden xs:inline">🔄 Sincronización</span>
            <span className="xs:hidden">🔄</span>
          </button>
        </div>

        {/* Form Card */}
        {activeTab === 'creatures' && (
          <div className="card ds-enter">
            <h2 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6 text-primary">Crear Nueva Criatura</h2>

            <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-6">
              {/* Información Básica */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    Nombre *
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleInputChange}
                    required
                    placeholder="Ej: Dragon"
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    URL de Imagen (Sprite)
                  </label>
                  <input
                    type="url"
                    name="image_url"
                    value={formData.image_url}
                    onChange={handleInputChange}
                    placeholder="https://tibiawiki.dev/images/Dragon.gif"
                    className="w-full"
                  />
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    HP *
                  </label>
                  <input
                    type="number"
                    name="hitpoints"
                    value={formData.hitpoints}
                    onChange={handleInputChange}
                    required
                    min="1"
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    EXP *
                  </label>
                  <input
                    type="number"
                    name="experience"
                    value={formData.experience}
                    onChange={handleInputChange}
                    required
                    min="1"
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    Armor
                  </label>
                  <input
                    type="number"
                    name="armor"
                    value={formData.armor}
                    onChange={handleInputChange}
                    min="0"
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    Speed
                  </label>
                  <input
                    type="number"
                    name="speed"
                    value={formData.speed}
                    onChange={handleInputChange}
                    min="0"
                    className="w-full"
                  />
                </div>
              </div>

              {/* Level & Difficulty */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    Nivel Mínimo *
                  </label>
                  <input
                    type="number"
                    name="level_min"
                    value={formData.level_min}
                    onChange={handleInputChange}
                    required
                    min="1"
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    Nivel Máximo
                  </label>
                  <input
                    type="number"
                    name="level_max"
                    value={formData.level_max || ''}
                    onChange={handleInputChange}
                    min="1"
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-content-secondary mb-2">
                    Dificultad *
                  </label>
                  <select
                    name="difficulty"
                    value={formData.difficulty}
                    onChange={handleInputChange}
                    required
                    className="w-full"
                  >
                    <option value="Trivial">Trivial</option>
                    <option value="Easy">Easy</option>
                    <option value="Medium">Medium</option>
                    <option value="Hard">Hard</option>
                    <option value="Extreme">Extreme</option>
                  </select>
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-semibold text-content-secondary mb-2">
                  Descripción
                </label>
                <textarea
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  rows={4}
                  placeholder="Descripción de la criatura..."
                  className="w-full resize-none"
                />
              </div>

              {/* Submit Button */}
              <div className="flex gap-4 pt-4">
                <button
                  type="submit"
                  className="app-button-primary flex-1"
                >
                  ✨ Crear Criatura
                </button>
                <button
                  type="button"
                  onClick={() => navigate('/')}
                  className="px-8 py-3 bg-surface-raised hover:bg-surface-hover rounded-xl font-semibold transition-all"
                >
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        )}

        {activeTab === 'zones' && (
          <div className="card text-center py-20 ds-enter">
            <div className="text-6xl mb-4">🗺️</div>
            <h3 className="text-2xl font-bold text-content-secondary mb-2">
              Gestión de Zonas de Hunt
            </h3>
            <p className="text-content-secondary">
              Próximamente: formulario para crear y editar zonas de hunt
            </p>
          </div>
        )}

        {activeTab === 'sync' && (
          <DataSyncPanel />
        )}

        {/* Info Card */}
        <div className="mt-8 card bg-gradient-to-r from-accent/30 to-info/30 border-accent/30">
          <h3 className="text-xl font-bold text-accent mb-4">💡 Datos Reales de Tibia</h3>
          <ul className="space-y-2 text-content-secondary">
            <li>✅ Usa sprites oficiales de TibiaWiki: <code className="text-primary">https://tibiawiki.dev/images/[Name].gif</code></li>
            <li>✅ Consulta <a href="https://tibiawiki.dev" target="_blank" rel="noopener noreferrer" className="text-info hover:underline">TibiaWiki.dev</a> para stats reales</li>
            <li>✅ Winter Update 2025: Soporte completo para vocación Monk 🧘</li>
            <li>✅ Script de importación: <code className="text-primary">python import_tibiawiki.py --manual</code></li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default AdminPage;
