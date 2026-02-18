const { createApp, ref, reactive, onMounted, computed } = Vue;

createApp({
  template: `
    <div class="app">
      <div class="header">
        <h1>⚡ CC Manager</h1>
        <p>Claude Code Task Queue</p>
      </div>
      
      <div class="container">
        <!-- 输入区 -->
        <div class="input-section">
          <textarea 
            v-model="newTask.prompt" 
            placeholder="输入任务 prompt..."
            rows="4"
          ></textarea>
          
          <div style="display: flex; gap: 8px; margin-top: 8px;">
            <input 
              v-model="newTask.project" 
              placeholder="项目名称"
              style="flex: 1; padding: 8px; border: 2px solid #eee; border-radius: 4px;"
            >
            <select v-model="newTask.mode" style="padding: 8px; border: 2px solid #eee; border-radius: 4px;">
              <option value="execute">Execute</option>
              <option value="plan">Plan</option>
            </select>
          </div>
          
          <button @click="submitTask" :disabled="submitting" style="margin-top: 8px;">
            {{ submitting ? '提交中...' : '📤 提交任务' }}
          </button>
        </div>
        
        <!-- Worker 面板 -->
        <h2 style="color: white; margin: 16px 0 8px;">Workers</h2>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px;">
          <div class="worker-card" v-for="w in workers" :key="w.id" :class="'worker-' + w.status">
            <div class="worker-id">#{{ w.id }}</div>
            <div class="worker-status">{{ w.status }}</div>
            <div class="worker-task" v-if="w.current_task_id">Task #{{ w.current_task_id }}</div>
          </div>
        </div>
        
        <!-- 任务列表 -->
        <h2 style="color: white; margin-bottom: 8px;">Tasks</h2>
        <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
          <button 
            v-for="s in ['all', 'queued', 'running', 'done', 'failed']" 
            :key="s"
            @click="filterStatus = s"
            :style="filterStatus === s ? 'background: white; color: #4F8CFF;' : 'background: rgba(255,255,255,0.2); color: white;'"
            style="padding: 4px 12px; border: none; border-radius: 20px; cursor: pointer; font-size: 12px;"
          >
            {{ s }}
          </button>
        </div>
        
        <div class="task-list" v-if="filteredTasks.length > 0">
          <div class="task-item" v-for="task in filteredTasks" :key="task.id">
            <div class="task-info">
              <div class="task-title">{{ task.title }}</div>
              <div class="task-meta">
                {{ task.project }} · ID: {{ task.id }} · {{ formatTime(task.created_at) }}
                <span v-if="task.worker_id"> · Worker #{{ task.worker_id }}</span>
              </div>
            </div>
            <div class="task-status" :class="'status-' + task.status">
              {{ task.status }}
            </div>
          </div>
        </div>
        <div v-else style="background: white; padding: 20px; border-radius: 12px; text-align: center; color: #999;">
          无任务
        </div>
      </div>
    </div>
  `,
  
  setup() {
    const newTask = reactive({
      project: 'deepcell',
      prompt: '',
      mode: 'execute'
    });
    
    const tasks = ref([]);
    const workers = ref([]);
    const filterStatus = ref('all');
    const submitting = ref(false);
    
    const filteredTasks = computed(() => {
      if (filterStatus.value === 'all') return tasks.value;
      return tasks.value.filter(t => t.status === filterStatus.value);
    });
    
    const submitTask = async () => {
      if (!newTask.prompt.trim()) return;
      
      submitting.value = true;
      try {
        const res = await fetch('/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project: newTask.project,
            title: newTask.prompt.substring(0, 60),
            prompt: newTask.prompt,
            mode: newTask.mode
          })
        });
        
        if (res.ok) {
          newTask.prompt = '';
          await Promise.all([loadTasks(), loadWorkers()]);
        }
      } catch (e) {
        console.error('Error:', e);
      } finally {
        submitting.value = false;
      }
    };
    
    const loadTasks = async () => {
      try {
        const res = await fetch('/api/tasks?limit=30');
        if (res.ok) tasks.value = await res.json();
      } catch (e) {}
    };
    
    const loadWorkers = async () => {
      try {
        const res = await fetch('/api/workers');
        if (res.ok) workers.value = await res.json();
      } catch (e) {}
    };
    
    const formatTime = (iso) => {
      return new Date(iso).toLocaleString('zh-CN', { 
        month: '2-digit', 
        day: '2-digit',
        hour: '2-digit', 
        minute: '2-digit' 
      });
    };
    
    onMounted(() => {
      loadTasks();
      loadWorkers();
      
      // 每 2 秒刷新
      setInterval(() => {
        loadTasks();
        loadWorkers();
      }, 2000);
      
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
      }
    });
    
    return {
      newTask,
      tasks,
      workers,
      filterStatus,
      filteredTasks,
      submitting,
      submitTask,
      loadTasks,
      formatTime
    };
  }
}).mount('#app');
