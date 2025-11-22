import React from 'react';
import { Modal } from '../ui/Modal';
import { useAppContext } from '@/contexts/AppContext';
import { TemplateEditor } from './TemplateEditor';
import { GeneralSettings } from './GeneralSettings';
import { Settings, FileType } from 'lucide-react';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
    const { filenameTemplateBlocks, setFilenameTemplateBlocks } = useAppContext();
    const [activeTab, setActiveTab] = React.useState('general');

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="Preferences">
            <div className="flex flex-col md:flex-row gap-6">
                {/* Sidebar Navigation */}
                <nav className="w-full md:w-48 flex-shrink-0 space-y-1">
                    <button
                        onClick={() => setActiveTab('general')}
                        className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                            activeTab === 'general'
                                ? 'bg-theme-cyan/10 text-theme-cyan'
                                : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'
                        }`}
                    >
                        <Settings className="h-4 w-4" />
                        General
                    </button>
                    <button
                        onClick={() => setActiveTab('template')}
                        className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                            activeTab === 'template' 
                                ? 'bg-theme-cyan/10 text-theme-cyan' 
                                : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'
                        }`}
                    >
                        <FileType className="h-4 w-4" />
                        Filename Template
                    </button>
                </nav>

                {/* Content Area */}
                <div className="flex-1 min-w-0">
                    {activeTab === 'general' && (
                        <GeneralSettings />
                    )}
                    {activeTab === 'template' && (
                        <div className="space-y-4 animate-fade-in">
                            <div>
                                <h3 className="text-base font-medium text-zinc-100">Filename Formatting</h3>
                                <p className="text-sm text-zinc-500">
                                    Drag and drop blocks to customize how your downloaded files are named.
                                </p>
                            </div>
                            <hr className="border-zinc-800" />
                            
                            <TemplateEditor 
                                blocks={filenameTemplateBlocks} 
                                onChange={setFilenameTemplateBlocks} 
                            />
                        </div>
                    )}
                </div>
            </div>
        </Modal>
    );
}