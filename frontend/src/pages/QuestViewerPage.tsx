import React, { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { Search, Book, ChevronRight, AlertCircle, Loader2 } from 'lucide-react';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure PDF Worker
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

// Mock Data for Quests mapping to PDF Pages
const QUESTS_DB = [
    { id: 1, name: 'The Desert Dungeon', page: 5, difficulty: 'Easy' },
    { id: 2, name: 'Pits of Inferno', page: 42, difficulty: 'Hard' },
    { id: 3, name: 'In Service of Yalahar', page: 12, difficulty: 'Medium' },
    { id: 4, name: 'The Ancient Tombs', page: 8, difficulty: 'Medium' },
    { id: 5, name: 'Annihilator', page: 66, difficulty: 'Extreme' },
];

const QuestViewerPage: React.FC = () => {
    const [selectedQuest, setSelectedQuest] = useState(QUESTS_DB[0]);
    const [search, setSearch] = useState('');
    const [scale, setScale] = useState(1.0);

    // Filter quests
    const filteredQuests = QUESTS_DB.filter(q =>
        q.name.toLowerCase().includes(search.toLowerCase())
    );

    function onDocumentLoadSuccess() {
        // Placeholder for future logic
    }

    return (
        <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12 gap-6 relative">

            {/* Sidebar - Quest List */}
            <div className="lg:col-span-4 xl:col-span-3 space-y-4">
                <div className="bg-surface-base/80 backdrop-blur border border-line rounded-xl p-4 sticky top-24">
                    <h2 className="text-xl font-serif text-primary mb-4 flex items-center gap-2">
                        <Book /> Quest Log
                    </h2>

                    <div className="relative mb-4">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-content-secondary w-4 h-4" />
                        <input
                            type="text"
                            placeholder="Search quest..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="w-full bg-surface border border-line rounded-lg py-2 pl-9 pr-4 text-sm text-content-primary focus:outline-none focus:border-primary transition-colors"
                        />
                    </div>

                    <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-2 custom-scrollbar">
                        {filteredQuests.map((quest) => (
                            <button
                                key={quest.id}
                                onClick={() => setSelectedQuest(quest)}
                                className={`w-full text-left px-4 py-3 rounded-lg flex items-center justify-between transition-all ${selectedQuest.id === quest.id
                                    ? 'bg-primary text-content-on-primary shadow-lg shadow-primary/20'
                                    : 'bg-surface/50 text-content-secondary hover:bg-surface hover:text-content-primary'
                                    }`}
                            >
                                <span>{quest.name}</span>
                                <ChevronRight className={`w-4 h-4 ${selectedQuest.id === quest.id ? 'text-content-primary' : 'text-content-muted'}`} />
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Main Content - PDF Viewer */}
            <div className="lg:col-span-8 xl:col-span-9">
                <div className="bg-surface-base/90 border border-line rounded-xl overflow-hidden min-h-[800px] flex flex-col">

                    {/* Toolbar */}
                    <div className="bg-surface p-4 border-b border-line flex items-center justify-between">
                        <div>
                            <h1 className="text-lg font-bold text-content-primary max-w-md truncate">{selectedQuest.name}</h1>
                            <p className="text-xs text-primary">Go to Page {selectedQuest.page}</p>
                        </div>

                        <div className="flex items-center gap-2">
                            <button onClick={() => setScale(s => Math.max(0.5, s - 0.1))} className="p-2 hover:bg-surface-raised rounded">-</button>
                            <span className="text-sm text-content-secondary">{Math.round(scale * 100)}%</span>
                            <button onClick={() => setScale(s => Math.min(2.0, s + 0.1))} className="p-2 hover:bg-surface-raised rounded">+</button>
                        </div>
                    </div>

                    {/* PDF Container */}
                    <div className="flex-1 bg-surface-base flex justify-center p-8 overflow-auto relative">
                        <Document
                            file="/quests-handbook.pdf"
                            onLoadSuccess={onDocumentLoadSuccess}
                            loading={
                                <div className="flex items-center gap-2 text-primary">
                                    <Loader2 className="animate-spin" /> Loading Knowledge Base...
                                </div>
                            }
                            error={
                                <div className="text-center text-content-muted mt-20">
                                    <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                    <p>PDF Guide not found on server.</p>
                                    <p className="text-sm mt-2">Please upload 'quests-handbook.pdf' to the public folder.</p>
                                </div>
                            }
                            className="shadow-2xl"
                        >
                            <Page
                                pageNumber={selectedQuest.page}
                                scale={scale}
                                className="shadow-2xl border border-line"
                                renderTextLayer={false}
                                renderAnnotationLayer={false}
                            />
                        </Document>
                    </div>
                </div>
            </div>

        </div>
    );
};

export default QuestViewerPage;
