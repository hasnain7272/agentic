import { ChatPane } from '@/features/chat/ChatPane';

export function DashboardMobile() {
  return (
    <main className="flex min-h-0 flex-1 flex-col bg-slate-950 md:hidden">
      <section className="min-h-0 flex-1 overflow-hidden">
        <ChatPane />
      </section>
    </main>
  );
}

export type MobileTab = 'agent';
