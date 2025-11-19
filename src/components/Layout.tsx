import { ReactNode } from 'react';

interface LayoutProps {
  SidebarContent: ReactNode;
  MainContent: ReactNode;
}

export function Layout({ SidebarContent, MainContent }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-synth-navy text-synth-light font-sans selection:bg-synth-pink selection:text-white">
      {/* Sidebar */}
      <aside className="w-80 flex-shrink-0 bg-synth-dark/80 border-r border-synth-cyan/20 p-4 overflow-y-auto backdrop-blur-md relative z-10 flex flex-col shadow-2xl">
        <div className="mb-6 mt-2 text-center">
            <h1 className="text-2xl font-black italic tracking-tighter text-transparent bg-clip-text bg-gradient-to-r from-synth-cyan to-synth-pink drop-shadow-[0_0_5px_rgba(8,217,214,0.5)]">
                MULTIYT-DLP
            </h1>
            <div className="text-[10px] font-mono text-synth-cyan/60 tracking-[0.2em] uppercase mt-1">
                System Ready
            </div>
        </div>
        {SidebarContent}
      </aside>
      
      {/* Main Content */}
      <main className="flex-grow p-6 overflow-y-auto relative z-0 scanlines">
        {MainContent}
      </main>
    </div>
  );
}