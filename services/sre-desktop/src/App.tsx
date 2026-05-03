import { useState } from 'react';
import { Taskbar } from './components/Taskbar';
import { Window } from './components/Window';
import { SRELeadDashboard } from './components/SRELeadDashboard';
import { Activity, ShieldAlert, MessageSquare } from 'lucide-react';
import 'regenerator-runtime/runtime';

export interface AppState {
  id: string;
  name: string;
  icon: string;
  isOpen: boolean;
  isMinimized: boolean;
}

const INITIAL_APPS: AppState[] = [
  { id: 'dashboard', name: 'CentificAI SRE Dashboard', icon: 'activity', isOpen: true, isMinimized: false },
  { id: 'incidents', name: 'Active Incidents', icon: 'alert', isOpen: false, isMinimized: false },
  { id: 'logs', name: 'Loki Logs', icon: 'logs', isOpen: false, isMinimized: false },
  { id: 'chat', name: 'SRE Agent Chat', icon: 'chat', isOpen: false, isMinimized: false },
];

function App() {
  const [apps, setApps] = useState<AppState[]>(INITIAL_APPS);

  const toggleApp = (id: string) => {
    setApps(prev => prev.map(app => {
      if (app.id === id) {
        if (!app.isOpen) {
          return { ...app, isOpen: true, isMinimized: false };
        }
        return { ...app, isMinimized: !app.isMinimized };
      }
      return app;
    }));
  };

  const closeApp = (id: string) => {
    setApps(prev => prev.map(app => {
      if (app.id === id && app.isOpen) {
        return { ...app, isOpen: false, isMinimized: false };
      }
      return app;
    }));
  };

  const getAppContent = (id: string) => {
    switch (id) {
      case 'dashboard':
        return <SRELeadDashboard />;
      case 'incidents':
        return (
          <div className="h-full w-full flex flex-col text-gray-800 bg-white p-4">
            <div className="flex justify-between items-center mb-4 border-b border-gray-200 pb-2">
              <h2 className="text-xl font-semibold text-red-600 flex items-center gap-2"><ShieldAlert size={20}/> Active Incidents</h2>
              <span className="bg-red-600 text-white px-2 py-1 rounded text-xs font-bold">1 CRITICAL</span>
            </div>
            <div className="bg-red-50 p-4 rounded-md border-l-4 border-l-red-500 mb-4 cursor-pointer hover:bg-red-100 transition-colors">
              <div className="flex justify-between">
                <h3 className="font-semibold text-red-900">food-orders 5xx spike</h3>
                <span className="text-xs text-red-500">2 mins ago</span>
              </div>
              <p className="text-sm mt-2 text-red-700">High error rate detected on food-orders service. Severity: HIGH.</p>
              <div className="mt-3 flex gap-2">
                <button className="bg-red-600 text-white px-3 py-1 rounded text-xs font-medium hover:bg-red-700 transition-colors">Investigate</button>
              </div>
            </div>
          </div>
        );
      case 'logs':
        return (
          <div className="h-full w-full font-mono text-sm bg-[#1E293B] text-[#4ADE80] p-4 rounded overflow-hidden flex flex-col">
            <div className="text-gray-400 mb-2 border-b border-gray-700 pb-2 flex justify-between">
              <span>user@sre-agent:~$ tail -f /var/log/loki.log</span>
              <span className="animate-pulse">_</span>
            </div>
            <div className="flex-1 overflow-y-auto space-y-1">
              <div className="text-white">[INFO] [food-orders] Starting HTTP request...</div>
              <div className="text-white">[INFO] [portfolio-web] Request completed in 45ms</div>
              <div className="text-red-400 font-bold">[ERROR] [food-orders] Connection timeout to database!</div>
              <div className="text-red-400 font-bold">[FATAL] [food-orders] Unhandled exception in payments module</div>
              <div className="text-white">[INFO] [agent] Detected signal: 5xx spike on food-orders</div>
              <div className="text-yellow-400">[WARN] [agent] SLA ACK satisfied. Starting investigation...</div>
            </div>
          </div>
        );
      case 'chat':
        return (
          <div className="h-full w-full flex flex-col bg-[#F1F5F9] rounded">
            <div className="flex-1 p-4 overflow-y-auto space-y-4">
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#5929d0] to-[#CF008B] flex items-center justify-center text-white shrink-0"><Activity size={16}/></div>
                <div className="bg-white rounded-lg p-3 text-sm text-gray-800 max-w-[80%] border border-gray-200 shadow-sm">
                  <p>Hello! I am the SRE Agent. I noticed a critical issue on <span className="text-red-600 font-mono">food-orders</span>.</p>
                  <p className="mt-2">I have analyzed the logs and metrics. Would you like me to propose a remediation?</p>
                </div>
              </div>
              <div className="flex gap-3 flex-row-reverse">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white shrink-0 text-xs font-bold">PT</div>
                <div className="bg-[#5929d0] rounded-lg p-3 text-sm text-white max-w-[80%] shadow-md">
                  Yes, please investigate and propose a fix.
                </div>
              </div>
            </div>
            <div className="p-3 border-t border-gray-200 bg-white">
              <div className="relative">
                <input type="text" placeholder="Type a message to the agent..." className="w-full bg-gray-100 border border-gray-200 rounded-full py-2 px-4 text-sm text-gray-800 focus:outline-none focus:border-[#5929d0] transition-colors" />
                <button className="absolute right-2 top-1.5 p-1 text-gray-400 hover:text-[#5929d0]"><MessageSquare size={16}/></button>
              </div>
            </div>
          </div>
        );
      default: return null;
    }
  };

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-cover bg-center" style={{ backgroundImage: 'linear-gradient(to bottom right, #f8fafc, #e2e8f0, #cbd5e1)' }}>
      {/* Desktop Background / Watermark */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03]">
        <Activity size={400} className="text-[#5929d0]" />
      </div>
      
      {/* Render open windows */}
      {apps.map(app => (
        <Window 
          key={app.id}
          title={app.name}
          isOpen={app.isOpen}
          isMinimized={app.isMinimized}
          onClose={() => closeApp(app.id)}
          onMinimize={() => toggleApp(app.id)}
          icon={<Activity size={14} className="text-[#5929d0]" />}
          width={app.id === 'dashboard' ? Math.min(window.innerWidth - 80, 1300) : 800}
          height={app.id === 'dashboard' ? Math.min(window.innerHeight - 100, 850) : 600}
        >
          {getAppContent(app.id)}
        </Window>
      ))}

      {/* Taskbar */}
      <Taskbar 
        apps={apps} 
        toggleApp={toggleApp} 
      />
    </div>
  );
}

export default App;
