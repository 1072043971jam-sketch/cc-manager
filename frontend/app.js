const { createApp, ref, reactive, onMounted } = Vue;

createApp({
  template: `
    <div class="app">
      <div class="header">
        <h1>⚡ CC Manager</h1>
        <p>Claude Code Task Queue</p>
      </div>
      
      <div class="container">
        <div class="input-section">
          <textarea 
            v-model="newTask.prompt" 
            placeholder="输入任务 prompt..."
          ></textarea>
          
          <div style="margin-top: 12px;">
            <input 
              v-model="newTask.project" 
              placeholder="项目名称 (如 deepcell)"
              style="width: 100%;"
            >
          </div>
          
          <button @click="submitTask">📤 提交任务</button>
        </div>
        
        <div>
          <h2 style="color: white; margin-bottom: 12px;">任务队列</h2>
          <div class="task-list" v-if="tasks.length > 0">
            <div class="task-item" v-for="task in tasks" :key="task.id">
              <div class="task-info">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  {{ task.project }} · ID: {{ task.id }} · {{ formatTime(task.created_at) }}
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
    </div>
  `,
  
  setup() {
    const newTask = reactive({
      project: 'deepcell',
      prompt: ''
    });
    
    const tasks = ref([]);
    
    const submitTask = async () => {
      if (!newTask.prompt.trim()) {
        alert('请输入任务 prompt');
        return;
      }
      
      try {
        const res = await fetch('/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project: newTask.project,
            title: newTask.prompt.substring(0, 50),
            prompt: newTask.prompt,
            mode: 'execute'
          })
        });
        
        if (res.ok) {
          console.log('Task submitted');
          newTask.prompt = '';
          loadTasks();
        }
      } catch (e) {
        console.error('Error:', e);
      }
    };
    
    const loadTasks = async () => {
      try {
        const res = await fetch('/api/tasks?limit=20');
        if (res.ok) {
          tasks.value = await res.json();
        }
      } catch (e) {
        console.error('Error:', e);
      }
    };
    
    const formatTime = (isoString) => {
      const date = new Date(isoString);
      return date.toLocaleString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    };
    
    onMounted(() => {
      loadTasks();
      setInterval(loadTasks, 2000);
      
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
      }
    });
    
    return {
      newTask,
      tasks,
      submitTask,
      loadTasks,
      formatTime
    };
  }
}).mount('#app');
