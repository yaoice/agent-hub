<template>
  <a-spin :spinning="loading">
    <div class="providers">
      <div class="toolbar">
        <div>
          <h3 class="title">Provider 管理</h3>
          <p class="desc">
            内置 Provider 类型目录。可启用/禁用类型；禁用后项目创建时将无法选择。未实现类型自动置灰。
          </p>
        </div>
      </div>

      <a-row :gutter="[16, 16]">
        <a-col v-for="p in providers" :key="p.type_key" :xs="24" :sm="12" :lg="8">
          <a-card :bordered="false" class="provider-card" :class="{ disabled: !p.implemented }">
            <div class="card-head">
              <div class="card-title">
                <ApiOutlined class="card-icon" />
                <span>{{ p.display_name }}</span>
              </div>
              <a-tag v-if="!p.implemented" color="default">未实现</a-tag>
              <a-tag v-else :color="p.enabled ? 'green' : 'orange'">
                {{ p.enabled ? '已启用' : '已禁用' }}
              </a-tag>
            </div>
            <p class="card-desc">{{ p.description }}</p>
            <div class="card-foot">
              <span class="type-key">{{ p.type_key }}</span>
              <a-tooltip :title="!p.implemented ? '该 Provider 尚未实现，暂不可启用' : ''">
                <a-switch
                  :checked="p.enabled"
                  :disabled="!p.implemented || togglingKey === p.type_key"
                  :loading="togglingKey === p.type_key"
                  checked-children="启用"
                  un-checked-children="禁用"
                  @change="(v: string | number | boolean) => toggle(p, v as boolean)"
                />
              </a-tooltip>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </a-spin>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ApiOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { providerApi } from '@/api'
import type { Provider } from '@/types'

const loading = ref(false)
const togglingKey = ref<string | null>(null)
const providers = ref<Provider[]>([])

async function toggle(p: Provider, value: boolean) {
  togglingKey.value = p.type_key
  try {
    await providerApi.setEnabled(p.type_key, value)
    message.success(value ? '已启用' : '已禁用')
    await loadList()
  } catch {
    await loadList()
  } finally {
    togglingKey.value = null
  }
}

async function loadList() {
  loading.value = true
  try {
    providers.value = await providerApi.list()
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
}
.title {
  margin: 0 0 4px;
}
.desc {
  margin: 0;
  color: #8a909d;
  font-size: 13px;
}
.provider-card {
  border-radius: 12px;
  box-shadow: 0 2px 10px rgba(31, 41, 64, 0.05);
  height: 100%;
}
.provider-card.disabled {
  opacity: 0.6;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
}
.card-icon {
  color: #4f6ef7;
}
.card-desc {
  margin: 12px 0 16px;
  color: #8a909d;
  font-size: 13px;
  min-height: 38px;
}
.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.type-key {
  font-family: monospace;
  color: #9aa0ad;
  font-size: 12px;
}
</style>
