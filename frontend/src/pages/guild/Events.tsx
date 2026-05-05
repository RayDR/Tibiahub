import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Calendar, Trophy, Users, Ticket, Gift, Plus, Trash2, ExternalLink, Loader2 } from 'lucide-react';
import { eventsApi, Event, EventCreate } from '../../services/events';
import { guildApi } from '../../services/guild';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { useSearchParams } from 'react-router-dom';

export const Events: React.FC = () => {
  useTranslation();
  const { user } = useAuth();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const initialFilter = (searchParams.get('type') as 'raffle' | 'contest' | 'hunt' | 'quest' | null) || 'all';
  const [filter, setFilter] = useState<'all' | 'raffle' | 'contest' | 'hunt' | 'quest'>(initialFilter);
  const [isDrawing, setIsDrawing] = useState(false);
  const [winnerNumber, setWinnerNumber] = useState<number | null>(null);
  const [winnerName, setWinnerName] = useState<string | null>(null);
  const [featureFlags, setFeatureFlags] = useState({
    guild_raffles_enabled: true,
    guild_contests_enabled: true,
  });
  const canManageEvents = Boolean(user?.is_superuser || ['leader', 'vice leader', 'guild leader', 'alpha warbringer', 'bloodhowl marshal'].includes((user?.guild_rank || '').toLowerCase()));
  const selectedGuild = (localStorage.getItem('selectedGuildName') || '').trim();
  const scopedGuild = user?.is_superuser
    ? (selectedGuild || user?.guild_name || 'Bloodborne Warhowl')
    : (user?.guild_name || undefined);

  useEffect(() => {
    const queryType = (searchParams.get('type') as 'raffle' | 'contest' | 'hunt' | 'quest' | null) || 'all';
    if (queryType !== filter) {
      setFilter(queryType);
    }
  }, [searchParams]);

  useEffect(() => {
    loadEvents();
  }, [filter, scopedGuild]);

  useEffect(() => {
    const loadFlags = async () => {
      try {
        const flags = await guildApi.getFeatureFlags();
        setFeatureFlags(flags);
      } catch {
        setFeatureFlags({ guild_raffles_enabled: true, guild_contests_enabled: true });
      }
    };
    void loadFlags();
  }, []);

  useEffect(() => {
    if (!featureFlags.guild_contests_enabled && filter === 'contest') {
      setFilter('all');
    }
    if (!featureFlags.guild_raffles_enabled && filter === 'raffle') {
      setFilter('all');
    }
  }, [featureFlags, filter]);

  const loadEvents = async () => {
    try {
      setLoading(true);
      const data = await eventsApi.getEvents('active', filter === 'all' ? undefined : filter, scopedGuild);
      setEvents(data);
    } catch (error) {
      console.error('Failed to load events:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateEvent = async (event: EventCreate) => {
    try {
      const payload: EventCreate = {
        ...event,
        guild_name: user?.is_superuser ? scopedGuild : (event.guild_name || user?.guild_name),
      };
      await eventsApi.createEvent(payload);
      setShowCreateModal(false);
      loadEvents();
      toast.success('Event created successfully!');
    } catch (error) {
      console.error('Failed to create event:', error);
      toast.error('Failed to create event');
    }
  };

  const handleJoinEvent = async (eventId: number) => {
    try {
      await eventsApi.joinEvent(eventId);
      loadEvents();
      if (selectedEvent && selectedEvent.id === eventId) {
        const updated = await eventsApi.getEvent(eventId);
        setSelectedEvent(updated);
      }
      toast.success('Successfully joined the event!');
    } catch (error: any) {
      toast.error(error.message || 'Failed to join event');
    }
  };

  const handleDrawWinner = async (eventId: number) => {
    try {
      setIsDrawing(true);
      setWinnerNumber(null);
      setWinnerName(null);

      // Simulate dice animation
      const animationDuration = 3000;
      const intervalTime = 100;
      const intervals = animationDuration / intervalTime;
      let count = 0;

      const event = events.find(e => e.id === eventId);
      if (!event) return;

      const interval = setInterval(() => {
        const randomNum = Math.floor(Math.random() * (event.total_slots || 100)) + 1;
        setWinnerNumber(randomNum);
        count++;

        if (count >= intervals) {
          clearInterval(interval);
        }
      }, intervalTime);

      // Draw the actual winner
      setTimeout(async () => {
        try {
          const result = await eventsApi.drawWinner(eventId);
          setWinnerNumber(result.winner_number || null);
          setWinnerName(result.winner_name);
          loadEvents();
          if (selectedEvent && selectedEvent.id === eventId) {
            const updated = await eventsApi.getEvent(eventId);
            setSelectedEvent(updated);
          }
        } catch (error: any) {
          toast.error(error.message || 'Failed to draw winner');
        } finally {
          setIsDrawing(false);
        }
      }, animationDuration);
    } catch (error) {
      setIsDrawing(false);
      console.error('Failed to draw winner:', error);
    }
  };

  const handleDeleteEvent = async (eventId: number) => {
    const confirmed = window.confirm('Are you sure you want to delete this event?');
    if (!confirmed) return;

    try {
      await eventsApi.deleteEvent(eventId);
      loadEvents();
      setShowDetailModal(false);
      setSelectedEvent(null);
      toast.success('Event deleted successfully');
    } catch (error) {
      console.error('Failed to delete event:', error);
      toast.error('Failed to delete event');
    }
  };

  const openEventDetail = async (event: Event) => {
    try {
      const detailed = await eventsApi.getEvent(event.id);
      setSelectedEvent(detailed);
      setShowDetailModal(true);
    } catch (error) {
      console.error('Failed to load event details:', error);
    }
  };

  const hasUserJoined = (event: Event) => {
    return event.participants.some(p => p.user_id === user?.id);
  };

  const getTypeMeta = (type: string) => {
    switch (type) {
      case 'raffle':
        return { label: 'Raffle', badge: 'bg-amber-900/30 text-amber-400 border-amber-700/50' };
      case 'contest':
        return { label: 'Contest', badge: 'bg-red-900/30 text-red-400 border-red-700/50' };
      case 'hunt':
      case 'hunt_event':
        return { label: 'Hunt', badge: 'bg-green-900/30 text-green-300 border-green-700/50' };
      case 'quest':
        return { label: 'Quest', badge: 'bg-indigo-900/30 text-indigo-300 border-indigo-700/50' };
      default:
        return { label: 'Custom', badge: 'bg-slate-800 text-slate-300 border-slate-700' };
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 p-3 sm:p-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
        <h1 className="text-2xl sm:text-3xl font-serif text-slate-100 flex items-center gap-2 sm:gap-3">
          <Trophy className="w-6 h-6 sm:w-8 sm:h-8 text-amber-500" />
          {filter === 'contest' ? 'Guild Contests' : 'Events & Raffles'}
        </h1>
        {canManageEvents && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-amber-600 hover:bg-amber-500 text-white px-3 sm:px-4 py-2 rounded-md transition-colors font-medium text-sm sm:text-base"
          >
            <Plus size={18} className="sm:w-5 sm:h-5" />
            <span className="hidden xs:inline">Create Event</span>
            <span className="xs:hidden">Create</span>
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2 sm:gap-3">
        {[
          { key: 'all', label: 'All Events', icon: null },
          ...(featureFlags.guild_raffles_enabled ? [{ key: 'raffle', label: 'Raffles', icon: <Ticket size={16} /> }] : []),
          ...(featureFlags.guild_contests_enabled ? [{ key: 'contest', label: 'Contests', icon: <Trophy size={16} /> }] : []),
          { key: 'hunt', label: 'Hunts', icon: <Users size={16} /> },
          { key: 'quest', label: 'Quests', icon: <Calendar size={16} /> },
        ].map(({ key, label, icon }) => (
          <button
            key={key}
            className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors font-medium ${filter === key
              ? 'bg-amber-600 text-white'
              : 'bg-slate-800/50 text-slate-300 hover:bg-slate-700/50 border border-slate-700'
              }`}
            onClick={() => {
              setFilter(key as any);
              if (key === 'all') {
                const nextParams = new URLSearchParams(searchParams);
                nextParams.delete('type');
                setSearchParams(nextParams, { replace: true });
              } else {
                setSearchParams({ type: key }, { replace: true });
              }
            }}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading events...</div>
      ) : events.length === 0 ? (
        <div className="bg-slate-900/50 rounded-lg border border-slate-800 p-12 text-center">
          <Trophy size={48} className="mx-auto mb-4 text-slate-700" />
          <p className="text-slate-400">No active events at the moment</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
          {events.map(event => (
            <div
              key={event.id}
              className={`bg-slate-900/80 border rounded-lg p-4 sm:p-6 hover:border-amber-500/50 transition-all ${getTypeMeta(event.type).badge?.includes('amber') ? 'border-amber-900/50' :
                getTypeMeta(event.type).badge?.includes('red') ? 'border-red-900/50' :
                  getTypeMeta(event.type).badge?.includes('green') ? 'border-green-900/50' :
                    getTypeMeta(event.type).badge?.includes('indigo') ? 'border-indigo-900/50' : 'border-slate-700'
                }`}
            >
              <div className="flex justify-between items-start mb-3 sm:mb-4">
                <h3 className="text-lg sm:text-xl font-bold text-slate-100">{event.title}</h3>
                {(() => {
                  const meta = getTypeMeta(event.type);
                  return (
                    <span className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-bold uppercase border ${meta.badge}`}>
                      {event.type === 'raffle' ? <Ticket size={12} /> : <Trophy size={12} />}
                      {meta.label}
                    </span>
                  );
                })()}
              </div>

              {event.description && (
                <p className="text-slate-300 text-sm mb-4 leading-relaxed">{event.description}</p>
              )}

              {event.reward && (
                <div className="flex items-center gap-2 p-3 bg-amber-900/20 border border-amber-700/30 rounded-md mb-4">
                  <Gift size={16} className="text-amber-500" />
                  <span className="text-amber-200 font-medium text-sm">{event.reward}</span>
                </div>
              )}

              <div className="flex gap-4 mb-4 text-sm">
                <div className="flex items-center gap-2 text-slate-400">
                  <Users size={16} />
                  <span>{event.participant_count} / {event.total_slots || '∞'}</span>
                </div>
                {event.draw_date && (
                  <div className="flex items-center gap-2 text-slate-400">
                    <Calendar size={16} />
                    <span>{new Date(event.draw_date).toLocaleDateString()}</span>
                  </div>
                )}
              </div>

              {event.is_drawn && event.winner_name && (
                <div className="flex items-center gap-2 p-3 bg-green-900/20 border border-green-700/30 rounded-md mb-4">
                  <Trophy size={16} className="text-green-500" />
                  <span className="text-green-200 font-medium text-sm">
                    Winner: {event.winner_name}
                    {event.winner_number && <span className="ml-2 text-green-400">#{event.winner_number}</span>}
                  </span>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition-colors font-medium text-sm"
                  onClick={() => openEventDetail(event)}
                >
                  View Details
                </button>
                {!event.is_drawn && !hasUserJoined(event) && (
                  <button
                    className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-md transition-colors font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handleJoinEvent(event.id)}
                    disabled={event.participant_count >= (event.total_slots || Infinity)}
                  >
                    Join Event
                  </button>
                )}
                {hasUserJoined(event) && !event.is_drawn && (
                  <span className="flex-1 px-4 py-2 bg-green-900/30 text-green-400 rounded-md text-center font-medium text-sm border border-green-700/50">
                    Joined ✓
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreateModal && (
        <CreateEventModal
          contestsEnabled={featureFlags.guild_contests_enabled}
          rafflesEnabled={featureFlags.guild_raffles_enabled}
          defaultType={filter === 'contest' ? 'contest' : (filter === 'raffle' ? 'raffle' : 'raffle')}
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreateEvent}
        />
      )}

      {showDetailModal && selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          onClose={() => {
            setShowDetailModal(false);
            setSelectedEvent(null);
            setWinnerNumber(null);
            setWinnerName(null);
          }}
          onDelete={handleDeleteEvent}
          onDrawWinner={handleDrawWinner}
          isDrawing={isDrawing}
          winnerNumber={winnerNumber}
          winnerName={winnerName}
          hasUserJoined={hasUserJoined(selectedEvent)}
          currentUser={user}
        />
      )}
    </div>
  );
};

interface CreateEventModalProps {
  contestsEnabled: boolean;
  rafflesEnabled: boolean;
  defaultType: 'raffle' | 'contest';
  onClose: () => void;
  onCreate: (event: EventCreate) => void;
}

const CreateEventModal: React.FC<CreateEventModalProps> = ({ contestsEnabled, rafflesEnabled, defaultType, onClose, onCreate }) => {
  const [formData, setFormData] = useState<EventCreate>({
    type: defaultType,
    title: '',
    description: '',
    rules: '',
    reward: '',
    total_slots: 100,
    entry_cost: '',
    status: 'active',
    start_date: new Date().toISOString(),
    end_date: '',
    draw_date: '',
    is_public: false,
    participant_mode: 'manual',
    active_days_limit: 10,
    guild_name: '',
    guild_world: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreate({
      ...formData,
      start_date: formData.start_date,
      end_date: formData.end_date || undefined,
      draw_date: formData.draw_date || undefined,
    });
  };

  const toLocalInput = (value?: string) => {
    if (!value) return '';
    return new Date(value).toISOString().slice(0, 16);
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-800 sticky top-0 bg-slate-900 z-10">
          <h2 className="text-2xl font-bold text-slate-100">Create New Event</h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Event Type</label>
            <select
              value={formData.type}
              onChange={e => setFormData({ ...formData, type: e.target.value as any })}
              required
              className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
            >
              {rafflesEnabled && <option value="raffle">Raffle</option>}
              {contestsEnabled && <option value="contest">Contest</option>}
              <option value="hunt">Hunt</option>
              <option value="quest">Quest</option>
              <option value="custom">Custom</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Title</label>
            <input
              type="text"
              value={formData.title}
              onChange={e => setFormData({ ...formData, title: e.target.value })}
              required
              className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              placeholder="Enter event title"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Description</label>
            <textarea
              value={formData.description}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
              rows={3}
              className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 resize-none"
              placeholder="Describe your event..."
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Start Date</label>
              <input
                type="datetime-local"
                required
                value={toLocalInput(formData.start_date)}
                onChange={e => setFormData({ ...formData, start_date: new Date(e.target.value).toISOString() })}
                className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">End Date (optional)</label>
              <input
                type="datetime-local"
                value={toLocalInput(formData.end_date)}
                onChange={e => setFormData({ ...formData, end_date: e.target.value ? new Date(e.target.value).toISOString() : '' })}
                className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Draw Date (raffles)</label>
              <input
                type="datetime-local"
                value={toLocalInput(formData.draw_date)}
                onChange={e => setFormData({ ...formData, draw_date: e.target.value ? new Date(e.target.value).toISOString() : '' })}
                className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Rules</label>
            <textarea
              value={formData.rules}
              onChange={e => setFormData({ ...formData, rules: e.target.value })}
              rows={4}
              className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20 resize-none font-mono text-sm"
              placeholder="Define event rules and guidelines..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Reward</label>
            <input
              type="text"
              value={formData.reward}
              onChange={e => setFormData({ ...formData, reward: e.target.value })}
              className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
              placeholder="e.g., 500k gold, Demon Helmet, etc."
            />
          </div>

          {formData.type === 'raffle' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Total Slots</label>
                <input
                  type="number"
                  value={formData.total_slots}
                  onChange={e => setFormData({ ...formData, total_slots: parseInt(e.target.value) })}
                  min="1"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Entry Cost</label>
                <input
                  type="text"
                  value={formData.entry_cost}
                  onChange={e => setFormData({ ...formData, entry_cost: e.target.value })}
                  placeholder="e.g., 100k gold"
                  className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Draw Date (Optional)</label>
            <input
              type="datetime-local"
              value={formData.draw_date}
              onChange={e => setFormData({ ...formData, draw_date: e.target.value })}
              className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
            />
          </div>

          <div className="flex items-center gap-3 bg-slate-950/50 p-3 rounded-md border border-slate-800">
            <input
              type="checkbox"
              id="is_public"
              checked={formData.is_public || false}
              onChange={e => setFormData({ ...formData, is_public: e.target.checked })}
              className="w-5 h-5 rounded border-slate-700 bg-slate-900 text-amber-500"
            />
            <label htmlFor="is_public" className="cursor-pointer">
              <span className="block text-sm font-medium text-slate-200">Public Event</span>
              <span className="block text-xs text-slate-400">Generate a public link for live viewing</span>
            </label>
          </div>

          {formData.is_public && (
            <div className="space-y-4 bg-slate-950/50 p-4 rounded-md border border-slate-800">
              <h3 className="text-sm font-semibold text-amber-400">Public Event Configuration</h3>
              
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Participant Mode</label>
                <select
                  value={formData.participant_mode}
                  onChange={e => setFormData({ ...formData, participant_mode: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                >
                  <option value="manual">Manual - Add participants manually</option>
                  <option value="guild_auto">Guild Auto - Load from guild automatically</option>
                </select>
              </div>

              {formData.participant_mode === 'guild_auto' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">Guild Name</label>
                    <input
                      type="text"
                      value={formData.guild_name}
                      onChange={e => setFormData({ ...formData, guild_name: e.target.value })}
                      placeholder="e.g., Bloodborne Warhowl"
                      className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">Active Days Limit</label>
                    <input
                      type="number"
                      value={formData.active_days_limit}
                      onChange={e => setFormData({ ...formData, active_days_limit: parseInt(e.target.value) || 10 })}
                      min="1"
                      max="365"
                      className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                    />
                    <p className="text-xs text-slate-500 mt-1">Only load members active within last X days</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">Guild World (Optional)</label>
                    <input
                      type="text"
                      value={formData.guild_world}
                      onChange={e => setFormData({ ...formData, guild_world: e.target.value })}
                      placeholder="e.g., Antica, Belobra..."
                      className="w-full bg-slate-950 border border-slate-700 rounded-md p-3 text-slate-200 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
                    />
                    <p className="text-xs text-slate-500 mt-1">Restrict participants to this world</p>
                  </div>
                </>
              )}
            </div>
          )}


          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition-colors font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-3 bg-amber-600 hover:bg-amber-500 text-white rounded-md transition-colors font-medium"
            >
              Create Event
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

interface EventDetailModalProps {
  event: Event;
  onClose: () => void;
  onDelete: (id: number) => void;
  onDrawWinner: (id: number) => void;
  isDrawing: boolean;
  winnerNumber: number | null;
  winnerName: string | null;
  hasUserJoined: boolean;
  currentUser: any;
}

const EventDetailModal: React.FC<EventDetailModalProps> = ({
  event,
  onClose,
  onDelete,
  onDrawWinner,
  isDrawing,
  winnerNumber,
  winnerName,
  currentUser,
}) => {
  const [isPublicEdit, setIsPublicEdit] = useState(event.is_public);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncLog, setSyncLog] = useState<string[]>([]);
  const [showLog, setShowLog] = useState(false);
  const [manualCharName, setManualCharName] = useState('');
  const [addingManual, setAddingManual] = useState(false);
  const canManageEvent = Boolean(currentUser?.is_superuser || ['leader', 'vice leader', 'guild leader', 'alpha warbringer', 'bloodhowl marshal'].includes((currentUser?.guild_rank || '').toLowerCase()));
  const publicUrl = event.type === 'contest' && event.public_code
    ? `https://tibiahub.domoforge.com/contests/${event.public_code}`
    : `https://tibiahub.domoforge.com/public/event/${event.uuid}`;

  const addLog = (message: string) => {
    setSyncLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
  };

  const handleTogglePublic = async () => {
    try {
      addLog(`Changing event visibility to ${!isPublicEdit ? 'PUBLIC' : 'PRIVATE'}...`);
      await eventsApi.updateEvent(event.id, { is_public: !isPublicEdit });
      setIsPublicEdit(!isPublicEdit);
      addLog(`✅ Event is now ${!isPublicEdit ? 'PUBLIC' : 'PRIVATE'}`);
      toast.success?.(`Event is now ${!isPublicEdit ? 'public' : 'private'}`);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(`Failed to update visibility: ${errorMsg}`);
      console.error('Toggle public error:', err);
    }
  };

  const handleSyncParticipants = async () => {
    if (!canManageEvent) return;
    setSyncLoading(true);
    addLog('🔄 Refreshing participant list...');
    
    try {
      addLog(`Loading current guild roster...`);
      addLog(`Guild: ${event.guild_name || 'Not configured'}`);
      
      const result = await eventsApi.loadGuildParticipants(event.id, true);
      
      addLog(`✅ Update completed!`);
      addLog(`  - Loaded: ${result.loaded} new participants`);
      addLog(`  - Updated: ${result.updated} existing participants`);
      addLog(`  - Total: ${result.total} participants`);
      
      toast.success?.(`Participants updated! ${result.total} total participants`);
      
      // Refresh event data without full reload
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(`Failed to refresh participants: ${errorMsg}`);
      console.error('Sync error:', err);
    } finally {
      setSyncLoading(false);
    }
  };

  const handleAddManualParticipant = async () => {
    if (!manualCharName.trim() || !canManageEvent) return;
    setAddingManual(true);
    addLog(`Adding manual participant: ${manualCharName}...`);
    
    try {
      addLog(`Validating character...`);
      const result = await eventsApi.addManualParticipant(event.id, { character_name: manualCharName });
      
      addLog(`✅ Participant added!`);
      addLog(`  - Character: ${result.character_name}`);
      addLog(`  - Level: ${result.character_level}`);
      addLog(`  - Vocation: ${result.character_vocation}`);
      addLog(`  - Number: #${result.assigned_number}`);
      
      toast.success?.(`${result.character_name} added successfully!`);
      setManualCharName('');
      
      // Refresh event data without immediate reload
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(`Failed to add participant: ${errorMsg}`);
      console.error('Add participant error:', err);
    } finally {
      setAddingManual(false);
    }
  };

  const handleExcludeParticipant = async (participantId: number, participantName: string) => {
    if (!canManageEvent) return;
    
    if (!confirm(`¿Marcar a ${participantName} como NO participante? No volverá a aparecer en actualizaciones automáticas.`)) {
      return;
    }
    
    addLog(`🚫 Excluding ${participantName}...`);
    
    try {
      await eventsApi.excludeParticipant(event.id, participantId);
      addLog(`✅ ${participantName} excluido permanentemente`);
      toast.success?.(`${participantName} excluido del evento`);
      
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(`Failed to exclude: ${errorMsg}`);
      console.error('Exclude error:', err);
    }
  };

  const handleDeleteParticipant = async (participantId: number, participantName: string) => {
    if (!canManageEvent) return;
    
    if (!confirm(`¿Eliminar a ${participantName}? Podrá volver a agregarse en la próxima actualización.`)) {
      return;
    }
    
    addLog(`🗑️ Deleting ${participantName}...`);
    
    try {
      await eventsApi.deleteParticipant(event.id, participantId);
      addLog(`✅ ${participantName} eliminado`);
      toast.success?.(`${participantName} eliminado del evento`);
      
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err: any) {
      const errorMsg = err.message || err.toString();
      addLog(`❌ Error: ${errorMsg}`);
      toast.error?.(`Failed to delete: ${errorMsg}`);
      console.error('Delete error:', err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6 border-b border-slate-800 flex justify-between items-start sticky top-0 bg-slate-900 z-10">
          <h2 className="text-2xl font-bold text-slate-100">{event.title}</h2>
          {canManageEvent && (
            <button
              onClick={() => onDelete(event.id)}
              className="p-2 bg-red-900/30 hover:bg-red-900/50 text-red-400 border border-red-700/50 rounded-md transition-colors"
            >
              <Trash2 size={18} />
            </button>
          )}
        </div>

        <div className="p-6 space-y-6">
          {event.description && (
            <div>
              <h3 className="text-lg font-semibold text-slate-200 mb-2">Description</h3>
              <p className="text-slate-300 leading-relaxed">{event.description}</p>
            </div>
          )}

          {event.rules && (
            <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-amber-400 mb-3 flex items-center gap-2">
                <Trophy size={18} />
                Rules
              </h3>
              <p className="text-slate-300 whitespace-pre-line leading-relaxed font-mono text-sm">{event.rules}</p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-slate-400">Starts</div>
              <div className="text-slate-200 font-medium">{event.start_date ? new Date(event.start_date).toLocaleString() : 'TBD'}</div>
            </div>
            {event.end_date && (
              <div>
                <div className="text-sm text-slate-400">Ends</div>
                <div className="text-slate-200 font-medium">{new Date(event.end_date).toLocaleString()}</div>
              </div>
            )}
            {event.draw_date && (
              <div>
                <div className="text-sm text-slate-400">Draw</div>
                <div className="text-slate-200 font-medium">{new Date(event.draw_date).toLocaleString()}</div>
              </div>
            )}
          </div>

          {event.reward && (
            <div className="bg-amber-900/20 border border-amber-700/30 rounded-lg p-4">
              <h3 className="text-lg font-semibold text-amber-400 mb-3">Reward</h3>
              <div className="flex items-center gap-3">
                <Gift size={24} className="text-amber-500" />
                <span className="text-amber-200 font-medium text-lg">{event.reward}</span>
              </div>
            </div>
          )}

          {/* Admin Controls */}
          {canManageEvent && (
            <div className="bg-gradient-to-br from-indigo-900/20 to-slate-900 border border-indigo-700/50 rounded-lg p-6 space-y-4">
              <h3 className="text-lg font-semibold text-indigo-400 mb-3 flex items-center gap-2">
                <Users size={18} />
                Admin Controls
              </h3>

              {/* Info Box for Public Events */}
              {isPublicEdit && (
                <div className="p-3 bg-blue-900/20 border border-blue-700/30 rounded-md text-sm text-blue-300">
                  ℹ️ Public events should be drawn from the public page. Participants update automatically.
                </div>
              )}

              {/* Public/Private Toggle */}
              <div className="flex items-center justify-between p-3 bg-slate-950/50 rounded-md">
                <div>
                  <div className="font-medium text-slate-200">Event Visibility</div>
                  <div className="text-xs text-slate-400">
                    {isPublicEdit ? '🌐 Public - Anyone can view' : '🔒 Private - Members only'}
                  </div>
                </div>
                <button
                  onClick={handleTogglePublic}
                  className={`px-4 py-2 rounded-md font-medium transition-colors ${
                    isPublicEdit 
                      ? 'bg-green-600 hover:bg-green-500 text-white'
                      : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                  }`}
                >
                  {isPublicEdit ? 'Public' : 'Private'}
                </button>
              </div>

              {/* Guild Participants */}
              {event.is_public && (
                <div className="space-y-3">
                  <div className="p-3 bg-slate-950/50 rounded-md">
                    <div className="text-sm text-slate-400 mb-2">
                      Mode: <span className="text-amber-400 font-mono">{event.participant_mode || 'manual'}</span>
                      {event.guild_name && <> | Guild: <span className="text-amber-400">{event.guild_name}</span></>}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3">
                    <button
                      onClick={handleSyncParticipants}
                      disabled={syncLoading}
                      className="flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-md font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {syncLoading ? (
                        <>
                          <Loader2 className="animate-spin" size={16} />
                          Refreshing...
                        </>
                      ) : (
                        <>
                          <Users size={16} />
                          Refresh Guild Participants
                        </>
                      )}
                    </button>

                    {/* Manual Add */}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={manualCharName}
                        onChange={e => setManualCharName(e.target.value)}
                        placeholder="Character name..."
                        className="flex-1 bg-slate-950 border border-slate-700 rounded-md p-2 text-slate-200 text-sm"
                        onKeyPress={e => e.key === 'Enter' && handleAddManualParticipant()}
                      />
                      <button
                        onClick={handleAddManualParticipant}
                        disabled={addingManual || !manualCharName.trim()}
                        className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-md font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {addingManual ? <Loader2 className="animate-spin" size={16} /> : 'Add'}
                      </button>
                    </div>
                  </div>

                  {/* Log Toggle */}
                  <button
                    onClick={() => setShowLog(!showLog)}
                    className="w-full px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-md text-sm font-medium transition-colors"
                  >
                    {showLog ? '🔽 Hide Logs' : '🔼 Show Logs'}
                  </button>

                  {/* Log Display */}
                  {showLog && (
                    <div className="bg-slate-950 border border-slate-700 rounded-md p-3 max-h-48 overflow-y-auto font-mono text-xs">
                      {syncLog.length === 0 ? (
                        <div className="text-slate-500">No logs yet. Perform an action to see logs.</div>
                      ) : (
                        syncLog.map((log, i) => (
                          <div key={i} className="text-slate-300 mb-1">{log}</div>
                        ))
                      )}
                    </div>
                  )}

                  {/* Public URL */}
                  {isPublicEdit && event.uuid && (
                    <div className="p-3 bg-green-900/20 border border-green-700/30 rounded-md">
                      <div className="text-xs text-green-400 mb-1">Public URL:</div>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={publicUrl}
                          readOnly
                          className="flex-1 bg-slate-950 border border-green-700/50 rounded p-2 text-green-300 text-xs font-mono"
                        />
                        <button
                          onClick={() => navigator.clipboard.writeText(publicUrl)}
                          className="px-3 py-2 bg-green-700 hover:bg-green-600 text-white rounded text-xs"
                        >
                          Copy
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {event.type === 'raffle' && !event.is_drawn && !event.is_public && canManageEvent && (
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-700 rounded-lg p-6 text-center">
              <button
                className="px-6 py-3 bg-amber-600 hover:bg-amber-500 text-white rounded-md font-bold text-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:scale-105 active:scale-95"
                onClick={() => onDrawWinner(event.id)}
                disabled={isDrawing || event.participants.length === 0}
              >
                {isDrawing ? 'Drawing Winner...' : 'Draw Winner'}
              </button>


              {isDrawing && winnerNumber && (
                <div className="mt-6 flex justify-center">
                  <div className="animate-bounce">
                    <div className="w-32 h-32 bg-gradient-to-br from-amber-500 to-amber-600 rounded-2xl flex items-center justify-center shadow-2xl">
                      <div className="text-5xl font-bold text-white">{winnerNumber}</div>
                    </div>
                  </div>
                </div>
              )}

              {!isDrawing && winnerName && (
                <div className="mt-6 bg-gradient-to-br from-amber-900/30 to-amber-800/30 border border-amber-600/50 rounded-lg p-6 animate-pulse">
                  <Trophy size={40} className="mx-auto text-amber-500 mb-3" />
                  <h3 className="text-2xl font-bold text-amber-300 mb-2">🎉 Winner: {winnerName} 🎉</h3>
                  {winnerNumber && <p className="text-3xl font-bold text-amber-400">#{winnerNumber}</p>}
                </div>
              )}
            </div>
          )}

          {event.is_drawn && event.winner_name && (
            <div className="bg-gradient-to-br from-green-900/30 to-green-800/30 border border-green-600/50 rounded-lg p-6 text-center">
              <Trophy size={40} className="mx-auto text-green-500 mb-3" />
              <h3 className="text-2xl font-bold text-green-300 mb-2">Winner: {event.winner_name}</h3>
              {event.winner_number && <p className="text-3xl font-bold text-green-400">#{event.winner_number}</p>}
            </div>
          )}

          <div>
            <h3 className="text-lg font-semibold text-slate-200 mb-4">
              Participants ({event.participant_count})
            </h3>
            <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-4 max-h-64 overflow-y-auto">
              <div className="grid grid-cols-1 gap-3">
                {event.participants.map(p => (
                  <div
                    key={p.id}
                    className="flex justify-between items-center bg-slate-900/50 border border-slate-700 rounded-md p-3"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-300 text-sm truncate">{p.username}</span>
                      {p.assigned_number && (
                        <span className="px-2 py-1 bg-amber-600/20 text-amber-400 rounded font-bold text-xs border border-amber-700/50">
                          #{p.assigned_number}
                        </span>
                      )}
                    </div>
                    {canManageEvent && event.is_public && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleExcludeParticipant(p.id, p.username)}
                          className="px-2 py-1 bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded text-xs border border-red-700/50 transition-colors"
                          title="Excluir permanentemente (no volverá en actualizaciones automáticas)"
                        >
                          🚫
                        </button>
                        <button
                          onClick={() => handleDeleteParticipant(p.id, p.username)}
                          className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded text-xs border border-slate-600 transition-colors"
                          title="Eliminar (puede volver en próxima actualización)"
                        >
                          🗑️
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-slate-800 sticky bottom-0 bg-slate-900">
          <button
            onClick={onClose}
            className="w-full px-4 py-3 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition-colors font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default Events;
