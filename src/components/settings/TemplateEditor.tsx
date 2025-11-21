import React from 'react';
import { createPortal } from 'react-dom';
import { 
    DndContext, 
    closestCenter, 
    KeyboardSensor, 
    PointerSensor, 
    useSensor, 
    useSensors, 
    DragOverlay, 
    defaultDropAnimationSideEffects, 
    DragStartEvent, 
    DragOverEvent 
} from '@dnd-kit/core';
import { 
    arrayMove, 
    SortableContext, 
    sortableKeyboardCoordinates, 
    useSortable, 
    rectSortingStrategy 
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { TemplateBlock } from '@/types';
import { Plus, GripVertical, Trash2 } from 'lucide-react';
import { twMerge } from 'tailwind-merge';
import { v4 as uuidv4 } from 'uuid';

// --- Available Blocks Definition ---

const AVAILABLE_VARS: Omit<TemplateBlock, 'id'>[] = [
    { type: 'variable', value: 'title', label: 'Title' },
    { type: 'variable', value: 'id', label: 'Video ID' },
    { type: 'variable', value: 'uploader', label: 'Uploader' },
    { type: 'variable', value: 'upload_date', label: 'Date' },
    { type: 'variable', value: 'resolution', label: 'Resolution' },
    { type: 'variable', value: 'duration', label: 'Duration' },
    { type: 'variable', value: 'ext', label: 'Extension' },
];

const AVAILABLE_SEPARATORS: Omit<TemplateBlock, 'id'>[] = [
    { type: 'separator', value: '.', label: '.' },
    { type: 'separator', value: ' - ', label: ' - ' },
    { type: 'separator', value: '_', label: '_' },
    { type: 'separator', value: ' ', label: '(Space)' },
];


// --- Sub Components ---

interface BlockProps extends React.HTMLAttributes<HTMLDivElement> {
    block: TemplateBlock;
    isOverlay?: boolean;
    onRemove?: () => void;
}

const Block = React.forwardRef<HTMLDivElement, BlockProps>(({ block, isOverlay, className, onRemove, ...props }, ref) => {
    const isVar = block.type === 'variable';
    
    return (
        <div
            ref={ref}
            className={twMerge(
                "relative flex items-center gap-2 px-3 py-2 rounded-md border text-xs font-bold uppercase tracking-wide select-none transition-all",
                "whitespace-nowrap flex-shrink-0", // Prevent squishing and wrapping
                isVar ? "bg-theme-cyan/10 text-theme-cyan border-theme-cyan/30" : "bg-zinc-800 text-zinc-400 border-zinc-700",
                isOverlay ? "shadow-xl scale-105 cursor-grabbing z-50" : "cursor-grab active:cursor-grabbing",
                className
            )}
            {...props}
        >
            <GripVertical className="h-3 w-3 opacity-50" />
            <span>{block.label}</span>
            {onRemove && (
                <button onClick={(e) => { e.stopPropagation(); onRemove(); }} className="ml-1 hover:text-red-500 transition-colors">
                    <Trash2 className="h-3 w-3" />
                </button>
            )}
        </div>
    );
});
Block.displayName = "Block";

const SortableBlock = ({ block, onRemove }: { block: TemplateBlock, onRemove: (id: string) => void }) => {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
    
    const style = {
        // Use Translate to avoid scaling/stretching distortions on variable width items
        transform: CSS.Translate.toString(transform),
        transition,
        opacity: isDragging ? 0.3 : 1,
    };

    return (
        <Block 
            ref={setNodeRef} 
            style={style} 
            block={block} 
            onRemove={() => onRemove(block.id)}
            {...attributes} 
            {...listeners} 
        />
    );
};


// --- Main Component ---

interface TemplateEditorProps {
    blocks: TemplateBlock[];
    onChange: (blocks: TemplateBlock[]) => void;
}

export function TemplateEditor({ blocks, onChange }: TemplateEditorProps) {
    const [activeId, setActiveId] = React.useState<string | null>(null);

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    const handleDragStart = (event: DragStartEvent) => {
        setActiveId(event.active.id as string);
    };

    // For variable width lists, sorting must happen onDragOver to trigger layout reflow
    const handleDragOver = (event: DragOverEvent) => {
        const { active, over } = event;
        if (over && active.id !== over.id) {
            const oldIndex = blocks.findIndex((b) => b.id === active.id);
            const newIndex = blocks.findIndex((b) => b.id === over.id);

            if (oldIndex !== newIndex) {
                onChange(arrayMove(blocks, oldIndex, newIndex));
            }
        }
    };

    const handleDragEnd = () => {
        setActiveId(null);
    };

    const addBlock = (base: Omit<TemplateBlock, 'id'>) => {
        const newBlock = { ...base, id: uuidv4() };
        onChange([...blocks, newBlock]);
    };

    const removeBlock = (id: string) => {
        onChange(blocks.filter(b => b.id !== id));
    };

    const activeBlock = blocks.find(b => b.id === activeId);

    // Preview string generation
    const previewString = blocks.map(b => b.type === 'variable' ? `[${b.label}]` : b.label).join('');

    return (
        <div className="space-y-6">
            {/* Preview Section */}
            <div className="bg-zinc-950 p-4 rounded-lg border border-zinc-800">
                <div className="text-xs text-zinc-500 mb-2 uppercase font-bold tracking-wider">Output Preview</div>
                <div className="font-mono text-sm text-zinc-300 break-all">
                    {previewString || <span className="text-zinc-600 italic">Empty template...</span>}
                </div>
            </div>

            {/* Editor Area */}
            <div className="space-y-2">
                 <div className="text-xs text-zinc-500 uppercase font-bold tracking-wider">Active Template</div>
                 <div className="min-h-[80px] p-4 bg-zinc-900/50 border border-dashed border-zinc-700 rounded-lg flex flex-wrap gap-2 items-center">
                    <DndContext 
                        sensors={sensors} 
                        collisionDetection={closestCenter} 
                        onDragStart={handleDragStart} 
                        onDragOver={handleDragOver}
                        onDragEnd={handleDragEnd}
                    >
                        <SortableContext items={blocks} strategy={rectSortingStrategy}>
                            {blocks.map((block) => (
                                <SortableBlock key={block.id} block={block} onRemove={removeBlock} />
                            ))}
                        </SortableContext>
                        
                        {blocks.length === 0 && (
                            <div className="w-full text-center text-zinc-600 text-sm">
                                Drag and drop is ready. Add blocks from below.
                            </div>
                        )}

                        {/* FIX: Render overlay in Portal to escape Parent Transforms (Modal animation) */}
                        {createPortal(
                            <DragOverlay dropAnimation={{
                                sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: '0.5' } } }),
                            }}>
                                {activeId && activeBlock ? <Block block={activeBlock} isOverlay /> : null}
                            </DragOverlay>,
                            document.body
                        )}
                    </DndContext>
                 </div>
            </div>

            {/* Toolbox */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-3">
                    <div className="text-xs text-zinc-500 uppercase font-bold tracking-wider">Variables</div>
                    <div className="flex flex-wrap gap-2">
                        {AVAILABLE_VARS.map((v) => (
                            <button 
                                key={v.value}
                                onClick={() => addBlock(v)}
                                className="group flex items-center gap-2 px-3 py-2 rounded-md border border-zinc-800 bg-zinc-900 hover:border-theme-cyan/50 hover:bg-zinc-800 transition-all"
                            >
                                <Plus className="h-3 w-3 text-zinc-500 group-hover:text-theme-cyan" />
                                <span className="text-xs font-medium text-zinc-300 group-hover:text-zinc-100">{v.label}</span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="space-y-3">
                    <div className="text-xs text-zinc-500 uppercase font-bold tracking-wider">Separators</div>
                    <div className="flex flex-wrap gap-2">
                        {AVAILABLE_SEPARATORS.map((s) => (
                            <button 
                                key={s.label}
                                onClick={() => addBlock(s)}
                                className="group flex items-center gap-2 px-3 py-2 rounded-md border border-zinc-800 bg-zinc-900 hover:border-zinc-600 hover:bg-zinc-800 transition-all"
                            >
                                <Plus className="h-3 w-3 text-zinc-500 group-hover:text-zinc-300" />
                                <span className="text-xs font-mono text-zinc-400 group-hover:text-zinc-200">{s.label}</span>
                            </button>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}