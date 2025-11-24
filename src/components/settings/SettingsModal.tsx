import React, { useRef } from 'react';
import { Modal } from '../ui/Modal';
import { GeneralSettings } from './GeneralSettings';
import { YtdlpSettings } from './YtdlpSettings';
import { AboutSettings } from './AboutSettings';
import { Settings, Youtube, Info, ChevronRight } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

type TabId = 'general' | 'ytdlp' | 'about';

interface SubTab {
    id: string;
    label: string;
}

interface TabConfig {
    id: TabId;
    label: string;
    icon: React.ElementType;
    subs: SubTab[];
    animationClass: string;
}

const TABS: TabConfig[] = [
    { 
        id: 'general', 
        label: 'General', 
        icon: Settings,
        animationClass: 'group-hover:animate-[spin_3s_linear_infinite]',
        subs: [
            { id: 'section-queue', label: 'Queue Management' },
            { id: 'section-logging', label: 'Logging' },
        ]
    },
    { 
        id: 'ytdlp', 
        label: 'YT-DLP', 
        icon: Youtube, 
        animationClass: 'group-hover:animate-pulse',
        subs: [
            { id: 'section-formatting', label: 'Filename Formatting' },
            { id: 'section-cookies', label: 'Cookies & Auth' },
        ]
    },
    { 
        id: 'about', 
        label: 'About', 
        icon: Info, 
        // Changed from animate-bounce to custom animate-float to fix jumpiness
        animationClass: 'group-hover:animate-float',
        subs: []
    },
];

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
    const [activeTab, setActiveTab] = React.useState<TabId>('general');
    const contentRef = useRef<HTMLDivElement>(null);

    const scrollToSection = (sectionId: string) => {
        const element = document.getElementById(sectionId);
        if (element && contentRef.current) {
            element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    const handleTabChange = (id: TabId) => {
        setActiveTab(id);
        // Reset scroll position when changing main tabs
        if (contentRef.current) {
            contentRef.current.scrollTop = 0;
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="Settings">
            <div className="flex flex-col md:flex-row gap-6 -mx-2 min-h-[500px]">
                
                {/* Sticky Sidebar */}
                <nav className="w-full md:w-60 flex-shrink-0 relative">
                    <div className="sticky top-0 space-y-1 pr-2">
                        {TABS.map((tab) => {
                            const isActive = activeTab === tab.id;
                            const Icon = tab.icon;

                            return (
                                <div key={tab.id} className="space-y-1 transition-all duration-300">
                                    <button
                                        onClick={() => handleTabChange(tab.id)}
                                        className={twMerge(
                                            "group w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                                            isActive
                                                ? "bg-theme-cyan/10 text-theme-cyan ring-1 ring-theme-cyan/20"
                                                : "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50"
                                        )}
                                    >
                                        <Icon className={twMerge("h-4 w-4 transition-colors", isActive ? "text-theme-cyan" : "text-zinc-500 group-hover:text-zinc-300", tab.animationClass)} />
                                        <span className="flex-1 text-left">{tab.label}</span>
                                        {tab.subs.length > 0 && (
                                            <ChevronRight className={twMerge("h-3 w-3 transition-transform duration-300", isActive ? "rotate-90 text-theme-cyan/50" : "text-zinc-600")} />
                                        )}
                                    </button>

                                    {/* Sub-tabs Animation Container */}
                                    <div 
                                        className={twMerge(
                                            "grid transition-all duration-300 ease-in-out pl-9 overflow-hidden",
                                            isActive && tab.subs.length > 0 ? "grid-rows-[1fr] opacity-100 mb-2" : "grid-rows-[0fr] opacity-0"
                                        )}
                                    >
                                        <div className="min-h-0 space-y-0.5 border-l border-zinc-800 pl-2 ml-1">
                                            {tab.subs.map(sub => (
                                                <button
                                                    key={sub.id}
                                                    onClick={() => scrollToSection(sub.id)}
                                                    className="w-full text-left px-2 py-1.5 text-xs text-zinc-500 hover:text-theme-cyan hover:bg-zinc-800/30 rounded transition-colors flex items-center gap-2 group/sub"
                                                >
                                                    <span className="w-1 h-1 rounded-full bg-zinc-700 group-hover/sub:bg-theme-cyan transition-colors" />
                                                    {sub.label}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </nav>

                {/* Scrollable Content Area */}
                <div 
                    ref={contentRef}
                    className="flex-1 min-w-0 md:border-l md:border-zinc-800/50 md:pl-6 max-h-[65vh] overflow-y-auto pr-2 scroll-smooth"
                >
                    {activeTab === 'general' && <GeneralSettings />}
                    {activeTab === 'ytdlp' && <YtdlpSettings />}
                    {activeTab === 'about' && <AboutSettings />}
                </div>
            </div>
        </Modal>
    );
}