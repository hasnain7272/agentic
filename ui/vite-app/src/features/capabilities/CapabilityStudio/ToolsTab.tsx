import React from 'react';
import { Server } from 'lucide-react';
import type { ToolInfo, CatalogResponse } from './types';

interface Props {
  tools: ToolInfo[];
  categories: CatalogResponse['categories'];
}

export function ToolsTab({ tools, categories }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {categories.map((category) => (
          <span key={category.id} className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-[11px] text-slate-400">
            {category.label} · {category.count}
          </span>
        ))}
      </div>
      {tools.map((tool) => (
        <div key={tool.name} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-violet-400" />
                <span className="text-sm font-semibold text-slate-100">{tool.name}</span>
                <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] uppercase tracking-wider text-slate-400">{tool.category}</span>
              </div>
              <p className="mt-2 text-sm text-slate-400">{tool.description}</p>
            </div>
            <div className="text-right text-[11px] text-slate-500">
              <div>{tool.origin === 'plugin' ? 'Plugin' : 'Built-in'}</div>
              <div>{tool.requires_sandbox ? 'Sandboxed' : 'Direct'}</div>
            </div>
          </div>
          {tool.parameters.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {tool.parameters.map((param) => (
                <span key={`${tool.name}-${param.name}`} className="rounded-lg bg-slate-950 px-2.5 py-1 text-[11px] text-slate-400 ring-1 ring-slate-800">
                  {param.name}: {param.type}{param.required ? '' : ' ?'}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
