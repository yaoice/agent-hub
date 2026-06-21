<template>
  <a-spin :spinning="loading">
    <div class="users">
      <div class="toolbar">
        <div>
          <h3 class="title">用户管理</h3>
          <p class="desc">查看与维护系统用户，支持新增、编辑、禁用与角色分配。</p>
        </div>
        <div class="toolbar-actions">
          <a-input-search
            v-model:value="search"
            placeholder="搜索用户名"
            allow-clear
            style="width: 220px"
            @search="loadList"
          />
          <a-button type="primary" @click="openCreate">
            <template #icon><PlusOutlined /></template>
            新增用户
          </a-button>
        </div>
      </div>

      <a-table :data-source="users" :columns="columns" row-key="id" :pagination="false">
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'role'">
            <a-tag :color="record.role === 'admin' ? 'red' : 'blue'">
              {{ record.role === 'admin' ? '管理员' : '普通用户' }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'is_active'">
            <a-switch
              :checked="record.is_active"
              :disabled="record.id === auth.user?.id"
              @change="(v: string | number | boolean) => toggleStatus(record, v as boolean)"
            />
          </template>
          <template v-else-if="column.key === 'created_at'">
            {{ formatTime(record.created_at) }}
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
            <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
          </template>
        </template>
      </a-table>

      <!-- 新增/编辑弹窗 -->
      <a-modal
        v-model:open="dialogVisible"
        :title="editing ? '编辑用户' : '新增用户'"
        :confirm-loading="saving"
        width="460px"
        @ok="submit"
      >
        <a-form ref="formRef" :model="form" :rules="rules" :label-col="{ style: { width: '90px' } }">
          <a-form-item label="用户名" name="username">
            <a-input v-model:value="form.username" :disabled="!!editing" placeholder="登录用户名" />
          </a-form-item>

          <!-- 新增：直接设置初始密码 -->
          <a-form-item v-if="!editing" label="密码" name="password">
            <a-input-password v-model:value="form.password" placeholder="初始密码（≥4 位）" />
          </a-form-item>

          <!-- 编辑：修改密码需原密码 + 新密码二次确认（留空则不修改密码） -->
          <template v-else>
            <a-form-item label="原密码" name="current_password">
              <a-input-password
                v-model:value="form.current_password"
                autocomplete="current-password"
                placeholder="管理员本人当前密码（不修改密码可留空）"
              />
            </a-form-item>
            <a-form-item label="新密码" name="password">
              <a-input-password
                v-model:value="form.password"
                autocomplete="new-password"
                placeholder="留空表示不修改密码（≥4 位）"
              />
            </a-form-item>
            <a-form-item label="确认新密码" name="confirm_password">
              <a-input-password
                v-model:value="form.confirm_password"
                autocomplete="new-password"
                placeholder="再次输入新密码"
              />
            </a-form-item>
          </template>

          <a-form-item label="角色" name="role">
            <a-select v-model:value="form.role">
              <a-select-option value="user">普通用户</a-select-option>
              <a-select-option value="admin">管理员</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>

      <!-- 详情抽屉 -->
      <a-drawer v-model:open="detailVisible" title="用户详情" width="420">
        <template v-if="detail">
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="用户名">{{ detail.username }}</a-descriptions-item>
            <a-descriptions-item label="角色">
              {{ detail.role === 'admin' ? '管理员' : '普通用户' }}
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="detail.is_active ? 'green' : 'default'">
                {{ detail.is_active ? '启用' : '禁用' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="创建时间">
              {{ formatTime(detail.created_at) }}
            </a-descriptions-item>
          </a-descriptions>
          <h4 class="member-title">所属项目（{{ detail.memberships.length }}）</h4>
          <a-list
            :data-source="detail.memberships"
            size="small"
            bordered
            :locale="{ emptyText: '未加入任何项目' }"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                {{ item.project_name }}
                <template #actions>
                  <a-tag :color="item.project_role === 'project_admin' ? 'purple' : 'default'">
                    {{ item.project_role === 'project_admin' ? '项目管理员' : '项目成员' }}
                  </a-tag>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </template>
      </a-drawer>
    </div>
  </a-spin>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'
import { message, type FormInstance } from 'ant-design-vue'
import type { Rule } from 'ant-design-vue/es/form'
import { userApi } from '@/api'
import type { UserDetail, UserRow, UserUpdateForm } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const saving = ref(false)
const users = ref<UserRow[]>([])
const search = ref('')
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detail = ref<UserDetail | null>(null)
const editing = ref<UserRow | null>(null)
const formRef = ref<FormInstance>()

const columns = [
  { title: '用户名', dataIndex: 'username', key: 'username', minWidth: 160 },
  { title: '角色', key: 'role', width: 120 },
  { title: '所属项目数', dataIndex: 'project_count', key: 'project_count', width: 120 },
  { title: '状态', key: 'is_active', width: 100 },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'action', width: 160, fixed: 'right' },
]

const form = reactive({
  username: '',
  password: '',
  role: 'user',
  current_password: '',
  confirm_password: '',
})

const rules = computed<Record<string, Rule[]>>(() => ({
  username: editing.value
    ? []
    : [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: editing.value
    ? [
        {
          // 编辑时新密码可留空（不改）；一旦填写则至少 4 位
          validator: (_r: Rule, v: string) =>
            !v || v.length >= 4
              ? Promise.resolve()
              : Promise.reject('新密码至少 4 位'),
          trigger: 'blur',
        },
      ]
    : [{ required: true, min: 4, message: '请输入至少 4 位密码', trigger: 'blur' }],
  current_password: editing.value
    ? [
        {
          validator: (_r: Rule, v: string) =>
            form.password && !v
              ? Promise.reject('修改密码需输入原密码')
              : Promise.resolve(),
          trigger: 'blur',
        },
      ]
    : [],
  confirm_password: editing.value
    ? [
        {
          validator: (_r: Rule, v: string) =>
            form.password && v !== form.password
              ? Promise.reject('两次输入的新密码不一致')
              : Promise.resolve(),
          trigger: 'blur',
        },
      ]
    : [],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}))

function formatTime(t: string) {
  return new Date(t + (t.endsWith('Z') ? '' : 'Z')).toLocaleString('zh-CN')
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    username: '',
    password: '',
    role: 'user',
    current_password: '',
    confirm_password: '',
  })
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openEdit(row: UserRow) {
  editing.value = row
  Object.assign(form, {
    username: row.username,
    password: '',
    role: row.role,
    current_password: '',
    confirm_password: '',
  })
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function openDetail(row: UserRow) {
  detailVisible.value = true
  detail.value = null
  try {
    detail.value = await userApi.detail(row.id)
  } catch {
    /* 拦截器已提示 */
  }
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
      const payload: UserUpdateForm = { role: form.role }
      if (form.password) {
        payload.password = form.password
        payload.current_password = form.current_password
        payload.confirm_password = form.confirm_password
      }
      await userApi.update(editing.value.id, payload)
    } else {
      await userApi.create({
        username: form.username,
        password: form.password,
        role: form.role,
      })
    }
    message.success('保存成功')
    dialogVisible.value = false
    await loadList()
    // 若修改了自己的角色，刷新登录态
    if (editing.value?.id === auth.user?.id) await auth.fetchMe()
  } catch {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row: UserRow, value: boolean) {
  try {
    await userApi.setStatus(row.id, value)
    message.success(value ? '已启用' : '已禁用')
    await loadList()
  } catch {
    /* 拦截器已提示，回滚由重新加载完成 */
    await loadList()
  }
}

async function loadList() {
  loading.value = true
  try {
    users.value = await userApi.list(search.value || undefined)
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
}
.toolbar-actions {
  display: flex;
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
.member-title {
  margin: 18px 0 10px;
}
</style>
