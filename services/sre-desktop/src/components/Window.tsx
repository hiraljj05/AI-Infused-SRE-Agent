import { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { X, Minus, Maximize } from 'lucide-react';

interface WindowProps {
  title: string;
  isOpen: boolean;
  isMinimized: boolean;
  onClose: () => void;
  onMinimize: () => void;
  children: ReactNode;
  icon?: ReactNode;
  width?: number;
  height?: number;
}

export function Window({ title, isOpen, isMinimized, onClose, onMinimize, children, icon, width = 1100, height = 750 }: WindowProps) {
  if (!isOpen) return null;

  return (
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ 
        scale: isMinimized ? 0 : 1, 
        opacity: isMinimized ? 0 : 1,
        y: isMinimized ? 500 : 0,
      }}
      exit={{ scale: 0.8, opacity: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      style={{ width, height, maxWidth: '100vw', maxHeight: 'calc(100vh - 56px)' }}
      className="absolute top-10 left-10 bg-white rounded-xl shadow-2xl flex flex-col overflow-hidden border border-[var(--color-n7)] z-10"
      drag
      dragConstraints={{ left: 0, right: window.innerWidth - width, top: 0, bottom: window.innerHeight - height - 60 }}
    >
      {/* Title bar - MacOS style */}
      <div className="h-12 bg-white flex items-center justify-between px-4 cursor-move select-none border-b border-[var(--color-n7)]">
        {/* Traffic Lights */}
        <div className="flex items-center space-x-2">
          <button onClick={onClose} className="w-3 h-3 rounded-full bg-[#FF5F56] border border-[#E0443E] hover:bg-[#FF5F56]/80 flex items-center justify-center group"><X size={8} className="opacity-0 group-hover:opacity-100 text-red-900" /></button>
          <button onClick={onMinimize} className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-[#DEA123] hover:bg-[#FFBD2E]/80 flex items-center justify-center group"><Minus size={8} className="opacity-0 group-hover:opacity-100 text-yellow-900" /></button>
          <button className="w-3 h-3 rounded-full bg-[#27C93F] border border-[#1AAB29] hover:bg-[#27C93F]/80 flex items-center justify-center group"><Maximize size={8} className="opacity-0 group-hover:opacity-100 text-green-900" /></button>
        </div>
        
        {/* Title */}
        <div className="flex items-center space-x-2 text-[var(--color-n1)] font-semibold text-sm absolute left-1/2 transform -translate-x-1/2">
          {icon}
          <span>{title}</span>
        </div>

        <div className="w-[42px]" /> {/* Spacer to balance absolute center */}
      </div>
      
      {/* Content area */}
      <div className="flex-1 bg-[var(--color-n8)] relative overflow-hidden flex flex-col">
        {children}
      </div>
    </motion.div>
  );
}
