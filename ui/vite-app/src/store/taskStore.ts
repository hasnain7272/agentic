import { create } from 'zustand';

interface Task {
  id: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

interface TaskState {
  activeTaskId: string | null;
  tasks: Record<string, Task>;
  setActiveTask: (id: string) => void;
  upsertTask: (task: Task) => void;
  clearTasks: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  activeTaskId: null,
  tasks: {},
  setActiveTask: (id) => set({ activeTaskId: id }),
  upsertTask: (task) =>
    set((state) => ({
      tasks: { ...state.tasks, [task.id]: task },
    })),
  clearTasks: () => set({ activeTaskId: null, tasks: {} }),
}));
