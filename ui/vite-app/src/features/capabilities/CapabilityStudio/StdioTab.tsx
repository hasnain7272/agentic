import { StdioRegisterCard } from './StdioRegisterCard';
import { StdioServerList } from './StdioServerList';
import { useStdioServers } from './useStdioServers';

interface Props {
  onServersChanged: () => void;
}

export function StdioTab({ onServersChanged }: Props) {
  const stdio = useStdioServers(onServersChanged);

  return (
    <div className="space-y-6">
      <StdioRegisterCard
        onRegister={stdio.register}
        onError={(message) => stdio.setResult({ id: 'register', status: 'error', data: message })}
      />
      {stdio.result?.id === 'register' && (
        <div className="rounded-lg bg-red-900/20 p-2 text-xs text-red-400">{String(stdio.result.data)}</div>
      )}
      <StdioServerList
        servers={stdio.servers}
        loading={stdio.loading}
        expanded={stdio.expanded}
        tools={stdio.tools}
        executing={stdio.executing}
        result={stdio.result}
        onRefresh={stdio.loadServers}
        onToggle={stdio.toggle}
        onRemove={stdio.remove}
        onRun={stdio.runTool}
      />
    </div>
  );
}
