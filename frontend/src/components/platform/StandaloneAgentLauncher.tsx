import { useState } from 'react';
import { Bot } from 'lucide-react';
import { DigitalEmployeeConsole } from './DigitalEmployeeConsole';

/**
 * Full-screen project editors live outside PlatformShell, so they mount the
 * same deterministic digital-employee console through this compact launcher.
 */
export const StandaloneAgentLauncher = () => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        aria-label="召唤数字员工"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-[70] grid h-14 w-14 place-items-center rounded-full bg-blue-600 text-white shadow-lg transition hover:-translate-y-1 hover:bg-blue-700"
      >
        <Bot size={24} />
      </button>
      <DigitalEmployeeConsole open={open} onClose={() => setOpen(false)} />
    </>
  );
};
