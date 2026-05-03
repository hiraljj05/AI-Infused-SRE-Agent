import { Activity, ShieldAlert, MessageSquare, TerminalSquare, FileText } from 'lucide-react';
import { AppState } from '../App';

interface TaskbarProps {
  apps: AppState[];
  toggleApp: (id: string) => void;
}

export function Taskbar({ apps, toggleApp }: TaskbarProps) {
  const getIcon = (iconName: string) => {
    switch (iconName) {
      case 'activity': return <Activity size={24} />;
      case 'alert': return <ShieldAlert size={24} />;
      case 'logs': return <TerminalSquare size={24} />;
      case 'chat': return <MessageSquare size={24} />;
      default: return <FileText size={24} />;
    }
  };

  const currentTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="absolute bottom-0 left-0 w-full h-14 bg-white/90 backdrop-blur-md border-t border-gray-200 flex items-center justify-between px-4 z-50 shadow-[0_-4px_20px_rgba(0,0,0,0.05)]">
      <div className="flex items-center space-x-2 h-full">
        {/* Start Button Area */}
        <div className="h-10 w-10 bg-gradient-to-br from-[#5929d0] to-[#CF008B] rounded-md flex items-center justify-center text-white mr-4 shadow-lg shadow-[#5929d0]/20 cursor-pointer hover:opacity-90 transition-opacity font-bold text-lg">
          C
        </div>

        {/* App Icons */}
        <div className="flex items-center space-x-2 h-full">
          {apps.map(app => (
            <button
              key={app.id}
              onClick={() => toggleApp(app.id)}
              className={`h-10 w-12 flex flex-col items-center justify-center rounded-md transition-all relative group
                ${app.isOpen ? 'bg-gray-100 hover:bg-gray-200' : 'hover:bg-gray-50'}
              `}
              title={app.name}
            >
              <div className={`${app.isOpen ? 'text-[#5929d0]' : 'text-gray-500'} transition-colors group-hover:text-[#5929d0]`}>
                {getIcon(app.icon)}
              </div>
              {app.isOpen && (
                <div className={`absolute bottom-0 w-6 h-1 rounded-t-sm transition-all ${app.isMinimized ? 'bg-gray-400' : 'bg-[#5929d0]'}`} />
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center space-x-6 text-gray-600 text-sm font-medium">
        <div className="flex flex-col items-end leading-tight">
          <span className="text-[#0F172A] font-bold">{currentTime}</span>
          <span className="text-xs text-gray-500">{new Date().toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  );
}
