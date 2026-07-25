import { Link } from 'react-router-dom';
import { Skull, CornerDownLeft } from 'lucide-react';

export default function NotFound() {
    return (
        <div className="min-h-screen bg-surface-base flex items-center justify-center p-4 relative overflow-hidden">
            {/* Background Texture */}
            <div className="absolute inset-0 bg-[url('https://tibiamaps.io/images/map-preview.png')] opacity-5 pointer-events-none mix-blend-overlay"></div>

            <div className="text-center relative z-10 max-w-md mx-auto">
                <div className="mb-8 relative inline-block">
                    <div className="absolute inset-0 bg-danger/20 blur-xl rounded-full"></div>
                    <Skull className="w-24 h-24 text-danger mx-auto relative animate-pulse" strokeWidth={1} />
                </div>

                <h1 className="text-4xl md:text-5xl font-cinzel text-danger font-bold mb-4 tracking-wider">
                    YOU ARE DEAD
                </h1>

                <p className="text-content-secondary text-lg mb-8 font-serif leading-relaxed">
                    Alas! The path you seek has been lost to the void.
                    Perhaps it was destroyed by demons, or never existed at all.
                </p>

                <div className="space-y-4">
                    <Link
                        to="/"
                        className="inline-flex items-center gap-2 bg-surface-base/50 hover:bg-surface border-2 border-line text-content-secondary px-6 py-3 rounded-lg transition-all font-cinzel uppercase tracking-wide group"
                    >
                        <CornerDownLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
                        Return to Temple
                    </Link>
                </div>

                <div className="mt-12 text-xs text-content-muted font-mono">
                    Error 404: Page Not Found
                </div>
            </div>
        </div>
    );
}
