import { AlertTriangle, Bot, CheckCircle } from 'lucide-react';
import type { SkillInfo } from './types';
import { useSessionStore } from '@/store/sessionStore';

interface Props {
  skills: SkillInfo[];
  onClose: () => void;
}

export function SkillsTab({ skills, onClose }: Props) {
  const useSkill = (skill: SkillInfo) => {
    const store = useSessionStore.getState();
    const sessionId = store.sessionId;

    store.toggleSkill(skill.id);

    for (const tool of skill.tools) {
      if (tool.origin === 'plugin' && tool.endpoint_url) {
        store.addPlugin({ name: tool.name, url: tool.endpoint_url });
      }
    }

    const skillContext = {
      skill_id: skill.id,
      skill_name: skill.name,
      tools: skill.tools.map(t => ({
        name: t.name,
        category: t.category,
        parameters: t.parameters,
        origin: t.origin,
      })),
      workspace_prepared: false,
    };

    window.dispatchEvent(new CustomEvent('ag-skill-activate', {
      detail: {
        skill: skillContext,
        prompt: skill.prompt,
        sessionId,
      }
    }));

    window.dispatchEvent(new CustomEvent('ag-insert-prompt', {
      detail: {
        text: skill.prompt,
        context: skillContext,
      }
    }));

    onClose();
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {skills.map((skill) => (
        <div key={skill.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Bot className="h-4 w-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-100">{skill.name}</h3>
                <Status ready={!!skill.ready} />
              </div>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{skill.description}</p>
            </div>
            <button onClick={() => useSkill(skill)} className="rounded-xl bg-cyan-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-cyan-500">
              {skill.ready ? 'Use Skill' : 'Use Partial'}
            </button>
          </div>
          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/70 p-3 text-xs text-slate-400">
            <div className="mb-2 font-semibold uppercase tracking-wider text-slate-500">Suggested Prompt</div>
            {skill.prompt}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {skill.tools.map((tool) => (
              <span key={tool.name} className="rounded-full border border-slate-700 bg-slate-800 px-2.5 py-1 text-[11px] text-slate-300">
                {tool.name}
              </span>
            ))}
            {skill.missing_tools?.map((tool) => (
              <span key={tool} className="rounded-full border border-amber-700/50 bg-amber-950/30 px-2.5 py-1 text-[11px] text-amber-300">
                missing: {tool}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Status({ ready }: { ready: boolean }) {
  return ready ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300"><CheckCircle className="h-3 w-3" />Ready</span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300"><AlertTriangle className="h-3 w-3" />Partial</span>
  );
}
