import { ReactNode } from 'react';

interface LayoutProps {
  SidebarContent: ReactNode;
  MainContent: ReactNode;
}

export function Layout({ SidebarContent, MainContent }: LayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar: Fixed width, houses all controls */}
      <aside className="w-80 flex-shrink-0 bg-zinc-800 border-r border-zinc-700 p-4 overflow-y-auto">
        {SidebarContent}
      </aside>
      
      {/* Main Content: Takes remaining space, for download queue */}
      <main className="flex-grow p-6 overflow-y-auto">
        {MainContent}
      </main>
    </div>
  );
}
