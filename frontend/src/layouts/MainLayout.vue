<template>
  <a-layout class="layout">
    <a-layout-sider
      v-model:collapsed="collapsed"
      :trigger="null"
      collapsible
      :width="220"
      class="aside"
    >
      <div class="brand">
        <FundOutlined :style="{ fontSize: '22px' }" />
        <span v-show="!collapsed" class="brand-text">智能体运营中心</span>
      </div>
      <a-menu
        theme="dark"
        mode="inline"
        :selected-keys="[activeMenu]"
        :open-keys="openKeys"
        @click="onMenuClick"
        @openChange="(keys: (string | number)[]) => (openKeys = keys as string[])"
      >
        <a-menu-item key="/dashboard">
          <template #icon><DashboardOutlined /></template>
          <span>运营看板</span>
        </a-menu-item>
        <a-menu-item key="/conversations">
          <template #icon><MessageOutlined /></template>
          <span>对话记录</span>
        </a-menu-item>
        <a-sub-menu v-if="auth.isAdmin" key="admin">
          <template #icon><SettingOutlined /></template>
          <template #title>管理面板</template>
          <a-menu-item key="/admin/users">
            <template #icon><TeamOutlined /></template>
            <span>用户管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/projects">
            <template #icon><ProjectOutlined /></template>
            <span>项目管理</span>
          </a-menu-item>
          <a-menu-item key="/admin/providers">
            <template #icon><ApiOutlined /></template>
            <span>Provider 管理</span>
          </a-menu-item>
        </a-sub-menu>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <a-layout-header class="header">
        <div class="header-left">
          <MenuUnfoldOutlined v-if="collapsed" class="collapse-btn" @click="collapsed = !collapsed" />
          <MenuFoldOutlined v-else class="collapse-btn" @click="collapsed = !collapsed" />
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <a-tag :color="auth.isAdmin ? 'red' : 'blue'">
            {{ auth.isAdmin ? '管理员' : '普通用户' }}
          </a-tag>
          <a-dropdown>
            <span class="user-chip">
              <UserOutlined />
              {{ auth.user?.username }}
              <DownOutlined />
            </span>
            <template #overlay>
              <a-menu @click="onCommand">
                <a-menu-item key="logout">退出登录</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <a-layout-content class="main">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ApiOutlined,
  DashboardOutlined,
  DownOutlined,
  FundOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
  ProjectOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'

const collapsed = ref(false)
const openKeys = ref<string[]>(['admin'])
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => route.path)
const pageTitle = computed(() => (route.meta.title as string) || '运营看板')

function onMenuClick({ key }: { key: string }) {
  if (key !== route.path) router.push(key)
}

function onCommand({ key }: { key: string }) {
  if (key === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout {
  height: 100vh;
}
.aside {
  background: #1f2940;
  overflow: hidden;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60px;
  padding: 0 18px;
  color: #fff;
  font-weight: 700;
  white-space: nowrap;
}
.brand-text {
  font-size: 15px;
}
.aside :deep(.ant-menu.ant-menu-dark) {
  background: transparent;
}
.aside :deep(.ant-menu-dark .ant-menu-item-selected) {
  background: var(--ah-primary);
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  padding: 0 20px;
  border-bottom: 1px solid #eef0f5;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.collapse-btn {
  cursor: pointer;
  font-size: 20px;
  color: #5a6072;
}
.page-title {
  font-size: 16px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #1f2329;
  outline: none;
}
.main {
  padding: 20px;
  overflow-y: auto;
}
</style>
