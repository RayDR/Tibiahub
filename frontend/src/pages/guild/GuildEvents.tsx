import React, { useEffect, useState } from 'react';
import { guildApi, Event } from '../../services/guild';

import { Plus, CalendarClock, Clock, CheckCircle2, XCircle, HelpCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useGuildContext } from '../../utils/guildContext';

export default function Events() {
    const { user } = useAuth();
    const guildName = useGuildContext(user);

    const [events, setEvents] = useState<Event[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        start_time: '',
        end_time: '',
        type: 'hunt'
    });
    const [creating, setCreating] = useState(false);

    const loadData = async () => {
        try {
            setLoading(true);
            if (!guildName) {
                setEvents([]);
                return;
            }
            const data = await guildApi.getEvents(0, 20, guildName);
            // Mocking attendance data for now as the API response doesn't nest it fully yet in my simple service
            // In a real app we'd fetch attendance status per event or include it in the event object
            setEvents(data);
        } catch (error) {
            console.error("Failed to load events", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, [guildName]);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreating(true);
        try {
            if (!guildName) throw new Error('Missing guild context');
            await guildApi.createEvent({
                ...formData,
                start_time: new Date(formData.start_time).toISOString(),
                end_time: formData.end_time ? new Date(formData.end_time).toISOString() : null
            }, guildName);
            setShowModal(false);
            setFormData({ title: '', description: '', start_time: '', end_time: '', type: 'hunt' });
            loadData();
        } catch (error) {
            console.error("Failed to create event", error);
        } finally {
            setCreating(false);
        }
    };

    const handleAttend = async (eventId: number, status: string) => {
        try {
            await guildApi.attendEvent(eventId, status);
            // optimistically update UI or reload
            alert("Attendance updated!");
        } catch (err) {
            console.error(err);
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-serif text-content-primary flex items-center gap-3">
                    <CalendarClock className="w-8 h-8 text-primary" />
                    Events & Hunts
                </h1>

                <button
                    onClick={() => setShowModal(true)}
                    className="flex items-center gap-2 bg-primary hover:bg-primary-hover text-content-on-primary px-4 py-2 rounded-md transition-colors text-sm font-medium"
                >
                    <Plus className="w-4 h-4" />
                    Schedule Event
                </button>
            </div>

            <div className="grid grid-cols-1 gap-4">
                {events.map((event) => (
                    <div key={event.id} className="bg-surface-base/80 border border-line/50 rounded-lg p-6 hover:border-line transition-all flex flex-col md:flex-row gap-6">
                        {/* Date Box */}
                        <div className="bg-surface-base rounded-lg p-4 flex-shrink-0 text-center w-full md:w-24 border border-line flex flex-col items-center justify-center">
                            <span className="text-xs text-content-muted uppercase font-bold">
                                {new Date(event.start_time).toLocaleString('default', { month: 'short' })}
                            </span>
                            <span className="text-2xl font-bold text-primary">
                                {new Date(event.start_time).getDate()}
                            </span>
                            <span className="text-xs text-content-secondary">
                                {new Date(event.start_time).toLocaleString('default', { weekday: 'short' })}
                            </span>
                        </div>

                        {/* Event Details */}
                        <div className="flex-1">
                            <div className="flex items-start justify-between">
                                <div>
                                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider mb-2 ${event.type === 'quest' ? 'bg-accent/50 text-accent' :
                                        event.type === 'hunt' ? 'bg-danger/50 text-danger' :
                                            'bg-surface text-content-secondary'
                                        }`}>
                                        {event.type}
                                    </span>
                                    <h3 className="text-lg font-bold text-content-primary">{event.title}</h3>
                                </div>
                            </div>

                            <div className="mt-2 text-sm text-content-secondary flex flex-col sm:flex-row gap-4 mb-3">
                                <div className="flex items-center gap-1.5">
                                    <Clock className="w-4 h-4 text-content-muted" />
                                    {new Date(event.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </div>
                                {/* Location placeholder if description contains it often, but for now just description */}
                            </div>

                            <p className="text-content-secondary text-sm whitespace-pre-line mb-4">{event.description}</p>

                            <div className="flex items-center gap-2 mt-4 pt-4 border-t border-line">
                                <span className="text-xs text-content-muted mr-2">Your Status:</span>
                                <button onClick={() => handleAttend(event.id, 'confirmed')} className="p-1.5 rounded bg-success/20 text-success hover:bg-success/40" title="Confirm"><CheckCircle2 className="w-4 h-4" /></button>
                                <button onClick={() => handleAttend(event.id, 'maybe')} className="p-1.5 rounded bg-primary/20 text-primary hover:bg-primary/40" title="Maybe"><HelpCircle className="w-4 h-4" /></button>
                                <button onClick={() => handleAttend(event.id, 'declined')} className="p-1.5 rounded bg-danger/20 text-danger hover:bg-danger/40" title="Decline"><XCircle className="w-4 h-4" /></button>
                            </div>
                        </div>
                    </div>
                ))}

                {events.length === 0 && !loading && (
                    <div className="text-center py-12 text-content-muted bg-surface-base/50 rounded-lg border border-line">
                        <CalendarClock className="w-12 h-12 mx-auto mb-4 opacity-20" />
                        <p>No events scheduled. Be the first to lead a hunt!</p>
                    </div>
                )}
            </div>

            {/* Create Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-surface-base/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-surface-base border border-line rounded-lg w-full max-w-lg shadow-2xl">
                        <div className="p-6 border-b border-line">
                            <h3 className="text-xl font-bold text-content-primary">Schedule Event</h3>
                        </div>

                        <form onSubmit={handleCreate} className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-content-secondary mb-1">Title</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.title}
                                    onChange={e => setFormData({ ...formData, title: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded p-2 text-content-primary focus:border-primary focus:outline-none"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Type</label>
                                    <select
                                        value={formData.type}
                                        onChange={e => setFormData({ ...formData, type: e.target.value })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary focus:border-primary focus:outline-none"
                                    >
                                        <option value="hunt">Hunt</option>
                                        <option value="quest">Quest</option>
                                        <option value="pvp">PvP</option>
                                        <option value="meeting">Meeting</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-content-secondary mb-1">Start Time</label>
                                    <input
                                        type="datetime-local"
                                        required
                                        value={formData.start_time}
                                        onChange={e => setFormData({ ...formData, start_time: e.target.value })}
                                        className="w-full bg-surface-base border border-line rounded p-2 text-content-primary focus:border-primary focus:outline-none"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-content-secondary mb-1">Description</label>
                                <textarea
                                    required
                                    rows={4}
                                    value={formData.description}
                                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                                    className="w-full bg-surface-base border border-line rounded p-2 text-content-primary focus:border-primary focus:outline-none font-mono text-sm"
                                    placeholder="Where, requirements, loot split rules..."
                                />
                            </div>

                            <div className="flex justify-end gap-3 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="px-4 py-2 text-content-secondary hover:text-content-primary font-medium"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={creating}
                                    className="bg-primary hover:bg-primary-hover text-content-on-primary px-4 py-2 rounded-md font-medium disabled:opacity-50"
                                >
                                    {creating ? 'Scheduling...' : 'Schedule Event'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
