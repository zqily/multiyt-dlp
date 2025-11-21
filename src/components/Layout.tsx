// src/components/Layout.tsx

import { ReactNode } from 'react';
import { Settings } from 'lucide-react';
import { Button } from './ui/Button';

interface LayoutProps {
  SidebarContent: ReactNode;
  MainContent: ReactNode;
}

export function Layout({ SidebarContent, MainContent }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-zinc-900 text-zinc-100">
      {/* Sidebar */}
      <aside className="w-80 flex-shrink-0 bg-zinc-900/50 border-r border-zinc-800 p-4 overflow-y-auto flex flex-col">
        <div className="flex items-center justify-between px-2 mb-8 mt-4">
            <div>
                <h1 className="text-lg font-bold tracking-tight text-white">
                    Multiyt-dlp
                </h1>
                <div className="text-xs text-zinc-500 mt-1">
                    Concurrent Video Downloader
                </div>
            </div>
            <Button variant="ghost" size="icon" title="Settings" className="text-zinc-500 hover:text-white">
                <Settings className="h-5 w-5" />
            </Button>
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