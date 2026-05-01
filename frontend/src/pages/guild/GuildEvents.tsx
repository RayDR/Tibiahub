import React, { useEffect, useState } from 'react';
import { guildApi, Event } from '../../services/guild';

import { Plus, CalendarClock, Clock, CheckCircle2, XCircle, HelpCircle } from 'lucide-react';

export default function Events() {

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
            const data = await guildApi.getEvents();
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
    }, []);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreating(true);
        try {
            await guildApi.createEvent({
                ...formData,
                start_time: new Date(formData.start_time).toISOString(),
                end_time: formData.end_time ? new Date(formData.end_time).toISOString() : null
            });
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
                <h1 className="text-3xl font-serif text-slate-100 flex items-center gap-3">
                    <CalendarClock className="w-8 h-8 text-amber-500" />
                    Events & Hunts
                </h1>

                <button
                    onClick={() => setShowModal(true)}
                    className="flex items-center gap-2 bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 rounded-md transition-colors text-sm font-medium"
                >
                    <Plus className="w-4 h-4" />
                    Schedule Event
                </button>
            </div>

            <div className="grid grid-cols-1 gap-4">
                {events.map((event) => (
                    <div key={event.id} className="bg-slate-900/80 border border-slate-700/50 rounded-lg p-6 hover:border-slate-600 transition-all flex flex-col md:flex-row gap-6">
                        {/* Date Box */}
                        <div className="bg-slate-950 rounded-lg p-4 flex-shrink-0 text-center w-full md:w-24 border border-slate-800 flex flex-col items-center justify-center">
                            <span className="text-xs text-slate-500 uppercase font-bold">
                                {new Date(event.start_time).toLocaleString('default', { month: 'short' })}
                            </span>
                            <span className="text-2xl font-bold text-amber-500">
                                {new Date(event.start_time).getDate()}
                            </span>
                            <span className="text-xs text-slate-400">
                                {new Date(event.start_time).toLocaleString('default', { weekday: 'short' })}
                            </span>
                        </div>

                        {/* Event Details */}
                        <div className="flex-1">
                            <div className="flex items-start justify-between">
                                <div>
                                    <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider mb-2 ${event.type === 'quest' ? 'bg-indigo-900/50 text-indigo-300' :
                                        event.type === 'hunt' ? 'bg-red-900/50 text-red-300' :
                                            'bg-slate-800 text-slate-300'
                                        }`}>
                                        {event.type}
                                    </span>
                                    <h3 className="text-lg font-bold text-slate-100">{event.title}</h3>
                                </div>
                            </div>

                            <div className="mt-2 text-sm text-slate-400 flex flex-col sm:flex-row gap-4 mb-3">
                                <div className="flex items-center gap-1.5">
                                    <Clock className="w-4 h-4 text-slate-500" />
                                    {new Date(event.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </div>
                                {/* Location placeholder if description contains it often, but for now just description */}
                            </div>

                            <p className="text-slate-300 text-sm whitespace-pre-line mb-4">{event.description}</p>

                            <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-800">
                                <span className="text-xs text-slate-500 mr-2">Your Status:</span>
                                <button onClick={() => handleAttend(event.id, 'confirmed')} className="p-1.5 rounded bg-green-900/20 text-green-500 hover:bg-green-900/40" title="Confirm"><CheckCircle2 className="w-4 h-4" /></button>
                                <button onClick={() => handleAttend(event.id, 'maybe')} className="p-1.5 rounded bg-yellow-900/20 text-yellow-500 hover:bg-yellow-900/40" title="Maybe"><HelpCircle className="w-4 h-4" /></button>
                                <button onClick={() => handleAttend(event.id, 'declined')} className="p-1.5 rounded bg-red-900/20 text-red-500 hover:bg-red-900/40" title="Decline"><XCircle className="w-4 h-4" /></button>
                            </div>
                        </div>
                    </div>
                ))}

                {events.length === 0 && !loading && (
                    <div className="text-center py-12 text-slate-500 bg-slate-900/50 rounded-lg border border-slate-800">
                        <CalendarClock className="w-12 h-12 mx-auto mb-4 opacity-20" />
                        <p>No events scheduled. Be the first to lead a hunt!</p>
                    </div>
                )}
            </div>

            {/* Create Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-lg shadow-2xl">
                        <div className="p-6 border-b border-slate-800">
                            <h3 className="text-xl font-bold text-slate-100">Schedule Event</h3>
                        </div>

                        <form onSubmit={handleCreate} className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-1">Title</label>
                                <input
                                    type="text"
                                    required
                                    value={formData.title}
                                    onChange={e => setFormData({ ...formData, title: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200 focus:border-amber-500 focus:outline-none"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-400 mb-1">Type</label>
                                    <select
                                        value={formData.type}
                                        onChange={e => setFormData({ ...formData, type: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200 focus:border-amber-500 focus:outline-none"
                                    >
                                        <option value="hunt">Hunt</option>
                                        <option value="quest">Quest</option>
                                        <option value="pvp">PvP</option>
                                        <option value="meeting">Meeting</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-400 mb-1">Start Time</label>
                                    <input
                                        type="datetime-local"
                                        required
                                        value={formData.start_time}
                                        onChange={e => setFormData({ ...formData, start_time: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200 focus:border-amber-500 focus:outline-none"
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-1">Description</label>
                                <textarea
                                    required
                                    rows={4}
                                    value={formData.description}
                                    onChange={e => setFormData({ ...formData, description: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200 focus:border-amber-500 focus:outline-none font-mono text-sm"
                                    placeholder="Where, requirements, loot split rules..."
                                />
                            </div>

                            <div className="flex justify-end gap-3 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="px-4 py-2 text-slate-400 hover:text-slate-200 font-medium"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={creating}
                                    className="bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 rounded-md font-medium disabled:opacity-50"
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
