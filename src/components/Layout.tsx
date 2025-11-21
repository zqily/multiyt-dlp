import { ReactNode } from 'react';

interface LayoutProps {
  SidebarContent: ReactNode;
  MainContent: ReactNode;
}

export function Layout({ SidebarContent, MainContent }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      {/* Sidebar */}
      <aside className="w-80 flex-shrink-0 bg-zinc-900/50 border-r border-zinc-800 p-4 overflow-y-auto flex flex-col">
        <div className="mb-8 mt-4 px-2">
            <h1 className="text-lg font-bold tracking-tight text-white">
                Multiyt-dlp
            </h1>
            <div className="text-xs text-zinc-500 mt-1">
                Concurrent Video Downloader
            </div>
        </div>
        {SidebarContent}
      </aside>
      
      {/* Main Content */}
      <main className="flex-grow p-8 overflow-y-auto bg-zinc-950">
        <div className="max-w-4xl mx-auto">
            {MainContent}
        </div>
      </main>
    </div>
  );
}