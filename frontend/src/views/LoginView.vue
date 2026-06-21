<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-left">
        <div class="hero">
          <FundOutlined :style="{ fontSize: '40px' }" />
          <h1>智能体运营中心</h1>
          <p>聚合空间应用盘点与 Token 消耗，统一掌控 AI 智能体资产全景。</p>
        </div>
      </div>
      <div class="login-right">
        <h2>欢迎登录</h2>
        <p class="sub">Agent Operation Console</p>
        <a-form :model="form" layout="vertical" @finish="onSubmit">
          <a-form-item>
            <a-input v-model:value="form.username" size="large" placeholder="用户名">
              <template #prefix><UserOutlined /></template>
            </a-input>
          </a-form-item>
          <a-form-item>
            <a-input-password
              v-model:value="form.password"
              size="large"
              placeholder="密码"
              @keyup.enter="onSubmit"
            >
              <template #prefix><LockOutlined /></template>
            </a-input-password>
          </a-form-item>
          <a-button
            type="primary"
            size="large"
            class="submit"
            block
            :loading="loading"
            html-type="submit"
          >
            登 录
          </a-button>
        </a-form>
        <a-alert
          type="info"
          show-icon
          message="默认管理员账号：admin / admin"
          class="tip"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { FundOutlined, LockOutlined, UserOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin' })

async function onSubmit() {
  if (!form.username || !form.password) {
    message.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    await auth.fetchMe()
    message.success('登录成功')
    router.push('/dashboard')
  } catch {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #4f6ef7 0%, #7c3aed 100%);
  padding: 16px;
}
.login-card {
  width: 880px;
  max-width: 100%;
  min-height: 460px;
  display: flex;
  background: #fff;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.2);
}
.login-left {
  flex: 1;
  background: linear-gradient(135deg, #3b4ea8 0%, #4f6ef7 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}
.hero {
  max-width: 320px;
}
.hero h1 {
  font-size: 26px;
  margin: 16px 0 12px;
}
.hero p {
  line-height: 1.7;
  opacity: 0.9;
}
.login-right {
  flex: 1;
  padding: 56px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.login-right h2 {
  margin: 0;
  font-size: 24px;
}
.sub {
  color: #9aa0ad;
  margin: 6px 0 28px;
}
.submit {
  width: 100%;
}
.tip {
  margin-top: 18px;
}
@media (max-width: 720px) {
  .login-left {
    display: none;
  }
  .login-right {
    padding: 40px 28px;
  }
}
</style>
