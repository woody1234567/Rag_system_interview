<script setup lang="ts">
import type { RagQueryResponse } from '../types/rag'

const question = ref('')
const includeDebug = ref(false)
const loading = ref(false)
const indexing = ref(false)
const health = ref<'checking' | 'ok' | 'down'>('checking')
const errorMsg = ref('')
const indexMsg = ref('')
const result = ref<RagQueryResponse | null>(null)

const { queryRag, buildIndex, checkHealth } = useRagApi()

onMounted(async () => {
  try {
    const res = await checkHealth()
    health.value = res.status === 'ok' ? 'ok' : 'down'
  } catch {
    health.value = 'down'
  }
})

const submitQuery = async () => {
  errorMsg.value = ''
  result.value = null
  if (!question.value.trim()) {
    errorMsg.value = '請輸入問題'
    return
  }

  loading.value = true
  try {
    result.value = await queryRag({ question: question.value, include_debug: includeDebug.value })
  } catch (error: any) {
    errorMsg.value = error?.data?.message || error?.message || '查詢失敗'
  } finally {
    loading.value = false
  }
}

const runIndex = async () => {
  indexMsg.value = ''
  indexing.value = true
  try {
    const res = await buildIndex()
    indexMsg.value = `建索引完成，chunks: ${res.chunks}`
  } catch (error: any) {
    indexMsg.value = error?.data?.message || error?.message || '建索引失敗'
  } finally {
    indexing.value = false
  }
}
</script>

<template>
  <main class="container">
    <h1>RAG Web Demo</h1>
    <p>FastAPI 狀態：<strong>{{ health }}</strong></p>

    <section class="panel">
      <h2>問答</h2>
      <textarea v-model="question" rows="4" placeholder="請輸入問題" />
      <label>
        <input v-model="includeDebug" type="checkbox">
        include debug
      </label>
      <div>
        <button :disabled="loading" @click="submitQuery">
          {{ loading ? '查詢中...' : '送出問題' }}
        </button>
      </div>
      <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
    </section>

    <section v-if="result" class="panel">
      <h2>結果</h2>
      <p><strong>answer:</strong> {{ result.answer }}</p>
      <p><strong>refusal:</strong> {{ result.refusal }}</p>
      <p><strong>reason:</strong> {{ result.reason }}</p>
      <p><strong>sources:</strong> {{ result.sources.join(', ') || 'N/A' }}</p>
      <pre v-if="result.retrieval_debug">{{ result.retrieval_debug }}</pre>
    </section>

    <section class="panel">
      <h2>索引</h2>
      <button :disabled="indexing" @click="runIndex">
        {{ indexing ? '建索引中...' : '重建索引' }}
      </button>
      <p v-if="indexMsg">{{ indexMsg }}</p>
    </section>
  </main>
</template>

<style scoped>
.container { max-width: 860px; margin: 2rem auto; padding: 0 1rem; }
.panel { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
textarea { width: 100%; margin-bottom: 0.5rem; }
.error { color: #c00; }
</style>
