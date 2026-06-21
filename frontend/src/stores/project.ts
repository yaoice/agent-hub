import { defineStore } from 'pinia'

/** 看板当前选中的项目，跨组件共享（看板页与顶部切换器）。 */
export const useProjectStore = defineStore('project', {
  state: () => ({
    currentProjectId: undefined as number | undefined,
  }),
  actions: {
    setCurrent(id?: number) {
      this.currentProjectId = id
    },
  },
})
