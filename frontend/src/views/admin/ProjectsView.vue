<template>
  <a-spin :spinning="loading">
    <div class="projects">
      <div class="toolbar">
        <div>
          <h3 class="title">项目管理</h3>
          <p class="desc">
            录入项目并选择 Provider 类型、配置访问凭证、分配成员，支持手动同步数据入库。
          </p>
        </div>
        <a-button type="primary" @click="openCreate">
          <template #icon><PlusOutlined /></template>
          新增项目
        </a-button>
      </div>

      <a-table :data-source="projects" :columns="columns" row-key="id" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'provider'">
            <a-tag color="geekblue">{{ record.provider_display_name }}</a-tag>
          </template>
          <template v-else-if="column.key === 'is_active'">
            <a-tag :color="record.is_active ? 'green' : 'default'">
              {{ record.is_active ? '启用' : '停用' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'last_sync'">
            <span v-if="record.last_sync_at">
              {{ formatTime(record.last_sync_at) }}
              <a-tag :color="record.last_sync_source === 'live' ? 'green' : 'orange'" size="small">
                {{ record.last_sync_source === 'live' ? '实时' : 'Mock' }}
              </a-tag>
            </span>
            <span v-else class="muted">未同步</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" :loading="syncingId === record.id" @click="openSyncDialog(record)">
              同步
            </a-button>
            <a-button type="link" size="small" @click="openMembers(record)">成员</a-button>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
            <a-popconfirm title="确认删除该项目？相关同步数据将一并删除。" @confirm="remove(record)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>

      <!-- 新增/编辑弹窗 -->
      <a-modal
        v-model:open="dialogVisible"
        :title="editing ? '编辑项目' : '新增项目'"
        :confirm-loading="saving"
        width="540px"
        @ok="submit"
      >
        <a-form ref="formRef" :model="form" :rules="rules" :label-col="{ style: { width: '110px' } }">
          <a-form-item label="项目名称" name="name">
            <a-input v-model:value="form.name" placeholder="例如：客服智能体项目" />
          </a-form-item>
          <a-form-item label="Provider" name="provider_type_key">
            <a-select v-model:value="form.provider_type_key" placeholder="选择 Provider 类型">
              <a-select-option
                v-for="p in selectableProviders"
                :key="p.type_key"
                :value="p.type_key"
              >
                {{ p.display_name }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="HOST" name="host">
            <a-input v-model:value="form.host" placeholder="例如：aiagent.example.com" />
          </a-form-item>
          <a-form-item label="SECRET_ID" name="secret_id">
            <a-input v-model:value="form.secret_id" placeholder="访问密钥 ID" />
          </a-form-item>
          <a-form-item label="SECRET_KEY" name="secret_key">
            <a-input-password
              v-model:value="form.secret_key"
              :placeholder="editing ? '留空表示不修改' : '访问密钥 Key'"
            />
          </a-form-item>
          <a-form-item label="Region">
            <a-input v-model:value="form.region" placeholder="默认 1" />
          </a-form-item>
          <a-form-item label="启用">
            <a-switch v-model:checked="form.is_active" />
          </a-form-item>
        </a-form>
      </a-modal>

      <!-- 成员管理抽屉 -->
      <a-drawer
        v-model:open="memberVisible"
        :title="`成员管理 · ${currentProject?.name || ''}`"
        width="460"
      >
        <div class="member-add">
          <a-select
            v-model:value="newMemberUserId"
            placeholder="选择用户"
            style="flex: 1"
            show-search
            option-filter-prop="label"
            :options="candidateOptions"
          />
          <a-select v-model:value="newMemberRole" style="width: 130px">
            <a-select-option value="member">项目成员</a-select-option>
            <a-select-option value="project_admin">项目管理员</a-select-option>
          </a-select>
          <a-button type="primary" :disabled="!newMemberUserId" @click="addMember">添加</a-button>
        </div>

        <a-list
          :data-source="members"
          size="small"
          bordered
          :locale="{ emptyText: '暂无成员' }"
          class="member-list"
        >
          <template #renderItem="{ item }">
            <a-list-item>
              <a-list-item-meta :title="item.username">
                <template #description>
                  <a-tag :color="item.project_role === 'project_admin' ? 'purple' : 'default'">
                    {{ item.project_role === 'project_admin' ? '项目管理员' : '项目成员' }}
                  </a-tag>
                </template>
              </a-list-item-meta>
              <template #actions>
                <a-popconfirm title="移除该成员？" @confirm="removeMember(item)">
                  <a-button type="link" size="small" danger>移除</a-button>
                </a-popconfirm>
              </template>
            </a-list-item>
          </template>
        </a-list>
      </a-drawer>

      <!-- 同步范围选择弹窗 -->
      <a-modal
        v-model:open="syncVisible"
        :title="`同步数据 · ${syncTarget?.name || ''}`"
        :confirm-loading="syncing"
        :ok-button-props="{ disabled: !syncScopes.length }"
        ok-text="开始同步"
        width="440px"
        @ok="confirmSync"
      >
        <p class="sync-tip">请选择需要同步的数据范围（可多选）：</p>
        <a-checkbox
          :checked="checkAll"
          :indeterminate="indeterminate"
          @change="onCheckAllChange"
        >
          全选
        </a-checkbox>
        <a-divider style="margin: 12px 0" />
        <a-checkbox-group v-model:value="syncScopes" class="sync-group">
          <a-checkbox
            v-for="opt in scopeOptions"
            :key="opt.value"
            :value="opt.value"
            class="sync-item"
          >
            {{ opt.label }}
            <span class="sync-desc">{{ opt.desc }}</span>
          </a-checkbox>
        </a-checkbox-group>
        <template v-if="syncScopes.includes('conversations')">
          <a-divider style="margin: 12px 0" />
          <a-checkbox v-model:checked="syncFull">
            全量回补
            <span class="sync-desc">忽略增量水位，按时间范围全量拉取（首次/补数据用）</span>
          </a-checkbox>
        </template>
      </a-modal>
    </div>
  </a-spin>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { message, Modal, type FormInstance } from 'ant-design-vue'
import type { Rule } from 'ant-design-vue/es/form'
import { projectApi, providerApi, userApi } from '@/api'
import type { Project, ProjectForm, ProjectMember, Provider, SyncScope, UserRow } from '@/types'

const loading = ref(false)
const saving = ref(false)
const syncingId = ref<number | null>(null)

// 同步范围选择
const scopeOptions: { label: string; value: SyncScope; desc: string }[] = [
  { label: '应用数量', value: 'app_count', desc: '空间/应用盘点' },
  { label: '应用对话记录', value: 'conversations', desc: '遍历应用拉取对话' },
  { label: 'token消耗', value: 'token', desc: 'Token 消耗排行' },
]
const syncVisible = ref(false)
const syncing = ref(false)
const syncTarget = ref<Project | null>(null)
const syncScopes = ref<SyncScope[]>([])
const syncFull = ref(false)
const checkAll = computed(() => syncScopes.value.length === scopeOptions.length)
const indeterminate = computed(
  () => syncScopes.value.length > 0 && syncScopes.value.length < scopeOptions.length,
)

const projects = ref<Project[]>([])
const providers = ref<Provider[]>([])
const allUsers = ref<UserRow[]>([])
const dialogVisible = ref(false)
const editing = ref<Project | null>(null)
const formRef = ref<FormInstance>()

const memberVisible = ref(false)
const currentProject = ref<Project | null>(null)
const members = ref<ProjectMember[]>([])
const newMemberUserId = ref<number>()
const newMemberRole = ref('member')

const columns = [
  { title: '项目名称', dataIndex: 'name', key: 'name', minWidth: 160 },
  { title: 'Provider', key: 'provider', width: 130 },
  { title: 'HOST', dataIndex: 'host', key: 'host', minWidth: 180, ellipsis: true },
  { title: '成员数', dataIndex: 'member_count', key: 'member_count', width: 90 },
  { title: '最近同步', key: 'last_sync', minWidth: 200 },
  { title: '状态', key: 'is_active', width: 90 },
  { title: '操作', key: 'action', width: 240, fixed: 'right' },
]

const selectableProviders = computed(() =>
  providers.value.filter((p) => p.enabled && p.implemented),
)

const candidateOptions = computed(() => {
  const memberIds = new Set(members.value.map((m) => m.user_id))
  return allUsers.value
    .filter((u) => !memberIds.has(u.id))
    .map((u) => ({ value: u.id, label: u.username }))
})

const form = reactive<ProjectForm>({
  name: '',
  provider_type_key: '',
  host: '',
  region: '1',
  is_active: true,
  secret_id: '',
  secret_key: '',
})

const rules = computed<Record<string, Rule[]>>(() => ({
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  provider_type_key: [{ required: true, message: '请选择 Provider', trigger: 'change' }],
  host: [{ required: true, message: '请输入 HOST', trigger: 'blur' }],
  secret_id: editing.value ? [] : [{ required: true, message: '请输入 SECRET_ID', trigger: 'blur' }],
  secret_key: editing.value ? [] : [{ required: true, message: '请输入 SECRET_KEY', trigger: 'blur' }],
}))

function formatTime(t: string) {
  return new Date(t + (t.endsWith('Z') ? '' : 'Z')).toLocaleString('zh-CN')
}

function resetForm() {
  Object.assign(form, {
    name: '',
    provider_type_key: selectableProviders.value[0]?.type_key || '',
    host: '',
    region: '1',
    is_active: true,
    secret_id: '',
    secret_key: '',
  })
}

function openCreate() {
  editing.value = null
  resetForm()
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openEdit(row: Project) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    provider_type_key: row.provider_type_key,
    host: row.host,
    region: row.region,
    is_active: row.is_active,
    secret_id: '',
    secret_key: '',
  })
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function submit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      const payload: Partial<ProjectForm> = {
        name: form.name,
        provider_type_key: form.provider_type_key,
        host: form.host,
        region: form.region,
        is_active: form.is_active,
      }
      if (form.secret_id) payload.secret_id = form.secret_id
      if (form.secret_key) payload.secret_key = form.secret_key
      await projectApi.update(editing.value.id, payload)
    } else {
      await projectApi.create(form)
    }
    message.success('保存成功')
    dialogVisible.value = false
    await loadList()
  } catch {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

async function remove(row: Project) {
  try {
    await projectApi.remove(row.id)
    message.success('已删除')
    await loadList()
  } catch {
    /* ignore */
  }
}

async function sync(row: Project, scopes: SyncScope[], full: boolean) {
  syncingId.value = row.id
  try {
    const res = await projectApi.sync(row.id, { scopes, full })
    Modal[res.ok ? 'success' : 'warning']({
      title: res.ok ? '同步成功' : '同步提示',
      content: res.message,
    })
    await loadList()
  } catch {
    /* 拦截器已提示 */
  } finally {
    syncingId.value = null
  }
}

function openSyncDialog(row: Project) {
  syncTarget.value = row
  // 默认全选
  syncScopes.value = scopeOptions.map((o) => o.value)
  syncFull.value = false
  syncVisible.value = true
}

function onCheckAllChange(e: { target: { checked: boolean } }) {
  syncScopes.value = e.target.checked ? scopeOptions.map((o) => o.value) : []
}

async function confirmSync() {
  if (!syncTarget.value || !syncScopes.value.length) return
  syncing.value = true
  try {
    await sync(syncTarget.value, [...syncScopes.value], syncFull.value)
    syncVisible.value = false
  } finally {
    syncing.value = false
  }
}

async function openMembers(row: Project) {
  currentProject.value = row
  memberVisible.value = true
  members.value = []
  newMemberUserId.value = undefined
  newMemberRole.value = 'member'
  try {
    const [m, u] = await Promise.all([projectApi.members(row.id), userApi.list()])
    members.value = m
    allUsers.value = u
  } catch {
    /* 拦截器已提示 */
  }
}

async function addMember() {
  if (!currentProject.value || !newMemberUserId.value) return
  try {
    await projectApi.addMember(currentProject.value.id, newMemberUserId.value, newMemberRole.value)
    message.success('已添加成员')
    newMemberUserId.value = undefined
    members.value = await projectApi.members(currentProject.value.id)
    await loadList()
  } catch {
    /* 拦截器已提示 */
  }
}

async function removeMember(item: ProjectMember) {
  if (!currentProject.value) return
  try {
    await projectApi.removeMember(currentProject.value.id, item.user_id)
    message.success('已移除成员')
    members.value = await projectApi.members(currentProject.value.id)
    await loadList()
  } catch {
    /* 拦截器已提示 */
  }
}

async function loadList() {
  loading.value = true
  try {
    projects.value = await projectApi.list()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    providers.value = await providerApi.list()
  } catch {
    /* ignore */
  }
  await loadList()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
}
.title {
  margin: 0 0 4px;
}
.desc {
  margin: 0;
  color: #8a909d;
  font-size: 13px;
}
.muted {
  color: #8a909d;
}
.member-add {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.member-list {
  margin-top: 8px;
}
.sync-tip {
  margin: 0 0 12px;
  color: #5a6072;
}
.sync-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}
.sync-item {
  margin-left: 0 !important;
}
.sync-desc {
  margin-left: 8px;
  color: #9aa0ad;
  font-size: 12px;
}
</style>
